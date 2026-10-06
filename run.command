#!/bin/sh
# macOS: double-click starts the server and opens the browser (python3 + pip install -r requirements.txt)
cd "$(dirname "$0")" && python3 desktop.py --browser "$@"
