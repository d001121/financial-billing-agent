@echo off
setlocal
cd /d "%~dp0"
call "%~dp0python.cmd" -m langgraph_cli dev --no-browser --no-reload --allow-blocking --host 127.0.0.1 --port 2024 --n-jobs-per-worker 3
exit /b %errorlevel%
