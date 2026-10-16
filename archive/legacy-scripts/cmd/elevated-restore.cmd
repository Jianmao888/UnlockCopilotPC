@echo off
set LOG=C:\Users\jianm\Code\DeepseekHarness\elevated-restore.log
echo ==== RESTORE ==== > "%LOG%"
echo [1] reset winhttp proxy >> "%LOG%"
netsh winhttp reset proxy >> "%LOG%" 2>&1
echo [2] remove machine CA >> "%LOG%"
certutil -delstore Root "DSH WU Capture CA" >> "%LOG%" 2>&1
echo [3] show >> "%LOG%"
netsh winhttp show proxy >> "%LOG%" 2>&1
certutil -store Root "DSH WU Capture CA" >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
type "%LOG%"
