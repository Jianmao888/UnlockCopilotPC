Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-MF-FrameServer/Camera_FrameServer'; StartTime=(Get-Date).AddMinutes(-3)} -ErrorAction SilentlyContinue |
  Sort-Object TimeCreated | Where-Object { $_.Id -eq 7 -or $_.Id -eq 6 } | Select-Object -Last 12 |
  ForEach-Object { '{0} id={1} {2}' -f $_.TimeCreated.ToString('HH:mm:ss'), $_.Id, (($_.Message -replace "`r`n",' ') -replace '\s+',' ') } |
  Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fs-after.log' -Encoding utf8
'--- Application errors last 3 min ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fs-after.log' -Append -Encoding utf8
Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=(Get-Date).AddMinutes(-3); Level=1,2,3} -ErrorAction SilentlyContinue |
  Select-Object -First 8 | ForEach-Object { '{0} {1} id={2} {3}' -f $_.TimeCreated.ToString('HH:mm:ss'), $_.ProviderName, $_.Id, ((($_.Message -replace "`r`n",' ') -replace '\s+',' ')).Substring(0,[Math]::Min(200,$_.Message.Length)) } |
  Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fs-after.log' -Append -Encoding utf8
'DONE' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\fs-after.log' -Append -Encoding utf8
