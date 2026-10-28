@echo off
chcp 65001 >nul
title Tanakh Explorer
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Creating virtual environment...
  python -m venv .venv || goto :err
  .venv\Scripts\python -m pip install -q -r requirements.txt || goto :err
)
if not exist data\build\corpus.pkl (
  echo First run: downloading and validating the Tanakh...
  .venv\Scripts\python -m tanakh_explorer setup || goto :err
)
echo Tanakh Explorer is running at http://127.0.0.1:8000  -  close this window to stop it.
.venv\Scripts\python -m tanakh_explorer serve --open
goto :eof
:err
echo Setup failed. See the messages above.
pause
