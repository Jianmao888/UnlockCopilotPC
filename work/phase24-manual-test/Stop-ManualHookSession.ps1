$ErrorActionPreference='Stop'
$state=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'session-state.json') -Raw|ConvertFrom-Json
if($state.Status -ne 'Ready'){return}
$expectedRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\phase21-host-ifeo')).Path
$expected=Join-Path $expectedRoot ($state.Label+'-stop.signal')
if($state.StopSignal -ne $expected){throw 'Unexpected stop-signal path.'}
if($state.NativeStopSignal){
 $nativeRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\phase26-shell-entry')).Path
 $nativeStop=Join-Path $nativeRoot ($state.Label+'-native-stop.signal')
 if($state.NativeStopSignal -ne $nativeStop){throw 'Unexpected native stop-signal path.'}
 Set-Content -LiteralPath $nativeStop -Value stop
 $nativeDone=Join-Path $nativeRoot ($state.Label+'-native-done.json')
 $deadline=[datetime]::UtcNow.AddSeconds(9)
 while(-not(Test-Path -LiteralPath $nativeDone) -and [datetime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100}
}
Set-Content -LiteralPath $expected -Value stop
