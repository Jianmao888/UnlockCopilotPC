param([ValidateSet('Open','Warm','Stop')][string]$Action='Open')
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$manual=Join-Path $root 'runtime\phase24-manual-test'
$stateFile=Join-Path $manual 'session-state.json'
$mutex=[Threading.Mutex]::new($false,('Local\CodexCTDLauncher-'+[Security.Principal.WindowsIdentity]::GetCurrent().User.Value))
$owned=$false
try {
 try{$owned=$mutex.WaitOne(0)}catch [Threading.AbandonedMutexException]{$owned=$true}
 if(-not $owned){return}
 if($Action -eq 'Stop'){
  if(Test-Path -LiteralPath $stateFile){& (Join-Path $manual 'Stop-ManualHookSession.ps1')}
  return
 }
 $state=$null
 if(Test-Path -LiteralPath $stateFile){$state=Get-Content -LiteralPath $stateFile -Raw|ConvertFrom-Json}
 $active=$state -and $state.Status -eq 'Ready' -and [DateTimeOffset]::UtcNow -lt [DateTimeOffset]::Parse($state.ExpiresUtc) -and (Get-Process -Id $state.ControllerPid -ErrorAction SilentlyContinue)
 if(-not $active){
  $controller=Start-Process -FilePath (Join-Path $root 'ClickToDoLauncher.exe') -ArgumentList '--controller' -WindowStyle Hidden -PassThru
  $deadline=[datetime]::UtcNow.AddSeconds(45)
  while($true){
   if($controller.HasExited){throw 'Controller exited before readiness; inspect logs/controller.stderr.txt.'}
   if([datetime]::UtcNow -gt $deadline){throw 'Controller readiness timed out.'}
   if(Test-Path -LiteralPath $stateFile){
    $state=Get-Content -LiteralPath $stateFile -Raw|ConvertFrom-Json
    if($state.Status -eq 'Ready' -and [DateTimeOffset]::UtcNow -lt [DateTimeOffset]::Parse($state.ExpiresUtc)){break}
   }
   Start-Sleep -Milliseconds 150
  }
 }
 if($Action -eq 'Open'){& (Join-Path $manual 'Open-ClickToDo.ps1')}
}finally{
 if($owned){$mutex.ReleaseMutex()}
 $mutex.Dispose()
}
