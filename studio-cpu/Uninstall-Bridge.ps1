$ErrorActionPreference='Stop'
if(-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required'}
$taskRoot=$PSScriptRoot;if(-not(Test-Path -LiteralPath (Join-Path $taskRoot 'deployment.json'))){$taskRoot=Join-Path $env:ProgramData 'CodexStudioCpuBridge'}
$taskState=Get-Content -LiteralPath (Join-Path $taskRoot 'deployment.json') -Raw | ConvertFrom-Json
$taskDeps=@($taskState.hostPreviousDependencies)
& sc.exe config CodexStudioSoftwareHostV2 depend= $(if($taskDeps.Count){$taskDeps -join '/'}else{'/'}) | Out-Null;if($LASTEXITCODE){throw 'Could not restore device-host dependencies'}
if(Get-Service CodexStudioCpuBridge -ErrorAction SilentlyContinue){Set-Service CodexStudioCpuBridge -StartupType Disabled;Stop-Service CodexStudioCpuBridge;& sc.exe delete CodexStudioCpuBridge | Out-Null;if($LASTEXITCODE){throw 'Service removal failed'}}
$taskState.status='Uninstalled';$taskState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskRoot 'deployment.json') -Encoding utf8
'CPU bridge removed; original service dependencies restored. Device-tree service, signed drivers, models and diagnostic files are preserved. Enabled effects require a CPU bridge or supported NPU to run.'
