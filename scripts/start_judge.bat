@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_judge.ps1" %*
exit /b %ERRORLEVEL%
