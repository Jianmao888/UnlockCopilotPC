param([ValidateRange(120,1750)][int]$DurationSeconds=900)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$hostRoot=(Resolve-Path -LiteralPath (Join-Path $root '..\phase21-host-ifeo')).Path
$old=(Resolve-Path -LiteralPath (Join-Path $root '..\phase19-clicktodo')).Path
$nativeRoot=(Resolve-Path -LiteralPath (Join-Path $root '..\phase26-shell-entry')).Path
$python='C:\Users\jianm\AppData\Local\Programs\Python\Python312\python.exe'
$stateFile=Join-Path $root 'session-state.json'
$pins=@{
 'C:\Windows\SystemApps\MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy\ClickToDo.exe'='6f709cb5e0b3506dcda250ae3ee27d67f25153a7f8db33f6173c7a3c4c889961'
 'C:\Windows\SystemApps\MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy\DiscoveryOverlay.dll'='0196208387b97bcd0ef59b3cc7782af941cc53e258ddaa6644fee6eb0fc6d37d'
 'C:\Windows\SystemApps\Microsoft.WindowsAppRuntime.CBS_8wekyb3d8bbwe\Microsoft.Windows.Workloads.dll'='19d6f9fb8cdf32caa522d887bd2023a1a03886ade0d09cc0ce7dead85e6850c4'
 'C:\Windows\System32\WSAIFabricHost.dll'='dbe0d2a3a7f314f8764deef43354af19dd73ffd660d086a792ce37e4f7ca7717'
}
foreach($path in $pins.Keys){if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ine $pins[$path]){throw ('Target version changed: '+$path)}}
if(Get-Process -Name ClickToDo,WorkloadsSessionHost -ErrorAction SilentlyContinue){throw 'Existing client or AI session: leave it untouched.'}
if(Test-Path -LiteralPath $stateFile){
 $previous=Get-Content -LiteralPath $stateFile -Raw|ConvertFrom-Json
 if($previous.Status -in @('Starting','Ready') -and (Get-Process -Id $previous.ControllerPid -ErrorAction SilentlyContinue)){throw 'A manual session controller is already running.'}
}
$label='interactive-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,6)
$ready=Join-Path $hostRoot ($label+'-ready.signal')
$stop=Join-Path $hostRoot ($label+'-stop.signal')
$expires=[DateTimeOffset]::UtcNow.AddSeconds($DurationSeconds)
$state=[ordered]@{Status='Starting';Label=$label;ControllerPid=$PID;StartedUtc=[datetime]::UtcNow.ToString('o');ExpiresUtc=$expires.ToString('o');ExpiresLocal=$expires.ToOffset([timespan]::FromHours(8)).ToString('yyyy-MM-dd HH:mm:ss zzz');StopSignal=$stop;ClientLog=(Join-Path $root 'runtime\startup-hook.jsonl')}
$nativeStop=Join-Path $nativeRoot ($label+'-native-stop.signal')
$nativeReady=Join-Path $nativeRoot ($label+'-native-ready.json')
$state.NativeStopSignal=$nativeStop
$state.NativeWinQReady=$false
function Save-State {$state|ConvertTo-Json|Set-Content -LiteralPath $stateFile -Encoding utf8}
Save-State
$controller=$null;$hookController=$null;$clientEnabled=$false;$nativeController=$null
try {
 $arm=Join-Path $hostRoot 'Arm-HostStartupProbe.ps1'
 $controller=Start-Process -FilePath 'C:\Windows\System32\sudo.exe' -ArgumentList @('--inline','powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$arm+'"'),'-Label',$label,'-Mode','patch','-DurationSeconds',($DurationSeconds+20)) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $hostRoot ($label+'-admin.stdout.txt')) -RedirectStandardError (Join-Path $hostRoot ($label+'-admin.stderr.txt'))
 $deadline=[datetime]::UtcNow.AddSeconds(15)
 while(-not(Test-Path -LiteralPath $ready)){
  if($controller.HasExited){throw 'Elevated controller exited before readiness.'}
  if([datetime]::UtcNow -gt $deadline){throw 'Arming timed out.'}
  Start-Sleep -Milliseconds 100
 }
 $hook=Join-Path $hostRoot 'attach-real-hosts.py'
 $hookController=Start-Process -FilePath 'C:\Windows\System32\sudo.exe' -ArgumentList @('--inline',('"'+$python+'"'),('"'+$hook+'"'),'--label',$label,'--duration-seconds',($DurationSeconds+20)) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $hostRoot ($label+'-hooks.stdout.txt')) -RedirectStandardError (Join-Path $hostRoot ($label+'-hooks.stderr.txt'))
 $hookReady=Join-Path $hostRoot ($label+'-hooks-ready.signal')
 $deadline=[datetime]::UtcNow.AddSeconds(10)
 while(-not(Test-Path -LiteralPath $hookReady)){
  if($hookController.HasExited){throw 'Model hook controller exited early.'}
  if([datetime]::UtcNow -gt $deadline){throw 'Model hook readiness timed out.'}
  Start-Sleep -Milliseconds 100
 }
 & (Join-Path $old 'package-debugging.ps1') -Action Enable -DebuggerPath (Join-Path $root 'manual-client-debugger.py')
 $clientEnabled=$true
 # Warm the package without sending a screen-selection invocation.
 & $python (Join-Path $hostRoot 'activate-client.py')
 if($LASTEXITCODE -ne 0){throw 'Packaged background activation failed.'}
 # Coordinate the existing native hotkey registrations after warming the client.
 $nativeScript=Join-Path $nativeRoot 'native-hotkey-session.py'
 $remaining=[Math]::Max(1,[int]($expires-[DateTimeOffset]::UtcNow).TotalSeconds)
 $nativeController=Start-Process -FilePath $python -ArgumentList @(('"'+$nativeScript+'"'),'--label',$label,'--parent-pid',$PID,'--duration-seconds',$remaining) -WindowStyle Hidden -PassThru
 $deadline=[datetime]::UtcNow.AddSeconds(15)
 while(-not(Test-Path -LiteralPath $nativeReady) -and -not $nativeController.HasExited -and [datetime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100}
 if(Test-Path -LiteralPath $nativeReady){
  $nativeResult=Get-Content -LiteralPath $nativeReady -Raw|ConvertFrom-Json
  $state.NativeWinQReady=[bool]$nativeResult.Ready
  if(-not $nativeResult.Ready){$state.NativeWinQError=$nativeResult.Error}
 }else{
  Set-Content -LiteralPath $nativeStop -Value stop
  $state.NativeWinQError='Native hotkey coordination timed out; see native log.'
 }
 $state.Status='Ready';Save-State
 while([DateTimeOffset]::UtcNow -lt $expires -and -not(Test-Path -LiteralPath $stop)){
  if($controller.HasExited -or $hookController.HasExited){throw 'A hook controller stopped before the test expired.'}
  Start-Sleep -Milliseconds 250
 }
} catch {
 $state.Error=$_.Exception.Message
 throw
} finally {
 # Restore Search on its UI thread before the host controller stops ClickToDo.
 Set-Content -LiteralPath $nativeStop -Value stop
 if($nativeController){$null=$nativeController.WaitForExit(9500)}
 $nativeDone=Join-Path $nativeRoot ($label+'-native-done.json')
 if(Test-Path -LiteralPath $nativeDone){$state.NativeCleanup=Get-Content -LiteralPath $nativeDone -Raw|ConvertFrom-Json}
 if($clientEnabled){& (Join-Path $old 'package-debugging.ps1') -Action Disable}
 Set-Content -LiteralPath $stop -Value stop
 if($controller){$null=$controller.WaitForExit(10000)}
 if($hookController){$null=$hookController.WaitForExit(6000)}
 $state.Status='Stopped';$state.StoppedUtc=[datetime]::UtcNow.ToString('o')
 $state.IfeoAbsent=(-not(Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\WorkloadsSessionHost.exe'))
 Save-State
}
