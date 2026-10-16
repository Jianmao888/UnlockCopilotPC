$ErrorActionPreference='Stop'
$state=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'session-state.json') -Raw|ConvertFrom-Json
if($state.Status -ne 'Ready' -or [DateTimeOffset]::UtcNow -ge [DateTimeOffset]::Parse($state.ExpiresUtc)){
 throw 'The temporary Hook session has ended. Start a new test session first.'
}
if(-not(Get-Process -Id $state.ControllerPid -ErrorAction SilentlyContinue)){throw 'Hook controller is not running.'}
Start-Process -FilePath 'ms-clicktodo://default/?'
# Replay once after startup, as in the successful bounded experiment.
Start-Sleep -Seconds 10
$current=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'session-state.json') -Raw|ConvertFrom-Json
if($current.Status -eq 'Ready' -and $current.Label -eq $state.Label){Start-Process -FilePath 'ms-clicktodo://default/?'}
