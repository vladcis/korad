"""Spúšťanie používateľských skriptov (Python) s objektom `psu`.

Skript beží vo vlastnom vlákne. Zastavenie sa vyhodnotí pri každom volaní psu.* alebo psu.wait().
Pri chybe alebo zastavení sa výstup zdroja vypne (ak psu.safe_off == True, čo je predvolené).
"""
import math
import os
import sys
import threading
import time
import traceback
import types


class ScriptStopped(Exception):
    pass


class ScriptPSU:
    """API dostupné skriptom ako `psu`."""

    def __init__(self, runner):
        self._r = runner
        self.safe_off = True

    # --- interné ---
    def _check(self):
        if self._r.stop_event.is_set():
            raise ScriptStopped()

    def _dev(self):
        self._check()
        return self._r.dev

    # --- nastavenie ---
    def set_v(self, volts):
        v = self._dev().set_v(volts)
        self._r.ctl.refresh_set()
        return v

    def set_i(self, amps):
        a = self._dev().set_i(amps)
        self._r.ctl.refresh_set()
        return a

    def set(self, volts=None, amps=None):
        if volts is not None:
            self.set_v(volts)
        if amps is not None:
            self.set_i(amps)

    def on(self):
        self._dev().output(True)

    def off(self):
        # vypnutie výstupu je povolené vždy, aj počas zastavovania skriptu (cleanup vo finally)
        self._r.dev.output(False)

    def output(self, on):
        self._dev().output(bool(on))

    def ocp(self, on):
        self._dev().ocp(bool(on))

    def ovp(self, on):
        self._dev().ovp(bool(on))

    def beep(self, on):
        self._dev().beep(bool(on))

    def save(self, slot):
        self._dev().save(slot)

    def recall(self, slot):
        self._dev().recall(slot)
        self._r.ctl.refresh_set()

    def raw(self, cmd, nbytes=0):
        return self._dev().raw(cmd, nbytes)

    # --- čítanie ---
    @property
    def vout(self):
        return self._dev().get_vout()

    @property
    def iout(self):
        return self._dev().get_iout()

    @property
    def vset(self):
        return self._dev().get_vset()

    @property
    def iset(self):
        return self._dev().get_iset()

    @property
    def power(self):
        d = self._dev()
        return round(d.get_vout() * d.get_iout(), 3)

    def status(self):
        return self._dev().status()

    @property
    def state(self):
        """Posledný stav z pollera (bez komunikácie so zdrojom)."""
        self._check()
        return dict(self._r.ctl.state)

    # --- čas ---
    def wait(self, seconds):
        end = time.monotonic() + float(seconds)
        while True:
            self._check()
            rem = end - time.monotonic()
            if rem <= 0:
                return
            time.sleep(min(0.1, rem))

    sleep = wait

    def ramp_v(self, start, end, duration, step=0.1):
        """Lineárny nábeh napätia zo start na end za duration sekúnd."""
        self._ramp(self.set_v, start, end, duration, step)

    def ramp_i(self, start, end, duration, step=0.01):
        self._ramp(self.set_i, start, end, duration, step)

    def _ramp(self, fn, start, end, duration, step):
        start, end, duration = float(start), float(end), float(duration)
        n = max(1, int(round(abs(end - start) / step)))
        dt = duration / n
        for k in range(n + 1):
            fn(start + (end - start) * k / n)
            if k < n:
                self.wait(dt)

    # --- výstup / logovanie ---
    def log(self, *args):
        self._check()
        self._r.emit(" ".join(str(a) for a in args))

    print = log

    def log_start(self, name=None, interval=0.5):
        self._check()
        return self._r.ctl.logger.start(name or f"script_{self._r.name}", interval)

    def log_stop(self):
        self._r.ctl.logger.stop()

    def elapsed(self):
        """Sekundy od štartu skriptu."""
        return time.time() - self._r.started


class ScriptRunner:
    def __init__(self, ctl):
        self.ctl = ctl  # Controller (app.py) s .dev, .state, .logger, .broker, .refresh_set
        self.thread = None
        self.stop_event = threading.Event()
        self.name = None
        self.started = None
        self.output = []
        self.status = "idle"  # idle | running | done | error | stopped
        self.error = None
        self.lock = threading.Lock()

    @property
    def dev(self):
        return self.ctl.dev

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def emit(self, line):
        entry = {"t": time.time(), "line": str(line)}
        self.output.append(entry)
        if len(self.output) > 2000:
            del self.output[:500]
        self.ctl.broker.publish("script", {"status": self.status, "name": self.name, "line": entry})

    def info(self):
        return {
            "status": self.status,
            "name": self.name,
            "running": self.running,
            "started": self.started,
            "error": self.error,
            "output": self.output[-300:],
        }

    def start(self, name, code):
        with self.lock:
            if self.running:
                raise RuntimeError("Už beží iný skript")
            if not self.ctl.dev.connected:
                raise RuntimeError("Zdroj nie je pripojený")
            self.stop_event.clear()
            self.name = name
            self.started = time.time()
            self.output = []
            self.error = None
            self.status = "running"
            self.thread = threading.Thread(target=self._run, args=(code,), daemon=True, name=f"script-{name}")
            self.thread.start()
            self.ctl.broker.publish("script", {"status": self.status, "name": self.name})

    def stop(self):
        self.stop_event.set()

    def _run(self, code):
        psu = ScriptPSU(self)
        tmod = types.SimpleNamespace(**{k: getattr(time, k) for k in dir(time) if not k.startswith("_")})
        tmod.sleep = psu.wait  # aby bolo možné skript zastaviť aj počas time.sleep()
        env = {
            "__name__": "__script__",
            "__builtins__": __builtins__,
            "psu": psu,
            "log": psu.log,
            "print": psu.log,
            "time": tmod,
            "math": math,
        }
        self.ctl.events.add(f"Skript '{self.name}' spustený")
        # skripty môžu importovať knižnice zo scripts/ (lib_*.py); pri každom behu sa načítajú nanovo
        sdir = getattr(self.ctl, "scripts_dir", None)
        if sdir and sdir not in sys.path:
            sys.path.insert(0, sdir)
        for m in [m for m in sys.modules if m.startswith("lib_")]:
            del sys.modules[m]
        try:
            exec(compile(code, f"<{self.name}>", "exec"), env)
            self.status = "done"
            self.emit("--- skript skončil ---")
        except ScriptStopped:
            self.status = "stopped"
            self.emit("--- skript zastavený ---")
            self._safe_off(psu)
        except Exception:  # noqa: BLE001
            self.status = "error"
            self.error = traceback.format_exc(limit=-3)
            self.emit("CHYBA:\n" + self.error)
            self._safe_off(psu)
        finally:
            self.ctl.events.add(f"Skript '{self.name}' – {self.status}")
            self.ctl.broker.publish("script", {"status": self.status, "name": self.name, "error": self.error})

    def _safe_off(self, psu):
        if psu.safe_off:
            try:
                self.ctl.dev.output(False)
                self.emit("Výstup vypnutý (safe_off)")
            except Exception as e:  # noqa: BLE001
                self.emit(f"Nepodarilo sa vypnúť výstup: {e}")
