$ErrorActionPreference='Stop'
if(-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required'}
$taskRoot=Join-Path $env:ProgramData 'CodexStudioCpuBridge'
$taskManifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'payload-sha256.json') -Raw | ConvertFrom-Json
$taskFiles=@($taskManifest | Where-Object path -like 'cpu-runtime/*-cpu-context.onnx')
if($taskFiles.Count -ne 4){throw 'Exactly four prepared models required'}
foreach($taskItem in $taskFiles){if((Get-FileHash -LiteralPath (Join-Path (Join-Path $PSScriptRoot 'payload') $taskItem.path)).Hash -ine $taskItem.sha256){throw 'Prepared model digest mismatch'}}
$taskBackup=Join-Path $taskRoot ('model-backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss'));New-Item -ItemType Directory -Path $taskBackup | Out-Null
Stop-Service CodexStudioSoftwareHostV2;Stop-Service CodexStudioCpuBridge
try{
 foreach($taskItem in $taskFiles){$taskName=Split-Path $taskItem.path -Leaf;Copy-Item -LiteralPath (Join-Path $taskRoot $taskItem.path) -Destination (Join-Path $taskBackup $taskName);Copy-Item -LiteralPath (Join-Path (Join-Path $PSScriptRoot 'payload') $taskItem.path) -Destination (Join-Path $taskRoot $taskItem.path) -Force}
 Stop-Service FrameServer -ErrorAction SilentlyContinue
 Start-Service CodexStudioCpuBridge;Start-Service CodexStudioSoftwareHostV2
 & (Join-Path $taskRoot 'Verify-Bridge.ps1') -RecordFiveSeconds
}catch{
 $taskFailure=$_;Stop-Service CodexStudioSoftwareHostV2 -ErrorAction SilentlyContinue;Stop-Service CodexStudioCpuBridge -ErrorAction SilentlyContinue
 foreach($taskItem in $taskFiles){$taskName=Split-Path $taskItem.path -Leaf;if(Test-Path -LiteralPath (Join-Path $taskBackup $taskName)){Copy-Item -LiteralPath (Join-Path $taskBackup $taskName) -Destination (Join-Path $taskRoot $taskItem.path) -Force}}
 Stop-Service FrameServer -ErrorAction SilentlyContinue;Start-Service CodexStudioCpuBridge;Start-Service CodexStudioSoftwareHostV2;throw $taskFailure
}
