@echo off
set LOG=C:\Users\jianm\Code\DeepseekHarness\restore.log
set KEY=HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsAI\LastConfiguration
echo ==== RESTORE HardwareCompatibility to 0 ==== > "%LOG%"
reg add "%KEY%" /v HardwareCompatibility /t REG_DWORD /d 0 /f >> "%LOG%" 2>&1
echo. >> "%LOG%"
reg query "%KEY%" >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
type "%LOG%"
