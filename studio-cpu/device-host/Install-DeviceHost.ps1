param([Parameter(Mandatory=$true)][string]$DriverDirectory,[string]$CameraInstanceId)
. (Join-Path $PSScriptRoot 'Studio.Common.ps1')
Assert-StudioAdministrator
$StudioInstallRoot=Join-Path $env:ProgramData 'CodexStudioHostV2'
$StudioStateFile=Join-Path $StudioInstallRoot 'deployment.json'
$taskService='CodexStudioSoftwareHostV2'
$taskDriverSource=(Resolve-Path -LiteralPath $DriverDirectory).Path
$taskManifest=Get-Content (Join-Path $PSScriptRoot 'binaries.json') -Raw | ConvertFrom-Json
foreach($taskBinary in $taskManifest){if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $taskBinary.Name)).Hash -ne $taskBinary.SHA256){throw ('Binary hash mismatch: '+$taskBinary.Name)}}
$taskCameras=@(Get-PnpDevice -PresentOnly -Class Camera | Where-Object {$_.InstanceId -like 'USB\*'})
if(-not $CameraInstanceId){if($taskCameras.Count -ne 1){$taskCameras|Select-Object FriendlyName,InstanceId;throw 'Specify -CameraInstanceId.'};$CameraInstanceId=$taskCameras[0].InstanceId}
if(-not ($taskCameras|Where-Object {$_.InstanceId -ieq $CameraInstanceId})){throw 'Selected USB camera is not present.'}
$taskKeys=@(Get-StudioCameraInterfaces $CameraInstanceId)
if($taskKeys.Count -ne 1){throw 'Expected exactly one VIDEO_CAMERA interface for the selected camera.'}
$taskKey=$taskKeys[0].Substring(6)
$taskOld=Get-CimInstance Win32_Service -Filter "Name='$taskService'"
if($taskOld){
 $taskExpected='"'+(Join-Path $StudioInstallRoot 'StudioSoftwareHost.exe')+'" --service'
 if($taskOld.PathName -ine $taskExpected){throw 'Service name is owned by a different executable.'}
 if((Get-FileHash (Join-Path $StudioInstallRoot 'StudioSoftwareHost.exe')).Hash -ne (Get-FileHash (Join-Path $PSScriptRoot 'StudioSoftwareHost.exe')).Hash){throw 'Different service version is installed; back up and stop it before an explicit upgrade.'}
 $taskIniText=Get-Content (Join-Path $StudioInstallRoot 'StudioHost.ini') -Raw
 if(-not (($taskIniText -split '\r?\n') -contains ('CameraInterfaceKey='+$taskKey))){throw 'The installed service targets a different camera.'}
 if(-not (Test-Path $StudioStateFile)){
  [pscustomobject]@{Status='Installed';AdoptedExistingService=$true;CameraInstanceId=$CameraInstanceId;CameraInterfaceKey=$taskKey;OriginalFSMExisted=$true;OriginalFSM=1;DriverDirectory=$taskDriverSource;BootAtDeployment=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o');RebootVerified=$false;GuiVerified=$false} | ConvertTo-Json | Set-Content $StudioStateFile -Encoding utf8
 }
 Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'CameraDurationProbe.exe'),(Join-Path $PSScriptRoot 'SoftwareMepNode.exe') -Destination $StudioInstallRoot -Force
 & (Join-Path $PSScriptRoot 'Verify.ps1')
 return
}
Initialize-StudioDirectory
$taskOriginal=(Get-ItemProperty -LiteralPath $taskKeys[0] -Name FSMEnableMsEffects -ErrorAction SilentlyContinue).FSMEnableMsEffects
$taskState=[pscustomobject]@{Status='Installing';AdoptedExistingService=$false;CameraInstanceId=$CameraInstanceId;CameraInterfaceKey=$taskKey;OriginalFSMExisted=($null -ne $taskOriginal);OriginalFSM=$taskOriginal;DriverDirectory=$taskDriverSource;BootAtDeployment=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o');RebootVerified=$false;GuiVerified=$false}
$taskState | ConvertTo-Json | Set-Content $StudioStateFile -Encoding utf8
$taskInfFiles=@()
foreach($taskInfName in @('MicrosoftEffectPack.inf','mep_camera_component.inf')){
 $taskMatches=@(Get-ChildItem -LiteralPath $taskDriverSource -Recurse -File -Filter $taskInfName)
 if($taskMatches.Count -ne 1){throw ('Expected one original INF: '+$taskInfName)}
 $taskInfFiles+=$taskMatches[0].FullName
}
foreach($taskInf in $taskInfFiles){
 $taskCat=[IO.Path]::ChangeExtension($taskInf,'.cat')
 if((Get-AuthenticodeSignature -LiteralPath $taskCat).Status -ne 'Valid'){throw 'Original driver catalog signature invalid'}
 & pnputil.exe /add-driver $taskInf
 if($LASTEXITCODE -notin @(0,3010)){throw 'Driver staging failed'}
}
foreach($taskBinary in $taskManifest){Copy-Item -LiteralPath (Join-Path $PSScriptRoot $taskBinary.Name) -Destination $StudioInstallRoot -Force}
[IO.File]::WriteAllText((Join-Path $StudioInstallRoot 'StudioHost.ini'),"[Studio]`r`nCameraInterfaceKey=$taskKey`r`nFailStartupTest=0`r`n",[Text.Encoding]::Unicode)
try {
 New-Service -Name $taskService -DisplayName 'Studio Effects Software Host (research V2)' -BinaryPathName ('"'+(Join-Path $StudioInstallRoot 'StudioSoftwareHost.exe')+'" --service') -StartupType Manual -DependsOn PlugPlay | Out-Null
 Start-Service $taskService
 & sc.exe failure $taskService reset= 86400 actions= restart/1000/restart/5000/none/0
 if($LASTEXITCODE){throw 'Could not configure recovery actions.'}
 & sc.exe failureflag $taskService 1
 if($LASTEXITCODE){throw 'Could not configure failure recovery.'}
 Set-Service $taskService -StartupType Automatic
 $taskState.Status='Installed';$taskState | ConvertTo-Json | Set-Content $StudioStateFile -Encoding utf8
 & (Join-Path $PSScriptRoot 'Verify.ps1')
}catch{
 $taskFailure=$_
 $taskServiceObject=Get-Service $taskService -ErrorAction SilentlyContinue
 if($taskServiceObject){Set-Service $taskService -StartupType Manual;Stop-Service $taskService -ErrorAction SilentlyContinue;& sc.exe delete $taskService | Out-Null}
 $taskMain=Get-PnpDevice -PresentOnly -InstanceId $StudioMainId -ErrorAction SilentlyContinue
 if($taskMain){& (Join-Path $StudioInstallRoot 'SoftwareMepNode.exe') --remove --seconds 0 | Out-Null}
 if($taskState.OriginalFSMExisted){New-ItemProperty -LiteralPath $taskKeys[0] -Name FSMEnableMsEffects -Value $taskState.OriginalFSM -PropertyType DWord -Force | Out-Null}
 else{Remove-ItemProperty -LiteralPath $taskKeys[0] -Name FSMEnableMsEffects -ErrorAction SilentlyContinue}
 $taskLegacy=Get-PnpDevice -InstanceId 'ROOT\MEP_CAM_VEN_8086_DEV_B03E\0000' -PresentOnly -ErrorAction SilentlyContinue
 if($taskLegacy){Enable-PnpDevice -InstanceId $taskLegacy.InstanceId -Confirm:$false}
 $taskState.Status='FailedRolledBack';$taskState | ConvertTo-Json | Set-Content $StudioStateFile -Encoding utf8
 throw $taskFailure
}
