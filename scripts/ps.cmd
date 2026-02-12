@echo off
where pwsh >nul 2>nul
if %ERRORLEVEL%==0 (
  pwsh -NoProfile %*
) else (
  powershell.exe -NoProfile %*
)
exit /b %ERRORLEVEL%
