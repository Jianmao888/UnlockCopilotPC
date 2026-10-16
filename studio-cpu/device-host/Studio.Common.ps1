$ErrorActionPreference='Stop'
$StudioInstallRoot=Join-Path $env:ProgramData 'CodexStudioSoftwareHost'
$StudioMainId='SWD\CodexStudio\MepAssets1'
$StudioStateFile=Join-Path $StudioInstallRoot 'installation.json'
function Assert-StudioAdministrator {
 if(-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run in an elevated 64-bit PowerShell.'}
 if(-not [Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64'){throw 'This package supports x64 Windows only.'}
 if([int](Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').CurrentBuild -lt 26100){throw 'Windows 11 build 26100 or later is required by this installer.'}
}
function Initialize-StudioDirectory {
 if(Test-Path -LiteralPath $StudioInstallRoot){
  $taskItem=Get-Item -LiteralPath $StudioInstallRoot
  if($taskItem.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Installation directory must not be a reparse point.'}
 }else{New-Item -ItemType Directory -Path $StudioInstallRoot | Out-Null}
 $taskAcl=New-Object Security.AccessControl.DirectorySecurity
 $taskAcl.SetAccessRuleProtection($true,$false)
 foreach($pair in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@('S-1-5-32-545','ReadAndExecute'))){
  $taskSid=New-Object Security.Principal.SecurityIdentifier($pair[0])
  $taskAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($taskSid,$pair[1],'ContainerInherit,ObjectInherit','None','Allow')))
 }
 Set-Acl -LiteralPath $StudioInstallRoot -AclObject $taskAcl
}
function Get-StudioTree {
 $taskParent=Get-PnpDevice -InstanceId $StudioMainId -PresentOnly -ErrorAction SilentlyContinue | Select-Object InstanceId,FriendlyName,Status
 $taskChildren=@()
 if($taskParent){
  $taskChildren=@(Get-PnpDevice -PresentOnly -Class SoftwareComponent | Where-Object {$_.InstanceId -like 'SWD\DRIVERENUM\MEP_CAMERA_COMPONENT*'} | Where-Object {(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_Parent).Data -ieq $StudioMainId} | Select-Object InstanceId,FriendlyName,Status)
 }
 [pscustomobject]@{Parent=$taskParent;Cameras=$taskChildren}
}
function Get-StudioCameraInterfaces([string]$InstanceId) {
 $taskBase='SYSTEM\CurrentControlSet\Control\DeviceClasses\{E5323777-F976-4f5b-9B55-B94699C46E44}'
 $taskRoot=[Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($taskBase)
 if(-not $taskRoot){return @()}
 try {
  foreach($taskName in $taskRoot.GetSubKeyNames()){
   # Do not open the protected Properties branch: it is not a camera interface.
   if(-not $taskName.StartsWith('##?#')){continue}
   $taskKey=$taskRoot.OpenSubKey($taskName)
   if(-not $taskKey){continue}
   try {
    if($taskKey.GetValue('DeviceInstance') -ieq $InstanceId){
     $taskInterface='HKLM:\'+$taskBase+'\'+$taskName+'\#GLOBAL'
     if(Test-Path -LiteralPath $taskInterface){$taskInterface}
    }
   }finally{$taskKey.Close()}
  }
 }finally{$taskRoot.Close()}
}
function Save-StudioState($State){$State | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $StudioStateFile -Encoding utf8}
function Restore-StudioSettings($State) {
 foreach($taskEntry in @($State.CameraInterfaces)){
  if(-not (Test-Path -LiteralPath $taskEntry.Key)){continue}
  $taskCurrent=(Get-ItemProperty -LiteralPath $taskEntry.Key -Name FSMEnableMsEffects -ErrorAction SilentlyContinue).FSMEnableMsEffects
  if($taskCurrent -ne 1){Write-Warning ('Value changed outside the installer, preserving: '+$taskEntry.Key);continue}
  if($taskEntry.Existed){New-ItemProperty -LiteralPath $taskEntry.Key -Name FSMEnableMsEffects -PropertyType DWord -Value ([int]$taskEntry.Value) -Force | Out-Null}
  else{Remove-ItemProperty -LiteralPath $taskEntry.Key -Name FSMEnableMsEffects}
 }
 foreach($taskId in @($State.DisabledLegacyNodes)){Enable-PnpDevice -InstanceId $taskId -Confirm:$false}
}
