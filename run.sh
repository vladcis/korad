#!/bin/sh
# Spustí web server; otvor http://127.0.0.1:8585
cd "$(dirname "$0")" && exec python3 app.py "$@"
