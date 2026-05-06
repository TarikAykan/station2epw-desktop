@echo off
REM Station2EPW Desktop — PyInstaller ile tek dosya EXE
REM Önce: pip install pyinstaller && pip install -r requirements.txt

cd /d "%~dp0"
pyinstaller --noconfirm --onefile --windowed --name Station2EPW main.py
