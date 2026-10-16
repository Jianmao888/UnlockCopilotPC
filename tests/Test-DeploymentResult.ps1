$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '..\native-install\tools\Assert-DeploymentResult.ps1')
$plan=[pscustomobject]@{Stage='fileRequestCount';Value='0x00000000; count=0'}
$success=[pscustomobject]@{Stage='install.end';Value='0x00000000; rebootRequired=0; result=0'}
Assert-DeploymentResult -Events @($plan)
Assert-DeploymentResult -Events @($plan,$success) -InstallRequested
$rejected=0
foreach($bad in @(
 @([pscustomobject]@{Stage='fileRequestCount';Value='0x00000000; count=1'}),
 @($plan,[pscustomobject]@{Stage='guard.stop';Value='Missing payload'}),
 @($plan,[pscustomobject]@{Stage='install.end';Value='0x80070005; denied'}),
 @($plan,[pscustomobject]@{Stage='managed.exception';Value='failure'}),
 @($plan)
)){
 $caught=$false
 try{Assert-DeploymentResult -Events $bad -InstallRequested}catch{$caught=$true}
 if(-not $caught){throw 'An incomplete/failed synthetic deployment was accepted'}
 $rejected++
}
[pscustomobject]@{SuccessfulCases=2;RejectedFailureCases=$rejected;SystemInstallCalled=$false}|ConvertTo-Json
