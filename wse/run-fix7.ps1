'=== SwDev5: full params, step1 no parent ===' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix7.log' -Encoding utf8
& 'C:\Users\jianm\Code\DeepseekHarness\wse\SwDev5.exe' - *>> 'C:\Users\jianm\Code\DeepseekHarness\wse\fix7.log'
'--- devices matching MEP/MEPTest ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix7.log' -Append -Encoding utf8
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match 'MEP' } | ForEach-Object { $_.Status + ' | ' + $_.Class + ' | ' + $_.FriendlyName + ' | ' + $_.InstanceId } | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix7.log' -Append -Encoding utf8
'--- SWD\DRIVERENUM ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix7.log' -Append -Encoding utf8
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Enum\SWD\DRIVERENUM' | ForEach-Object { $_.PSChildName } | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix7.log' -Append -Encoding utf8
'DONE' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix7.log' -Append -Encoding utf8
