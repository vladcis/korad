#!/usr/bin/env python3
"""Desktop verzia (Linux / macOS / Windows): spustí lokálny server a otvorí UI v natívnom okne.

Vyžaduje: pip install pywebview   (Linux navyše: python3-gi gir1.2-webkit2-4.1 alebo Qt)
Bez pywebview sa otvorí predvolený prehliadač.
"""
import argparse
import socket
import sys
import threading
import webbrowser

import app as korad_app


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default=None)
    ap.add_argument("--port", type=int, default=0, help="port servera (0 = náhodný voľný)")
    ap.add_argument("--browser", action="store_true", help="otvoriť v prehliadači namiesto natívneho okna")
    a = ap.parse_args()
    port = a.port or free_port()
    korad_app.create(a.device)
    t = threading.Thread(
        target=lambda: korad_app.app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False),
        daemon=True,
    )
    t.start()
    url = f"http://127.0.0.1:{port}"
    print("UI:", url)
    if not a.browser:
        try:
            import webview  # pywebview
            webview.create_window("KORAD KA3005P", url, width=1280, height=860, min_size=(900, 600))
            webview.start()
            return
        except ImportError:
            print("pywebview nie je nainštalované (pip install pywebview) – otváram prehliadač.", file=sys.stderr)
    webbrowser.open(url)
    try:
        t.join()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
