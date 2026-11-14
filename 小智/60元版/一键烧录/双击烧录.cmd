@echo off
setlocal
set "PSModulePath="
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Flash-Xmini-C3.ps1"
set "FLASH_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %FLASH_EXIT%
