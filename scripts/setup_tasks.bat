@echo off
REM ===== Setup Agentest Scheduled Tasks =====
REM Right-click this file and select "Run as Administrator"

set WRAPPER=C:\Users\HP\PycharmProjects\GenAI\agentest\scripts\_run_weekday.ps1

:: Clean old tasks
schtasks /DELETE /TN "Agentest-LongTerm-Morning" /F 2>nul
schtasks /DELETE /TN "Agentest-LongTerm-Afternoon" /F 2>nul
schtasks /DELETE /TN "Agentest-BTST-Daily" /F 2>nul

:: Create as SYSTEM (no password, works when locked)
schtasks /CREATE /SC DAILY /TN "Agentest-LongTerm-Morning" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File %WRAPPER% scripts/run_daily.py" /ST 10:15 /F /RU "NT AUTHORITY\SYSTEM" /RL HIGHEST
if %ERRORLEVEL%==0 (echo [OK] Agentest-LongTerm-Morning @ 10:15) else (echo [FAIL] Agentest-LongTerm-Morning)

schtasks /CREATE /SC DAILY /TN "Agentest-LongTerm-Afternoon" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File %WRAPPER% scripts/run_daily.py" /ST 15:15 /F /RU "NT AUTHORITY\SYSTEM" /RL HIGHEST
if %ERRORLEVEL%==0 (echo [OK] Agentest-LongTerm-Afternoon @ 15:15) else (echo [FAIL] Agentest-LongTerm-Afternoon)

schtasks /CREATE /SC DAILY /TN "Agentest-BTST-Daily" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File %WRAPPER% scripts/run_daily.py --btst-backtest" /ST 15:20 /F /RU "NT AUTHORITY\SYSTEM" /RL HIGHEST
if %ERRORLEVEL%==0 (echo [OK] Agentest-BTST-Daily @ 15:20) else (echo [FAIL] Agentest-BTST-Daily)

echo.
echo Done! All tasks run as SYSTEM (works even when PC is locked).
echo Tasks run Mon-Fri only (enforced by _run_weekday.ps1).
echo.
pause
