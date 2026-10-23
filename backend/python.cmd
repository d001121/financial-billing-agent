@echo off
setlocal
set "PYTHONHOME="
set "PYTHONPATH="
"%~dp0bishi1\python.exe" %*
exit /b %errorlevel%
