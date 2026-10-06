#!/usr/bin/env python3
"""Builds a standalone app with PyInstaller (run separately on each OS).

    pip install -r requirements.txt pyinstaller pywebview
    python build.py              -> dist/korad  (Linux), dist/korad.exe (Windows), dist/korad.app + dist/korad (macOS)
    python build.py --onedir     -> dist/korad/ directory (used for the Linux AppImage)
"""
import os
import sys

import PyInstaller.__main__

sep = os.pathsep
onedir = "--onedir" in sys.argv[1:]
args = [
    "desktop.py",
    "--name", "korad",
    "--onedir" if onedir else "--onefile",
    "--clean",
    "--noconfirm",
    f"--add-data=static{sep}static",
    f"--add-data=scripts{sep}scripts",
    "--collect-submodules", "serial",
]
try:
    import webview  # noqa: F401
    args += ["--collect-all", "webview"]
    has_webview = True
except ImportError:
    has_webview = False
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  Qt backend of pywebview (Linux AppImage)
    # qtpy imports the binding at runtime, PyInstaller would not see it
    for m in ("sip", "QtCore", "QtGui", "QtWidgets", "QtNetwork", "QtWebChannel",
              "QtWebEngineCore", "QtWebEngineWidgets"):
        args += ["--hidden-import", f"PyQt6.{m}"]
except ImportError:
    pass

if sys.platform in ("win32", "darwin") and has_webview:
    args.append("--windowed")        # no console; output goes to logs/app.log
if sys.platform == "darwin":
    args += ["--osx-bundle-identifier", "sk.korad.psu"]

print("PyInstaller:", " ".join(args))
PyInstaller.__main__.run(args)
