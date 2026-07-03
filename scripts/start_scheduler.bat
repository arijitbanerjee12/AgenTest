@echo off
REM Start Agentest Scheduler (starts background timer, hidden window)
start /B powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\HP\PycharmProjects\GenAI\agentest\scripts\AgentestScheduler.ps1"
echo Started. Scheduler runs in background, checks time every 10s.
echo See logs at: scripts\scheduler.log
