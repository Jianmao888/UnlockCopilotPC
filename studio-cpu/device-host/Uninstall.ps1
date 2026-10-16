. (Join-Path $PSScriptRoot 'Studio.Common.ps1')
Assert-StudioAdministrator
$taskStage=Join-Path $env:ProgramData 'CodexStudioHostV2'
$taskStateFile=Join-Path $taskStage 'deployment.json'
$taskState=Get-Content $taskStateFile -Raw | ConvertFrom-Json
if($taskState.AdoptedExistingService){throw 'This service was adopted from the investigation. Use work/studio-effects-investigation/Restore-StudioHostV2.ps1 to restore the verified root-plus-hook setup.'}
$taskSvc=Get-Service -Name CodexStudioSoftwareHostV2 -ErrorAction SilentlyContinue
if($taskSvc){Set-Service $taskSvc.Name -StartupType Manual;Stop-Service $taskSvc.Name;& sc.exe delete $taskSvc.Name | Out-Null}
$taskMain=Get-PnpDevice -PresentOnly -InstanceId $StudioMainId -ErrorAction SilentlyContinue
if($taskMain){& (Join-Path $taskStage 'SoftwareMepNode.exe') --remove --seconds 0;if($LASTEXITCODE){throw 'Software tree removal failed.'}}
$taskLegacy=Get-PnpDevice -InstanceId 'ROOT\MEP_CAM_VEN_8086_DEV_B03E\0000' -PresentOnly -ErrorAction SilentlyContinue
if($taskLegacy){Enable-PnpDevice -InstanceId $taskLegacy.InstanceId -Confirm:$false}
$taskKey='HKLM:\'+$taskState.CameraInterfaceKey
if($taskState.OriginalFSMExisted){New-ItemProperty -LiteralPath $taskKey -Name FSMEnableMsEffects -Value $taskState.OriginalFSM -PropertyType DWord -Force | Out-Null}
else{Remove-ItemProperty -LiteralPath $taskKey -Name FSMEnableMsEffects -ErrorAction SilentlyContinue}
$taskState.Status='Uninstalled';$taskState | ConvertTo-Json | Set-Content $taskStateFile -Encoding utf8
'Service removed and recorded settings restored. Shared signed driver packages and logs were preserved.'
'On the investigation laptop, use Restore-StudioHostV2.ps1 to return to the previously working root-plus-hook setup.'
