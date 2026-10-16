$ErrorActionPreference='Stop'
$taskHostState=Join-Path $env:ProgramData 'CodexStudioHostV2\deployment.json'
if(Test-Path -LiteralPath $taskHostState){$taskState=Get-Content -LiteralPath $taskHostState -Raw | ConvertFrom-Json;if($taskState.AdoptedExistingService){throw 'The device host predates this installer. To preserve its prior state, only Uninstall-Bridge.ps1 is allowed; consult the investigation recovery record for the pre-existing host.'}}
if(Get-Service CodexStudioSoftwareHostV2 -ErrorAction SilentlyContinue){Stop-Service CodexStudioSoftwareHostV2}
if(Get-Service CodexStudioCpuBridge -ErrorAction SilentlyContinue){& (Join-Path $PSScriptRoot 'Uninstall-Bridge.ps1')}
if(Test-Path -LiteralPath $taskHostState){& (Join-Path $PSScriptRoot 'device-host\Uninstall.ps1')}
'Recorded settings restored and services removed. Shared signed driver packages and diagnostic files were preserved.'
