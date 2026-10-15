@echo off
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install torch==2.14.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu126
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -c constraints-windows.txt -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import tkinter, torch, torchaudio, soundfile, triton; from voxcpm import VoxCPM; print('Dependency imports passed; no model loaded.')"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip freeze > ".venv\installed-packages.txt"
if errorlevel 1 goto failed
echo Setup complete. Run start.cmd.
pause
exit /b 0
:failed
echo Setup failed. Install Python 3.12 with the Python launcher, then retry. See README.md.
pause
exit /b 1
