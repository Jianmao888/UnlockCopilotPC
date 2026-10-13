@echo off
set LOG=C:\Users\jianm\Code\DeepseekHarness\trigger-orch.log
echo ==== restart orchestrator services ==== > "%LOG%"
for %%S in (UsoSvc wuauserv WSAIFabricSvc) do (
  echo. >> "%LOG%"
  echo [stop] %%S >> "%LOG%"
  net stop %%S >> "%LOG%" 2>&1
)
timeout /t 5 /nobreak > nul
for %%S in (WSAIFabricSvc wuauserv UsoSvc) do (
  echo. >> "%LOG%"
  echo [start] %%S >> "%LOG%"
  net start %%S >> "%LOG%" 2>&1
)
echo. >> "%LOG%"
echo [state] >> "%LOG%"
sc query UsoSvc >> "%LOG%" 2>&1
sc query wuauserv >> "%LOG%" 2>&1
sc query WSAIFabricSvc >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
