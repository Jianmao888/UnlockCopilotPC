@echo off
set CA=C:\Users\jianm\Code\DeepseekHarness\mitm-ca\ca.crt
set LOG=C:\Users\jianm\Code\DeepseekHarness\elevated-setup.log
echo ==== SETUP ==== > "%LOG%"
echo [1] install machine CA >> "%LOG%"
certutil -f -addstore Root "%CA%" >> "%LOG%" 2>&1
echo [2] set winhttp proxy >> "%LOG%"
netsh winhttp set proxy 127.0.0.1:8899 >> "%LOG%" 2>&1
echo [3] show >> "%LOG%"
netsh winhttp show proxy >> "%LOG%" 2>&1
echo [4] verify CA in LocalMachine\Root >> "%LOG%"
certutil -store Root "DSH WU Capture CA" >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
type "%LOG%"
