Get-WinEvent -LogName 'Microsoft-Windows-MF-FrameServer/Camera_FrameServer' -MaxEvents 40 -ErrorAction SilentlyContinue |
  ForEach-Object { '{0} [{1}] id={2} {3}' -f $_.TimeCreated, $_.LevelDisplayName, $_.Id, ((($_.Message -replace "`r`n",' ') -replace '\s+',' ')) } | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\frameserver.log' -Encoding utf8
'--- DeviceMFT ---' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\frameserver.log' -Append -Encoding utf8
Get-WinEvent -LogName 'Microsoft-Windows-MF-FrameServer/Camera_DeviceMFT' -MaxEvents 40 -ErrorAction SilentlyContinue |
  ForEach-Object { '{0} [{1}] id={2} {3}' -f $_.TimeCreated, $_.LevelDisplayName, $_.Id, ((($_.Message -replace "`r`n",' ') -replace '\s+',' ')) } | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\frameserver.log' -Append -Encoding utf8
'DONE' | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wse\frameserver.log' -Append -Encoding utf8
