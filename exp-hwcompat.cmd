@echo off
set LOG=C:\Users\jianm\Code\DeepseekHarness\exp-hwcompat.log
set KEY=HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsAI\LastConfiguration
echo ==== EXPERIMENT: force HardwareCompatibility=1 + restart wuauserv ==== > "%LOG%"
echo. >> "%LOG%"
echo [1] BEFORE >> "%LOG%"
reg query "%KEY%" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo [2] SET HardwareCompatibility=1 >> "%LOG%"
reg add "%KEY%" /v HardwareCompatibility /t REG_DWORD /d 1 /f >> "%LOG%" 2>&1
reg query "%KEY%" /v HardwareCompatibility >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo [3] RESTART wuauserv >> "%LOG%"
net stop wuauserv >> "%LOG%" 2>&1
timeout /t 3 /nobreak > nul
net start wuauserv >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo [4] SERVICE STATE >> "%LOG%"
sc query wuauserv >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo [5] AFTER (immediately) >> "%LOG%"
reg query "%KEY%" >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
type "%LOG%"
