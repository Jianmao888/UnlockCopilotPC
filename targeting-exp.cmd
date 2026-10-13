@echo off
set LOG=C:\Users\jianm\Code\DeepseekHarness\targeting-exp.log
set TI=HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo
set BAK=C:\Users\jianm\Code\DeepseekHarness\targeting-backup

echo ==== TargetingInfo experiment ==== > "%LOG%"
if not exist "%BAK%" mkdir "%BAK%"
echo. >> "%LOG%"
echo [0] BACKUP >> "%LOG%"
reg export "%TI%" "%BAK%\TargetingInfo-before.reg" /y >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo [1] BEFORE - DynamicInstalled >> "%LOG%"
reg query "%TI%\DynamicInstalled" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo [2] ADD product keys >> "%LOG%"
reg add "%TI%\DynamicInstalled\Windows.Workload.ContentExtraction.amd64" /v Version /t REG_SZ /d "0.0.0.0" /f >> "%LOG%" 2>&1
reg add "%TI%\DynamicInstalled\Windows.Workload.Analysis.amd64" /v Version /t REG_SZ /d "0.0.0.0" /f >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo [3] AFTER - DynamicInstalled >> "%LOG%"
reg query "%TI%\DynamicInstalled" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo [4] RESTART wuauserv >> "%LOG%"
net stop wuauserv >> "%LOG%" 2>&1
timeout /t 3 /nobreak > nul
net start wuauserv >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
type "%LOG%"
