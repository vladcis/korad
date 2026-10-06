@echo off
rem Run from source on Windows: python 3.10+ and "pip install -r requirements.txt"
cd /d "%~dp0"
python desktop.py --browser %*
pause
