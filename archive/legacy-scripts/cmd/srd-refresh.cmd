# srd-refresh.cmd - copy StateRepository for inspection
@echo off
set SRC=C:\ProgramData\Microsoft\Windows\AppRepository
set DST=C:\Users\jianm\Code\DeepseekHarness\srd-copy2
set LOG=C:\Users\jianm\Code\DeepseekHarness\srd-refresh.log
echo START > "%LOG%"
if not exist "%DST%" mkdir "%DST%"
copy /y "%SRC%\StateRepository-Machine.srd" "%DST%\" >> "%LOG%" 2>&1
copy /y "%SRC%\StateRepository-Machine.srd-wal" "%DST%\" >> "%LOG%" 2>&1
copy /y "%SRC%\StateRepository-Machine.srd-shm" "%DST%\" >> "%LOG%" 2>&1
dir "%DST%" >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
