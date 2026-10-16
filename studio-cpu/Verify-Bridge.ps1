param([switch]$RecordFiveSeconds,[string]$CameraMatch)
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
if(-not (Test-Path -LiteralPath (Join-Path $taskRoot 'profile.json'))){$taskRoot=Join-Path $env:ProgramData 'CodexStudioCpuBridge'}
$taskStatus=Get-Content -LiteralPath (Join-Path $taskRoot 'status.json') -Raw | ConvertFrom-Json
$taskService=Get-CimInstance Win32_Service -Filter "Name='CodexStudioCpuBridge'"
if(-not $taskService -or $taskService.State -ne 'Running' -or -not $taskStatus.active -or [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-[double]$taskStatus.time -gt 10){throw 'Bridge is not running and recently attached'}
$taskProcess=Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$taskStatus.worker_pid)
if(-not $taskProcess -or $taskProcess.ExecutablePath -ine (Join-Path $taskRoot 'python\python.exe')){throw 'Worker does not use the installed private Python'}
if($RecordFiveSeconds){
 if(-not $CameraMatch){$taskDeviceState=Get-Content -LiteralPath (Join-Path $env:ProgramData 'CodexStudioHostV2\deployment.json') -Raw | ConvertFrom-Json;$CameraMatch=$taskDeviceState.CameraInstanceId.Replace('\','#').ToLowerInvariant()}
 $taskOutput=Join-Path $taskRoot ('verify-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.mp4')
 & (Join-Path $taskRoot 'CameraDurationProbe.exe') --seconds 5 --match $CameraMatch --output $taskOutput
 if($LASTEXITCODE){throw 'Five-second capture failed'}
 Start-Sleep -Milliseconds 1100
 $taskStatus=Get-Content -LiteralPath (Join-Path $taskRoot 'status.json') -Raw | ConvertFrom-Json
}
[pscustomobject]@{Service=$taskService.Name;State=$taskService.State;Worker=$taskStatus.worker_pid;FrameServer=$taskStatus.service_pid;AutomaticCameraCapture=$taskStatus.automatic_camera_capture;Counts=$taskStatus.inference_counts;Errors=$taskStatus.error_events;RebootVerified=(Get-Content -LiteralPath (Join-Path $taskRoot 'deployment.json') -Raw | ConvertFrom-Json).rebootVerified} | ConvertTo-Json -Depth 5
