@echo off
set SRC=C:\ProgramData\Microsoft\Windows\AppRepository
set DST=C:\Users\jianm\Code\DeepseekHarness\srd-copy
set LOG=C:\Users\jianm\Code\DeepseekHarness\srd-probe.log
echo BATCH STARTED > "%LOG%"
echo [1] DIR >> "%LOG%"
dir "%SRC%" >> "%LOG%" 2>&1
if not exist "%DST%" mkdir "%DST%"
echo [2] COPY >> "%LOG%"
copy /y "%SRC%\*.srd" "%DST%\" >> "%LOG%" 2>&1
echo [3] LIST COPY >> "%LOG%"
dir "%DST%" >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
