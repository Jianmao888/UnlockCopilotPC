function Assert-DeploymentResult {
 param([Parameter(Mandatory=$true)][object[]]$Events,[switch]$InstallRequested)
 $failures=@($Events | Where-Object {$_.Stage -in @('guard.stop','managed.exception','LoadLibraryEx.failed','GetProcAddress.failed') -or ($_.Stage -like '*.end' -and $_.Value -match '^0x[89A-Fa-f]')})
 if($failures.Count){throw ('Native deployment did not pass: '+(($failures | ForEach-Object {$_.Stage+': '+$_.Value}) -join '; '))}
 if(-not ($Events | Where-Object {$_.Stage -eq 'fileRequestCount' -and $_.Value -eq '0x00000000; count=0'})){throw 'No successful zero-file plan was observed.'}
 if($InstallRequested -and -not ($Events | Where-Object {$_.Stage -eq 'install.end' -and $_.Value -match '^0x00000000;'})){throw 'No successful native Install result was observed.'}
}
