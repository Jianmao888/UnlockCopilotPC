'=== SwDev3 with cfgmgr32, parent = computer ===' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix5.log' -Encoding utf8
& 'C:\Users\jianm\Code\DeepseekHarness\wse\SwDev3.exe' 'SWD\COMPUTER\MFG_TIMI&FAM_Mi_Laptop&PROD_Xiaomi_Book_Pro_16_2022&SKU_TM2121-40435' *>> 'C:\Users\jianm\Code\DeepseekHarness\wse\fix5.log'
'--- SWD\DRIVERENUM after ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix5.log' -Append -Encoding utf8
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Enum\SWD\DRIVERENUM' | ForEach-Object { $_.PSChildName } | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix5.log' -Append -Encoding utf8
'--- devices matching MEP ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix5.log' -Append -Encoding utf8
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match 'MEP' } | ForEach-Object { $_.Status + ' | ' + $_.Class + ' | ' + $_.InstanceId } | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix5.log' -Append -Encoding utf8
'DONE' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix5.log' -Append -Encoding utf8
