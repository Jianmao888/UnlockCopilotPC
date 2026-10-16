param([switch]$GuiVerified)
$ErrorActionPreference='Stop'
$taskRoot=Join-Path $env:ProgramData 'CodexStudioCpuBridge';$taskFile=Join-Path $taskRoot 'deployment.json';$taskState=Get-Content -LiteralPath $taskFile -Raw | ConvertFrom-Json
$taskBoot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime()
$taskInstalledBoot=([datetime]$taskState.boot).ToUniversalTime()
if($taskBoot -le $taskInstalledBoot){throw 'No later actual boot since installation; cannot mark reboot verified'}
& (Join-Path $taskRoot 'Verify-Bridge.ps1') -RecordFiveSeconds
$taskDevice=Get-Content -LiteralPath (Join-Path $env:ProgramData 'CodexStudioHostV2\status.json') -Raw | ConvertFrom-Json
if(-not $taskDevice.active -or (Get-Service CodexStudioSoftwareHostV2).Status -ne 'Running'){throw 'Device host not healthy after reboot'}
$taskState.rebootVerified=$true;$taskState | Add-Member -NotePropertyName guiAfterRebootVerified -NotePropertyValue ([bool]$GuiVerified) -Force;$taskState | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $taskFile -Encoding utf8
'Actual reboot and five-second capture verified. GUI confirmation: '+[bool]$GuiVerified
