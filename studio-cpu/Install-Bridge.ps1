param([string]$InstallRoot=(Join-Path $env:ProgramData 'CodexStudioCpuBridge'))
$ErrorActionPreference='Stop'
if(-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required'}
if(-not [Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64'){throw 'Only Windows x64 is supported'}
if(Get-Service CodexStudioCpuBridge -ErrorAction SilentlyContinue){throw 'CPU bridge already exists; use the installed management scripts'}
if(Test-Path -LiteralPath $InstallRoot){throw 'Target already exists; preserve it and choose a fresh directory'}
$taskPayload=Join-Path $PSScriptRoot 'payload';$taskManifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'payload-sha256.json') -Raw | ConvertFrom-Json
foreach($taskItem in $taskManifest){if((Get-FileHash -LiteralPath (Join-Path $taskPayload $taskItem.path)).Hash -ine $taskItem.sha256){throw ('Payload hash mismatch: '+$taskItem.path)}}
$taskStore=Join-Path $env:WINDIR 'System32\DriverStore\FileRepository'
$taskDriver=@(Get-ChildItem -Path (Join-Path $taskStore 'microsofteffectpack.inf_amd64_*') -Directory | Where-Object {Test-Path -LiteralPath (Join-Path $_.FullName 'ps-onnxruntime.dll')} | Where-Object {(Get-FileHash -LiteralPath (Join-Path $_.FullName 'PerceptionCore.dll')).Hash -eq '374F9DDCF450B063F98F81B7ACDDD1C94F8977A525B4D82504E7779B44AAD4F9'})
$taskCamera=@(Get-ChildItem -Path (Join-Path $taskStore 'mep_camera_component.inf_amd64_*') -Directory | Where-Object {Test-Path -LiteralPath (Join-Path $_.FullName 'WindowsEffectsCameraMediaSource.dll')} | Where-Object {(Get-FileHash -LiteralPath (Join-Path $_.FullName 'WindowsEffectsCameraMediaSource.dll')).Hash -eq '54D842610391F15602E5C68C4AF3A2D9A1372F2344800EEB30A767567386BC66'})
if($taskDriver.Count -ne 1 -or $taskCamera.Count -ne 1){throw 'Exactly one supported engine and camera package must be staged first'}
$taskHost=Get-CimInstance Win32_Service -Filter "Name='CodexStudioSoftwareHostV2'"
if(-not $taskHost){throw 'Install the V2 software-device host first'}
$taskDeps=@((Get-Service CodexStudioSoftwareHostV2).ServicesDependedOn.Name)
New-Item -ItemType Directory -Path $InstallRoot | Out-Null
$taskAcl=New-Object Security.AccessControl.DirectorySecurity;$taskAcl.SetAccessRuleProtection($true,$false)
foreach($taskPair in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@('S-1-5-32-545','ReadAndExecute'),@('S-1-5-19','ReadAndExecute'))){$taskSid=New-Object Security.Principal.SecurityIdentifier($taskPair[0]);$taskAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($taskSid,$taskPair[1],'ContainerInherit,ObjectInherit','None','Allow')))}
Set-Acl -LiteralPath $InstallRoot -AclObject $taskAcl
Copy-Item -Path (Join-Path $taskPayload '*') -Destination $InstallRoot -Recurse
$taskProfile=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'profile-template.json') -Raw | ConvertFrom-Json
$taskProfile.driverDirectory=$taskDriver[0].FullName;$taskProfile.cameraDirectory=$taskCamera[0].FullName;$taskProfile.runtimeDirectory=Join-Path $InstallRoot 'cpu-runtime'
foreach($taskModel in $taskProfile.models){$taskModel.path=Join-Path $taskProfile.runtimeDirectory $taskModel.file}
$taskExpected=@{'PerceptionCore.dll'='374f9ddcf450b063f98f81b7acddd1c94f8977a525b4d82504e7779b44aad4f9';'PerceptionCoreResources.dll'='9c988e751d0aebb85fc75dce3f252ac32da23c408ac6bf73773d8431b64eccaa';'ps-onnxruntime.dll'='2bee89d82184edeeb2e7ea6dea43e44d5759d27d2298b39bfcf42c0a5232e9e8'}
$taskFiles=@();foreach($taskName in @('PerceptionCore.dll','PerceptionCoreResources.dll','ps-onnxruntime.dll','openvino.dll')){$taskPath=Join-Path $taskDriver[0].FullName $taskName;$taskDigest=(Get-FileHash -LiteralPath $taskPath).Hash.ToLowerInvariant();if($taskExpected.ContainsKey($taskName) -and $taskDigest -ne $taskExpected[$taskName]){throw ('Unsupported driver binary: '+$taskName)};$taskFiles+=[pscustomobject]@{path=$taskPath;sha256=$taskDigest}}
$taskProfile.driverFiles=$taskFiles
$taskProfile | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $InstallRoot 'profile.json') -Encoding utf8
$taskState=[pscustomobject]@{status='Installing';root=$InstallRoot;hostPreviousDependencies=$taskDeps;boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o');rebootVerified=$false;installed=(Get-Date).ToString('o')}
$taskState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $InstallRoot 'deployment.json') -Encoding utf8
foreach($taskFile in @('Uninstall-Bridge.ps1','Verify-Bridge.ps1')){Copy-Item -LiteralPath (Join-Path $PSScriptRoot $taskFile) -Destination $InstallRoot}
try{
 New-Service -Name CodexStudioCpuBridge -DisplayName 'Studio Effects CPU Bridge (research)' -BinaryPathName ('"'+(Join-Path $InstallRoot 'StudioCpuService.exe')+'" --service') -StartupType Manual -DependsOn PlugPlay,RpcSs | Out-Null
 Start-Service CodexStudioCpuBridge
 & sc.exe failure CodexStudioCpuBridge reset= 86400 actions= restart/2000/restart/5000/restart/30000 | Out-Null;if($LASTEXITCODE){throw 'Recovery setup failed'}
 & sc.exe failureflag CodexStudioCpuBridge 1 | Out-Null;if($LASTEXITCODE){throw 'Recovery flag setup failed'}
 Set-Service CodexStudioCpuBridge -StartupType Automatic
 $taskNewDeps=@($taskDeps+'CodexStudioCpuBridge'|Select-Object -Unique)
 & sc.exe config CodexStudioSoftwareHostV2 depend= ($taskNewDeps -join '/') | Out-Null;if($LASTEXITCODE){throw 'Device-host dependency setup failed'}
 $taskState.status='Installed';$taskState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $InstallRoot 'deployment.json') -Encoding utf8
 & (Join-Path $InstallRoot 'Verify-Bridge.ps1')
}catch{
 $taskFailure=$_
 & sc.exe config CodexStudioSoftwareHostV2 depend= $(if($taskDeps.Count){$taskDeps -join '/'}else{'/'}) | Out-Null
 if(Get-Service CodexStudioCpuBridge -ErrorAction SilentlyContinue){Stop-Service CodexStudioCpuBridge -ErrorAction SilentlyContinue;& sc.exe delete CodexStudioCpuBridge | Out-Null}
 $taskState.status='FailedRolledBack';$taskState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $InstallRoot 'deployment.json') -Encoding utf8
 throw $taskFailure
}
