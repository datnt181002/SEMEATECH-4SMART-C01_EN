@echo off
setlocal
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --windowed --name "4SMART-C01-Sensor-Utility" main.py
echo.
echo Build complete: dist\4SMART-C01-Sensor-Utility\4SMART-C01-Sensor-Utility.exe

