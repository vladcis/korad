#!/usr/bin/env python3
"""Builds a standalone app with PyInstaller (run separately on each OS).

    pip install -r requirements.txt pyinstaller pywebview
    python build.py              -> dist/korad  (Linux), dist/korad.exe (Windows), dist/korad.app + dist/korad (macOS)
"""
import os
import sys

import PyInstaller.__main__

sep = os.pathsep
args = [
    "desktop.py",
    "--name", "korad",
    "--onefile",
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

if sys.platform in ("win32", "darwin") and has_webview:
    args.append("--windowed")        # no console; output goes to logs/app.log
if sys.platform == "darwin":
    args += ["--osx-bundle-identifier", "sk.korad.psu"]

print("PyInstaller:", " ".join(args))
PyInstaller.__main__.run(args)
