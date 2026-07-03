Set Shell = CreateObject("WScript.Shell")
Shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\Users\HP\PycharmProjects\GenAI\agentest\scripts\AgentestScheduler.ps1", 0, False
