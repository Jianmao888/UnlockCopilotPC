@echo off
set LOG=C:\Users\jianm\Code\DeepseekHarness\targeting-cleanup.log
set TI=HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo
echo ==== cleanup targeting test keys ==== > "%LOG%"
reg delete "%TI%\DynamicInstalled\Windows.Workload.ContentExtraction.amd64" /f >> "%LOG%" 2>&1
reg delete "%TI%\DynamicInstalled\Windows.Workload.Analysis.amd64" /f >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo [verify] DynamicInstalled 剩余项 >> "%LOG%"
reg query "%TI%\DynamicInstalled" >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
type "%LOG%"
