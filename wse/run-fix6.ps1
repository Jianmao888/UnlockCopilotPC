& 'C:\Users\jianm\Code\DeepseekHarness\wse\SwDev4.exe' *> 'C:\Users\jianm\Code\DeepseekHarness\wse\fix6.log'
'--- devices matching MEP after ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix6.log' -Append -Encoding utf8
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match 'MEP' } | ForEach-Object { $_.Status + ' | ' + $_.Class + ' | ' + $_.FriendlyName + ' | ' + $_.InstanceId } | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix6.log' -Append -Encoding utf8
'--- SWD\DRIVERENUM tail ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix6.log' -Append -Encoding utf8
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Enum\SWD\DRIVERENUM' | ForEach-Object { $_.PSChildName } | Select-Object -Last 6 | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix6.log' -Append -Encoding utf8
'DONE' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fix6.log' -Append -Encoding utf8
