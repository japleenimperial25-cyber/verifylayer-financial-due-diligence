@echo off
setlocal
cd /d "%~dp0"
start "VerifyLayer HTTPS server" "C:\Users\kaurj\AppData\Local\Programs\Python\Python312\python.exe" website.py
timeout /t 2 /nobreak >nul
start "" "https://localhost:8443"
