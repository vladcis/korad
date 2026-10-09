#!/usr/bin/env python3
"""Desktop version (Linux / macOS / Windows): starts a local server and opens the UI in a native window.

Requires: pip install pywebview   (Linux additionally: python3-gi gir1.2-webkit2-4.1 or Qt)
Without pywebview the default browser is opened.
"""
import argparse
import atexit
import json
import os
import socket
import sys
import threading
import urllib.request
import webbrowser

import app as korad_app

INSTANCE_FILE = os.path.join(korad_app.HOME, "instance.json")   # {pid, url} of the running server


def running_instance():
    """URL of an already running KORAD server (same data folder), or None."""
    try:
        with open(INSTANCE_FILE, encoding="utf-8") as f:
            url = json.load(f)["url"]
        with urllib.request.urlopen(url + "/api/state", timeout=2) as r:
            return url if r.status == 200 else None
    except Exception:  # noqa: BLE001  (no file, stale file, server gone)
        return None


def claim_instance(url):
    os.makedirs(korad_app.HOME, exist_ok=True)
    with open(INSTANCE_FILE, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "url": url}, f)

    def release():
        try:
            with open(INSTANCE_FILE, encoding="utf-8") as f:
                if json.load(f).get("pid") == os.getpid():
                    os.remove(INSTANCE_FILE)
        except Exception:  # noqa: BLE001
            pass
    atexit.register(release)


def _redirect_output():
    """In a packaged GUI app (no console), redirects output to logs/app.log."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    os.makedirs(korad_app.LOGS_DIR, exist_ok=True)
    f = open(os.path.join(korad_app.LOGS_DIR, "app.log"), "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or f
    sys.stderr = sys.stderr or f


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Api:
    """Exposed to the page as window.pywebview.api."""

    def __init__(self, url):
        self._url = url
        self._window = None
        self._closing_ok = False

    def _on_closing(self):
        """Window close: with a script running ask first (in the page), never kill it silently."""
        r = korad_app.ctl.scripts
        if self._closing_ok or not r.running:
            return True
        threading.Thread(target=self._window.evaluate_js, args=("askQuit()",), daemon=True).start()
        return False

    def quit(self):
        """Called by the page after the user confirmed quitting while a script runs."""
        korad_app.shutdown()
        self._closing_ok = True
        self._window.destroy()

    def set_title(self, title):
        if self._window:
            self._window.set_title(title)

    def open_trend(self):
        import webview
        webview.create_window("KORAD – trend", self._url + "/?view=trend", width=1100, height=520, min_size=(500, 260))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default=None)
    ap.add_argument("--port", type=int, default=0, help="server port (0 = random free port)")
    ap.add_argument("--browser", action="store_true", help="open in the browser instead of a native window")
    ap.add_argument("--server", action="store_true", help="only run the server, open nothing")
    ap.add_argument("--no-autoconnect", action="store_true")
    a = ap.parse_args()
    _redirect_output()
    other = running_instance()
    if other and not a.server:
        # a second server would fight over the serial port - show the running one instead
        print(f"KORAD is already running at {other} - opening it instead of starting a second instance.", file=sys.stderr)
        if a.browser:
            webbrowser.open(other)
            return
        try:
            import webview
            webview.create_window("KORAD KA3005P", other, width=1280, height=800, min_size=(900, 600))
            webview.start()
            return
        except Exception:  # noqa: BLE001
            webbrowser.open(other)
            return
    port = a.port or free_port()
    korad_app.create(a.device, not a.no_autoconnect)
    t = threading.Thread(
        target=lambda: korad_app.app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False),
        daemon=True,
    )
    t.start()
    url = f"http://127.0.0.1:{port}"
    claim_instance(url)
    print("UI:", url)
    if a.server:
        try:
            t.join()
        except KeyboardInterrupt:
            pass
        return
    if not a.browser:
        try:
            import webview  # pywebview
            api = Api(url)
            api._window = webview.create_window("KORAD KA3005P", url, width=1280, height=800, min_size=(900, 600),
                                                js_api=api)
            api._window.events.closing += api._on_closing
            try:
                webview.start()
            finally:
                korad_app.shutdown()
            return
        except ImportError:
            print("pywebview is not installed (pip install pywebview) - opening the browser.", file=sys.stderr)
        except Exception as e:  # noqa: BLE001  (e.g. missing WebKitGTK on Linux)
            print(f"Native window could not be opened ({e}) - opening the browser.", file=sys.stderr)
    webbrowser.open(url)
    try:
        t.join()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
