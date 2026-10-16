pnputil /restart-device "ROOT\MEP_VEN_8086_DEV_B03E\0000" | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix4.log' -Encoding utf8
Start-Sleep 5
'--- SWD\DRIVERENUM MEP entries ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix4.log' -Append -Encoding utf8
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Enum\SWD\DRIVERENUM' | Where-Object { $_.PSChildName -match '(?i)mep' } | ForEach-Object { $_.PSChildName } | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix4.log' -Append -Encoding utf8
'--- run SwDev2 (software device creation, parent = computer) ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix4.log' -Append -Encoding utf8
& 'C:\Users\jianm\Code\DeepseekHarness\wse\SwDev2.exe' 'SWD\COMPUTER\MFG_TIMI&FAM_Mi_Laptop&PROD_Xiaomi_Book_Pro_16_2022&SKU_TM2121-40435' *>> 'C:\Users\jianm\Code\DeepseekHarness\wse\fix4.log'
'--- after: SWD\DRIVERENUM entries ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix4.log' -Append -Encoding utf8
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Enum\SWD\DRIVERENUM' | ForEach-Object { $_.PSChildName } | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix4.log' -Append -Encoding utf8
'--- devices matching MEP ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix4.log' -Append -Encoding utf8
Get-PnpDevice | Where-Object { $_.InstanceId -match 'MEP' } | ForEach-Object { $_.Status + ' ' + $_.Class + ' ' + $_.InstanceId } | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix4.log' -Append -Encoding utf8
'DONE' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix4.log' -Append -Encoding utf8
