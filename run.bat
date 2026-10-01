@echo off
rem Spustenie zo zdrojakov na Windows: python 3.10+ a "pip install -r requirements.txt"
cd /d "%~dp0"
python desktop.py --browser %*
pause
