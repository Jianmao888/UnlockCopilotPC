param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9-]+$')][string]$Label,[ValidateSet('observe','patch')][string]$Mode='observe',[ValidateRange(30,1800)][int]$DurationSeconds=70)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$stageParent='C:\ProgramData\CodexAIResearch'
$stage=Join-Path $stageParent ('host-startup-'+$Label)
$exe=Join-Path $stage 'HostStartupDebugger.exe'
$logs=Join-Path $stage 'logs'
$stop=Join-Path $root ($Label+'-stop.signal')
$ready=Join-Path $root ($Label+'-ready.signal')
$key='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\WorkloadsSessionHost.exe'
$filter=Join-Path $key 'CodexAIResearch'
$target='C:\Program Files\WindowsApps\WindowsWorkload.Manager.1_1.2511.1196.0_x64__8wekyb3d8bbwe\WorkloadsSessionHost.exe'
$command='"'+$exe+'" --'+$Mode+' "'+$logs+'"'
if(Test-Path -LiteralPath $key){throw 'Existing IFEO configuration: refusing to overwrite it.'}
if((Test-Path -LiteralPath $stage) -or (Test-Path -LiteralPath $ready) -or (Test-Path -LiteralPath $stop)){throw 'Use a fresh experiment label.'}
if(-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run this bounded controller through Windows sudo.'}
$armed=$false
$started=[datetime]::UtcNow
try {
 New-Item -ItemType Directory -Path $stage -Force | Out-Null
 # Service identity can execute the probe; only administrators and SYSTEM can edit it.
 $acl=New-Object Security.AccessControl.DirectorySecurity
 $acl.SetAccessRuleProtection($true,$false)
 foreach($pair in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@('S-1-5-19','ReadAndExecute'),@([Security.Principal.WindowsIdentity]::GetCurrent().User.Value,'ReadAndExecute'))){
  $sid=New-Object Security.Principal.SecurityIdentifier($pair[0])
  $rule=New-Object Security.AccessControl.FileSystemAccessRule($sid,$pair[1],'ContainerInherit,ObjectInherit','None','Allow')
  $acl.AddAccessRule($rule)
 }
 Set-Acl -LiteralPath $stage -AclObject $acl
 Copy-Item -LiteralPath (Join-Path $root 'HostStartupDebugger.exe') -Destination $exe
 Set-Content -LiteralPath (Join-Path $stage 'host-lifetime-ms.txt') -Value ([Math]::Max(1000,($DurationSeconds-5)*1000)) -Encoding ascii
 New-Item -ItemType Directory -Path $logs | Out-Null
 $logAcl=Get-Acl -LiteralPath $logs
 $localService=New-Object Security.Principal.SecurityIdentifier('S-1-5-19')
 $logAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($localService,'Modify','ContainerInherit,ObjectInherit','None','Allow')))
 Set-Acl -LiteralPath $logs -AclObject $logAcl
 [pscustomobject]@{Target=$target;OriginalKeyExisted=$false;Debugger=$command;Stage=$stage;Mode=$Mode;ExpiresUtc=[datetime]::UtcNow.AddSeconds($DurationSeconds+5).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root ($Label+'-recovery.json')) -Encoding utf8
 New-Item -Path $key | Out-Null
 $armed=$true
 New-ItemProperty -LiteralPath $key -Name UseFilter -PropertyType DWord -Value 1 | Out-Null
 New-Item -Path $filter | Out-Null
 New-ItemProperty -LiteralPath $filter -Name FilterFullPath -PropertyType String -Value $target | Out-Null
 New-ItemProperty -LiteralPath $filter -Name Debugger -PropertyType String -Value $command | Out-Null
 Set-Content -LiteralPath $ready -Value $stage
 'armed '+$stage
 $deadline=[datetime]::UtcNow.AddSeconds($DurationSeconds)
 while(-not (Test-Path -LiteralPath $stop) -and [datetime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 150}
} finally {
 if($armed){
  # Delete only the branch created by this bounded experiment, never another debugger.
  if(Test-Path -LiteralPath $filter){
   $current=Get-ItemProperty -LiteralPath $filter
   if($current.Debugger -eq $command){Remove-Item -LiteralPath $filter}
   else{throw 'Debugger changed externally; preserve it for manual review.'}
  }
  if(Test-Path -LiteralPath $key){
   $k=Get-Item -LiteralPath $key
   if($k.SubKeyCount -eq 0 -and @($k.GetValueNames() | Where-Object {$_ -ne 'UseFilter'}).Count -eq 0){Remove-ItemProperty -LiteralPath $key -Name UseFilter -ErrorAction SilentlyContinue;Remove-Item -LiteralPath $key}
  }
 }
 if(Test-Path -LiteralPath $logs){
  # Stop only exact-path debugger children recorded by this experiment.
  $pids=@(Get-ChildItem -LiteralPath $logs -Filter '*.jsonl' | ForEach-Object {Get-Content -LiteralPath $_.FullName | ForEach-Object {try{$r=$_|ConvertFrom-Json;if($r.event -eq 'child_before_entry'){$r.data.pid}}catch{}}})
  foreach($childPid in $pids){$p=Get-Process -Id $childPid -ErrorAction SilentlyContinue;if($p -and $p.Path -eq $target){Stop-Process -Id $childPid -Force}}
  Get-ChildItem -LiteralPath $logs -Filter '*.jsonl' | Copy-Item -Destination $root
 }
 # ClickToDo can start another instance that the ordinary user cannot terminate.
 # Only end exact-path clients created during this previously idle test window.
 Get-Process -Name ClickToDo -ErrorAction SilentlyContinue | Where-Object {$_.StartTime.ToUniversalTime() -ge $started -and $_.Path -ieq 'C:\Windows\SystemApps\MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy\ClickToDo.exe'} | Stop-Process -Force -ErrorAction SilentlyContinue
 Set-Content -LiteralPath (Join-Path $root ($Label+'-cleanup.json')) -Value ([pscustomobject]@{TimeUtc=[datetime]::UtcNow.ToString('o');IfeoAbsent=(-not(Test-Path -LiteralPath $key));Stage=$stage}|ConvertTo-Json) -Encoding utf8
 'cleanup complete'
}
