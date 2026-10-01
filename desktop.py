#!/usr/bin/env python3
"""Desktop verzia (Linux / macOS / Windows): spustí lokálny server a otvorí UI v natívnom okne.

Vyžaduje: pip install pywebview   (Linux navyše: python3-gi gir1.2-webkit2-4.1 alebo Qt)
Bez pywebview sa otvorí predvolený prehliadač.
"""
import argparse
import os
import socket
import sys
import threading
import webbrowser

import app as korad_app


def _redirect_output():
    """V zabalenej GUI aplikácii (bez konzoly) presmeruje výpisy do súboru logs/app.log."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default=None)
    ap.add_argument("--port", type=int, default=0, help="server port (0 = random free port)")
    ap.add_argument("--browser", action="store_true", help="open in the browser instead of a native window")
    ap.add_argument("--server", action="store_true", help="only run the server, open nothing")
    ap.add_argument("--no-autoconnect", action="store_true")
    a = ap.parse_args()
    _redirect_output()
    port = a.port or free_port()
    korad_app.create(a.device, not a.no_autoconnect)
    t = threading.Thread(
        target=lambda: korad_app.app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False),
        daemon=True,
    )
    t.start()
    url = f"http://127.0.0.1:{port}"
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
            webview.create_window("KORAD KA3005P", url, width=1280, height=860, min_size=(900, 600))
            webview.start()
            return
        except ImportError:
            print("pywebview nie je nainštalované (pip install pywebview) – otváram prehliadač.", file=sys.stderr)
        except Exception as e:  # noqa: BLE001  (napr. chýbajúci WebKitGTK na Linuxe)
            print(f"Natívne okno sa nepodarilo otvoriť ({e}) – otváram prehliadač.", file=sys.stderr)
    webbrowser.open(url)
    try:
        t.join()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
