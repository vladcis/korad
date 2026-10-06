#!/bin/sh
# Starts the web server; open http://127.0.0.1:8585
cd "$(dirname "$0")" && exec python3 app.py "$@"
