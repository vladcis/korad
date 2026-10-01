#!/bin/sh
# macOS: dvojklik spustí server a otvorí prehliadač (python3 + pip install -r requirements.txt)
cd "$(dirname "$0")" && python3 desktop.py --browser "$@"
