@echo off
cd /d %~dp0
C:\Python310\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8080
pause
