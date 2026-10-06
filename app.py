#!/usr/bin/env python3
"""Local web server + API for controlling the KORAD KA3005P/PS power supply.

Usage:  python app.py [--port 8585] [--device /dev/ttyACM0] [--host 127.0.0.1]
Then open http://127.0.0.1:8585
"""
import argparse
import collections
import json
import os
import queue
import re
import sys
import threading
import time

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

import examples
from datalog import DataLogger, EventLog, safe_name
from korad import Korad, KoradError
from scripting import ScriptRunner
from sequencer import sequence_code

BASE = os.path.dirname(os.path.abspath(__file__))
FROZEN = bool(getattr(sys, "frozen", False))          # packaged with PyInstaller
BUNDLE = getattr(sys, "_MEIPASS", BASE)               # where static/ and the example scripts/ live


def _data_root():
    """Folder with user data (scripts, logs, sequences).
    From source = the project folder; packaged app = the user profile (overridden by KORAD_HOME)."""
    env = os.environ.get("KORAD_HOME")
    if env:
        return os.path.abspath(env)
    if not FROZEN:
        return BASE
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Korad")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Korad")
    return os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "korad")


HOME = _data_root()
HIDE_SN = os.environ.get("KORAD_HIDE_SN", "") not in ("", "0")
SCRIPTS_DIR = os.path.join(HOME, "scripts")
LOGS_DIR = os.path.join(HOME, "logs")
STATIC_DIR = os.path.join(BUNDLE, "static")
DATA_DIR = os.path.join(HOME, "data")
SEQ_DIR = os.path.join(DATA_DIR, "sequences")
PRESETS_FILE = os.path.join(DATA_DIR, "presets.json")
DEFAULT_PRESETS = [{"v": 3.3, "i": 1.0}, {"v": 5.0, "i": 1.0}, {"v": 9.0, "i": 1.0},
                   {"v": 12.0, "i": 2.0}, {"v": 24.0, "i": 2.0}, {"v": 30.0, "i": 5.0}]
HISTORY_SECONDS = 3600  # server-side buffer for the trend chart (survives page refresh)
POLL_INTERVAL = 0.5     # the PSU responds slowly (~80 ms/command) and resets its USB when overloaded
SET_REFRESH_EVERY = 3   # every Nth poll also reads VSET/ISET
RECONNECT_EVERY = 3.0   # automatic reconnect attempt [s]


class Broker:
    """Simple pub/sub for SSE clients."""

    def __init__(self):
        self.clients = set()
        self.lock = threading.Lock()

    def subscribe(self):
        q = queue.Queue(maxsize=500)
        with self.lock:
            self.clients.add(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            self.clients.discard(q)

    def publish(self, event, data):
        msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        with self.lock:
            for q in list(self.clients):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass


class Controller:
    def __init__(self, device=None):
        self.dev = Korad(device)
        self.broker = Broker()
        self.events = EventLog(os.path.join(LOGS_DIR, "events.log"), self.broker)
        self.logger = DataLogger(LOGS_DIR, self.broker)
        self.scripts = ScriptRunner(self)
        self.scripts_dir = SCRIPTS_DIR
        self.state = {
            "connected": False, "port": None, "idn": None, "error": None,
            "vset": 0.0, "iset": 0.0, "vout": 0.0, "iout": 0.0, "power": 0.0,
            "mode": "CV", "output": False, "ocp": False, "ovp": False, "beep": False,
            "ocp_limit": None, "ovp_limit": None, "limits_supported": True,
            "t": 0.0,
        }
        self.cmd_history = []
        self.history = collections.deque(maxlen=int(HISTORY_SECONDS / POLL_INTERVAL) + 10)
        self._last_out_cmd = 0.0
        self.auto_reconnect = False
        self._last_reconnect = 0.0
        self._n = 0
        self._refresh_set = threading.Event()
        self.dev.on_command = self._on_command
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True, name="poller")
        self.poll_thread.start()

    # --- events ---
    def _on_command(self, cmd, resp):
        if cmd in ("VOUT1?", "IOUT1?", "STATUS?", "VSET1?", "ISET1?", "OCP1?", "OVP1?"):
            return
        if cmd in ("OUT0", "OUT1"):
            self._last_out_cmd = time.time()
        e = {"t": time.time(), "cmd": cmd, "resp": resp}
        self.cmd_history.append(e)
        if len(self.cmd_history) > 300:
            del self.cmd_history[:100]
        self.broker.publish("cmd", e)

    def refresh_set(self):
        self._refresh_set.set()

    # --- connection ---
    def connect(self, port=None, baud=None):
        if baud:
            self.dev.baud = int(baud)
        idn = self.dev.connect(port)
        if HIDE_SN:  # KORAD_HIDE_SN=1 -> serial number is hidden in the UI (screen sharing, screenshots)
            idn = re.sub(r"SN:\S+", "SN:••••••", idn)
        self.state.update(connected=True, port=self.dev.port, idn=idn, error=None)
        self.auto_reconnect = True
        self.events.add(f"Connected: {idn} ({self.dev.port})")
        self.refresh_set()
        return idn

    def disconnect(self):
        self.auto_reconnect = False
        self.dev.close()
        self.state.update(connected=False, error=None)
        self.events.add("Disconnected")
        self.broker.publish("state", self.state)

    # --- polling ---
    def _poll_loop(self):
        while True:
            t0 = time.monotonic()
            if self.dev.connected:
                try:
                    self._poll_once()
                except KoradError as e:
                    self.state.update(error=str(e), connected=self.dev.connected)
                    self.events.add(f"Communication error: {e}", "error")
                    self.broker.publish("state", self.state)
            else:
                if self.state["connected"]:
                    self.state.update(connected=False)
                    self.broker.publish("state", self.state)
                if self.auto_reconnect and time.monotonic() - self._last_reconnect > RECONNECT_EVERY:
                    self._last_reconnect = time.monotonic()
                    try:
                        self.connect()
                    except KoradError as e:
                        self.state.update(error=f"Reconnect failed: {e}")
                        self.broker.publish("state", self.state)
            dt = POLL_INTERVAL - (time.monotonic() - t0)
            if dt > 0:
                time.sleep(dt)

    def _poll_once(self):
        d = self.dev
        self._n += 1
        # with the output off the display shows the set values -> read them more often
        every = 1 if not self.state["output"] else SET_REFRESH_EVERY
        if self._refresh_set.is_set() or self._n % every == 0:
            self._refresh_set.clear()
            self.state["vset"] = d.get_vset()
            self.state["iset"] = d.get_iset()
            if self.state["limits_supported"]:
                ocp_l, ovp_l = d.get_ocp_limit(), d.get_ovp_limit()
                if ocp_l is None or ovp_l is None:
                    self.state["limits_supported"] = False  # older firmware without OCP1?/OVP1?
                else:
                    self.state.update(ocp_limit=ocp_l, ovp_limit=ovp_l)
        vout = d.get_vout()
        iout = d.get_iout()
        st = d.status()
        if self.state["output"] and not st["output"] and time.time() - self._last_out_cmd > 2:
            self.events.add("Output switched off by the PSU itself (OCP/OVP protection or front-panel button)", "warn")
        self.state.update(
            vout=vout, iout=iout, power=round(vout * iout, 3),
            mode="CV" if st["cv"] else "CC",
            output=st["output"], ocp=st["ocp"], ovp=st["ovp"], beep=st["beep"],
            t=time.time(), error=None, connected=True,
        )
        self.history.append((round(self.state["t"], 3), vout, iout, self.state["power"], int(st["output"])))
        self.logger.tick(self.state)
        self.broker.publish("state", self.state)

    def script_status(self):
        return self.scripts.info()


# ---------------------------------------------------------------- Flask
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
ctl: Controller = None  # type: ignore


def ok(**kw):
    kw.setdefault("ok", True)
    return jsonify(kw)


def err(msg, code=400):
    return jsonify(ok=False, error=str(msg)), code


@app.errorhandler(KoradError)
def _korad_err(e):
    return err(e, 503)


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# --- state / connection ---
@app.get("/api/state")
def api_state():
    return jsonify(state=ctl.state, script=ctl.script_status(), logger=ctl.logger.info(),
                   paths={"home": HOME, "scripts": SCRIPTS_DIR, "logs": LOGS_DIR})


@app.get("/api/history")
def api_history():
    """Recent samples for the trend chart: [[t, vout, iout, power, output], ...]."""
    secs = min(HISTORY_SECONDS, max(1, int(request.args.get("seconds", HISTORY_SECONDS))))
    cut = time.time() - secs
    return jsonify(samples=[h for h in list(ctl.history) if h[0] >= cut])


@app.get("/api/ports")
def api_ports():
    return jsonify(ports=Korad.port_list(), current=ctl.dev.port, baud=ctl.dev.baud)


@app.post("/api/connect")
def api_connect():
    j = request.json or {}
    port = j.get("port") or None
    try:
        idn = ctl.connect(port, j.get("baud"))
    except KoradError as e:
        ctl.state.update(connected=False, error=str(e))
        ctl.broker.publish("state", ctl.state)
        return err(e, 503)
    return ok(idn=idn, port=ctl.dev.port)


@app.post("/api/disconnect")
def api_disconnect():
    ctl.disconnect()
    return ok()


# --- control ---
@app.post("/api/set")
def api_set():
    j = request.json or {}
    out = {}
    if "v" in j and j["v"] is not None:
        out["vset"] = ctl.state["vset"] = ctl.dev.set_v(j["v"])
        ctl.events.add(f"VSET {out['vset']:.2f} V")
    if "i" in j and j["i"] is not None:
        out["iset"] = ctl.state["iset"] = ctl.dev.set_i(j["i"])
        ctl.events.add(f"ISET {out['iset']:.3f} A")
    ctl.refresh_set()
    return ok(**out)


def _bool_route(name, fn):
    def view():
        on = bool((request.json or {}).get("on"))
        fn(on)
        ctl.events.add(f"{name} {'ON' if on else 'OFF'}")
        return ok(on=on)
    view.__name__ = f"api_{name.lower()}"
    return view


app.add_url_rule("/api/output", view_func=_bool_route("Output", lambda on: ctl.dev.output(on)), methods=["POST"])
app.add_url_rule("/api/ocp", view_func=_bool_route("OCP", lambda on: ctl.dev.ocp(on)), methods=["POST"])
app.add_url_rule("/api/ovp", view_func=_bool_route("OVP", lambda on: ctl.dev.ovp(on)), methods=["POST"])
app.add_url_rule("/api/beep", view_func=_bool_route("Beep", lambda on: ctl.dev.beep(on)), methods=["POST"])


@app.post("/api/limits")
def api_limits():
    j = request.json or {}
    out = {}
    if j.get("ocp") is not None:
        out["ocp_limit"] = ctl.dev.set_ocp_limit(j["ocp"])
        ctl.events.add(f"OCP threshold {out['ocp_limit']:.3f} A")
    if j.get("ovp") is not None:
        out["ovp_limit"] = ctl.dev.set_ovp_limit(j["ovp"])
        ctl.events.add(f"OVP threshold {out['ovp_limit']:.2f} V")
    ctl.refresh_set()
    return ok(**out)


@app.post("/api/memory/<int:slot>/<action>")
def api_memory(slot, action):
    if action == "save":
        ctl.dev.save(slot)
        ctl.events.add(f"Saved to M{slot}")
    elif action == "recall":
        ctl.dev.recall(slot)
        ctl.refresh_set()
        ctl.events.add(f"Recalled M{slot}")
    else:
        return err("Unknown action")
    return ok()


@app.post("/api/raw")
def api_raw():
    j = request.json or {}
    cmd = (j.get("cmd") or "").strip()
    if not cmd:
        return err("Empty command")
    expect = bool(j.get("expect", cmd.endswith("?")))
    resp = ctl.dev.raw(cmd, 1 if expect else 0)
    ctl.refresh_set()
    return ok(cmd=cmd, resp=resp)


@app.get("/api/commands")
def api_commands():
    return jsonify(items=ctl.cmd_history[-200:])


# --- scripts ---
def _script_path(name):
    name = safe_name(name)
    if not name.endswith(".py"):
        name += ".py"
    return name, os.path.join(SCRIPTS_DIR, name)


@app.get("/api/scripts")
def api_scripts():
    items = []
    for fn in sorted(os.listdir(SCRIPTS_DIR)):
        if fn.endswith(".py"):
            st = os.stat(os.path.join(SCRIPTS_DIR, fn))
            items.append({"name": fn, "size": st.st_size, "mtime": st.st_mtime})
    return jsonify(items=items, runner=ctl.script_status())


@app.get("/api/scripts/<name>")
def api_script_get(name):
    name, p = _script_path(name)
    if not os.path.isfile(p):
        return err("Script does not exist", 404)
    with open(p, encoding="utf-8") as f:
        return jsonify(name=name, code=f.read())


@app.put("/api/scripts/<name>")
def api_script_put(name):
    name, p = _script_path(name)
    code = (request.json or {}).get("code", "")
    with open(p, "w", encoding="utf-8") as f:
        f.write(code)
    ctl.events.add(f"Script '{name}' saved")
    return ok(name=name)


@app.delete("/api/scripts/<name>")
def api_script_delete(name):
    name, p = _script_path(name)
    if os.path.isfile(p):
        os.remove(p)
        ctl.events.add(f"Script '{name}' deleted")
    return ok()


@app.post("/api/scripts/run")
def api_script_run():
    j = request.json or {}
    name = j.get("name") or "editor"
    code = j.get("code")
    if code is None:
        name, p = _script_path(name)
        if not os.path.isfile(p):
            return err("Script does not exist", 404)
        with open(p, encoding="utf-8") as f:
            code = f.read()
    try:
        ctl.scripts.start(name, code)
    except RuntimeError as e:
        return err(e, 409)
    return ok(runner=ctl.script_status())


@app.post("/api/scripts/stop")
def api_script_stop():
    ctl.scripts.stop()
    return ok()


@app.get("/api/scripts/status")
def api_script_status():
    return jsonify(ctl.script_status())


# --- logging ---
@app.get("/api/logs")
def api_logs():
    return jsonify(items=ctl.logger.list(), logger=ctl.logger.info())


@app.post("/api/logs/start")
def api_logs_start():
    j = request.json or {}
    if not ctl.dev.connected:
        return err("PSU is not connected", 503)
    name = ctl.logger.start(j.get("name") or "log", j.get("interval") or 1.0)
    ctl.events.add(f"Logging started: {name}")
    return ok(name=name, logger=ctl.logger.info())


@app.post("/api/logs/stop")
def api_logs_stop():
    was = ctl.logger.stop()
    ctl.events.add(f"Logging stopped: {was}")
    return ok(logger=ctl.logger.info())


@app.get("/api/logs/<name>")
def api_log_download(name):
    try:
        return send_file(ctl.logger.path(name), as_attachment=True, download_name=os.path.basename(name))
    except FileNotFoundError:
        return err("Log does not exist", 404)


@app.get("/api/logs/<name>/data")
def api_log_data(name):
    try:
        return jsonify(ctl.logger.read(name, int(request.args.get("limit", 3000))))
    except FileNotFoundError:
        return err("Log does not exist", 404)


@app.delete("/api/logs/<name>")
def api_log_delete(name):
    try:
        ctl.logger.delete(name)
    except FileNotFoundError:
        return err("Log does not exist", 404)
    return ok()


@app.get("/api/events")
def api_events():
    return jsonify(items=ctl.events.list(int(request.args.get("limit", 200))))


# --- U/I presets ---
def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


@app.get("/api/presets")
def api_presets():
    return jsonify(items=_load_json(PRESETS_FILE, DEFAULT_PRESETS))


@app.put("/api/presets")
def api_presets_put():
    items = (request.json or {}).get("items") or []
    items = [{"v": round(float(p.get("v", 0)), 2), "i": round(float(p.get("i", 0)), 3)} for p in items][:12]
    _save_json(PRESETS_FILE, items)
    return ok(items=items)


@app.post("/api/presets/<int:n>/apply")
def api_preset_apply(n):
    items = _load_json(PRESETS_FILE, DEFAULT_PRESETS)
    if not 0 <= n < len(items):
        return err("Invalid preset", 404)
    p = items[n]
    ctl.dev.set_v(p["v"])
    ctl.dev.set_i(p["i"])
    ctl.refresh_set()
    ctl.events.add(f"Preset {n + 1}: {p['v']:.2f} V / {p['i']:.3f} A")
    return ok(**p)


# --- programmable test (sequences) ---
def _seq_path(name):
    name = safe_name(name)
    if not name.endswith(".json"):
        name += ".json"
    return name, os.path.join(SEQ_DIR, name)


@app.get("/api/sequences")
def api_sequences():
    items = [fn for fn in sorted(os.listdir(SEQ_DIR)) if fn.endswith(".json")]
    return jsonify(items=items)


@app.get("/api/sequences/<name>")
def api_sequence_get(name):
    name, p = _seq_path(name)
    if not os.path.isfile(p):
        return err("Sequence does not exist", 404)
    return jsonify(name=name, **_load_json(p, {}))


@app.put("/api/sequences/<name>")
def api_sequence_put(name):
    name, p = _seq_path(name)
    j = request.json or {}
    _save_json(p, {"steps": j.get("steps", []), "start": j.get("start", 1), "end": j.get("end"), "cycles": j.get("cycles", 1)})
    ctl.events.add(f"Sequence '{name}' saved")
    return ok(name=name)


@app.delete("/api/sequences/<name>")
def api_sequence_delete(name):
    name, p = _seq_path(name)
    if os.path.isfile(p):
        os.remove(p)
    return ok()


@app.post("/api/sequences/run")
def api_sequence_run():
    j = request.json or {}
    try:
        code = sequence_code(j.get("steps", []), j.get("start", 1), j.get("end"), j.get("cycles", 1))
        ctl.scripts.start("program:" + safe_name(j.get("name") or "test"), code)
    except (ValueError, RuntimeError) as e:
        return err(e, 409)
    return ok(runner=ctl.script_status(), code=code)


# --- SSE ---
@app.get("/api/stream")
def api_stream():
    q = ctl.broker.subscribe()

    def gen():
        try:
            yield f"event: state\ndata: {json.dumps(ctl.state)}\n\n"
            yield f"event: script\ndata: {json.dumps({'status': ctl.scripts.status, 'name': ctl.scripts.name})}\n\n"
            yield f"event: logger\ndata: {json.dumps(ctl.logger.info())}\n\n"
            while True:
                try:
                    yield q.get(timeout=15)
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            ctl.broker.unsubscribe(q)

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- main
def shutdown(timeout=6.0):
    """Before the app exits: stops a running script the same way as the Stop button
    (output off when psu.safe_off) and closes the CSV log."""
    if ctl is None:
        return
    r = ctl.scripts
    if r.running:
        print(f"Stopping script '{r.name}' before exit…")
        r.stop()
        r.thread.join(timeout)
    if ctl.logger.active:
        ctl.logger.stop()


def create(device=None, autoconnect=True, baud=9600):
    global ctl
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(SEQ_DIR, exist_ok=True)
    changed = examples.sync(os.path.join(BUNDLE, "scripts"), SCRIPTS_DIR)
    for action, files in changed.items():
        if files:
            print(f"Example scripts {action}:", ", ".join(sorted(files)))
    print("Data (scripts, logs):", HOME)
    ctl = Controller(device)
    ctl.dev.baud = baud
    if autoconnect:
        try:
            print("Connected:", ctl.connect(), "on", ctl.dev.port)
        except KoradError as e:
            ctl.state.update(error=str(e))
            print("Could not connect to the PSU:", e, "(connect it from the UI)", file=sys.stderr)
    return app


def main(argv=None):
    ap = argparse.ArgumentParser(description="KORAD KA3005P web control")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8585)
    ap.add_argument("--device", default=None, help="serial port (default: auto-detect)")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--no-autoconnect", action="store_true")
    a = ap.parse_args(argv)
    create(a.device, not a.no_autoconnect, a.baud)
    print(f"Open http://{a.host}:{a.port}")
    app.run(host=a.host, port=a.port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
