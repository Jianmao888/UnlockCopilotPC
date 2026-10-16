@echo off
cd /d C:\Users\jianm\Code\DeepseekHarness
set PY=C:\Users\jianm\AppData\Local\Programs\Python\Python312\python.exe
echo [run] python=%PY% > hook-log.txt
"%PY%" --version >> hook-log.txt 2>&1
"%PY%" hook_wu_svc.py >> hook-log.txt 2>&1
echo EXIT=%ERRORLEVEL% >> hook-log.txt
