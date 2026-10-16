param([string]$CameraInstanceId)
$ErrorActionPreference='Stop'
if(-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required'}
foreach($taskName in @('msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll')){if(-not(Test-Path -LiteralPath (Join-Path "$env:WINDIR\System32" $taskName))){throw 'Install the Microsoft Visual C++ x64 runtime first: https://aka.ms/vs/17/release/vc_redist.x64.exe'}}
$taskPrepared=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'prepared.json') -Raw | ConvertFrom-Json
$taskCurrent=@(Get-CimInstance Win32_Processor | Select-Object Name,ProcessorId,AddressWidth)
if(($taskCurrent | ConvertTo-Json -Compress) -ne (@($taskPrepared.cpu) | ConvertTo-Json -Compress)){throw 'CPU differs from the preparation computer; run Prepare.ps1 on this computer first'}
$taskHadHost=[bool](Get-Service CodexStudioSoftwareHostV2 -ErrorAction SilentlyContinue)
$taskCreatedHost=$false
try{
 if(-not $taskHadHost){& (Join-Path $PSScriptRoot 'device-host\Install-DeviceHost.ps1') -DriverDirectory $taskPrepared.driverDirectory -CameraInstanceId $CameraInstanceId;$taskCreatedHost=$true}
 else{& (Join-Path $PSScriptRoot 'device-host\Verify.ps1')}
 if(-not (Get-Service CodexStudioCpuBridge -ErrorAction SilentlyContinue)){& (Join-Path $PSScriptRoot 'Install-Bridge.ps1')}
 & (Join-Path $env:ProgramData 'CodexStudioCpuBridge\Verify-Bridge.ps1')
}catch{
 $taskFailure=$_
 if($taskCreatedHost){if(Get-Service CodexStudioCpuBridge -ErrorAction SilentlyContinue){& (Join-Path $PSScriptRoot 'Uninstall-Bridge.ps1')};& (Join-Path $PSScriptRoot 'device-host\Uninstall.ps1')}
 throw $taskFailure
}
'Installed. Open Windows Studio Effects and verify framing and blur. Actual reboot verification is still required.'
