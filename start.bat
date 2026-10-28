@echo off
chcp 65001 >nul
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
start "" http://127.0.0.1:8000
.venv\Scripts\python -m tanakh_explorer serve
goto :eof
:err
echo Setup failed. See the messages above.
pause
