@echo off
echo Creating virtual environment...
python -m venv .venv

echo Installing dependencies...
call .venv\Scripts\pip.exe install -r requirements.txt

echo Setup complete.
pause
