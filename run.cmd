@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Missing .venv. Run: uv venv --python 3.14 .venv
    echo Then: uv pip install --python .venv/Scripts/python.exe -e ".[dev,build]"
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "app\main.py"
