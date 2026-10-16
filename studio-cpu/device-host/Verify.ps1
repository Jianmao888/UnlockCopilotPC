param([switch]$RecordFiveSeconds,[string]$OutputDirectory)
. (Join-Path $PSScriptRoot 'Studio.Common.ps1')
Assert-StudioAdministrator
$taskStage=Join-Path $env:ProgramData 'CodexStudioHostV2'
$taskService=Get-CimInstance Win32_Service -Filter "Name='CodexStudioSoftwareHostV2'"
$taskStatus=Get-Content (Join-Path $taskStage 'status.json') -Raw | ConvertFrom-Json
if($taskService.State -ne 'Running' -or -not $taskStatus.active -or $taskStatus.pid -ne $taskService.ProcessId){throw 'Service is not running with a current ready status.'}
$taskTree=Get-StudioTree
if(-not $taskTree.Parent -or $taskTree.Cameras.Count -ne 1){throw 'Expected software device tree is absent.'}
$taskData=[pscustomobject]@{Service=($taskService | Select-Object Name,State,StartMode,StartName,ProcessId);State=$taskStatus;Tree=$taskTree;ContinuousCaptureRequested=[bool]$RecordFiveSeconds;RebootAcceptanceStillRequired=$true}
$taskData | ConvertTo-Json -Depth 6
if($RecordFiveSeconds){
 if(-not $OutputDirectory){$OutputDirectory=Join-Path $PSScriptRoot ('validation-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
 New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
 $taskDeploy=Get-Content (Join-Path $taskStage 'deployment.json') -Raw | ConvertFrom-Json
 $taskMatch=$taskDeploy.CameraInstanceId.Replace('\','#').ToLowerInvariant()
 $taskClip=Join-Path ([IO.Path]::GetFullPath($OutputDirectory)) 'camera-5sec.mp4'
 $taskExe=Join-Path $taskStage 'CameraDurationProbe.exe'
 $taskArgs='--seconds 5 --match "'+$taskMatch+'" --output "'+$taskClip+'"'
 $taskChild=New-Object Diagnostics.Process
 $taskChild.StartInfo.FileName=$taskExe;$taskChild.StartInfo.Arguments=$taskArgs
 $taskChild.StartInfo.UseShellExecute=$false;$taskChild.StartInfo.CreateNoWindow=$true;$taskChild.StartInfo.WindowStyle='Hidden'
 $taskChild.StartInfo.RedirectStandardOutput=$true;$taskChild.StartInfo.RedirectStandardError=$true
 [void]$taskChild.Start()
 $taskStdout=$taskChild.StandardOutput.ReadToEndAsync();$taskStderr=$taskChild.StandardError.ReadToEndAsync()
 if(-not $taskChild.WaitForExit(25000)){$taskChild.Kill();$taskChild.WaitForExit();throw 'Capture timed out.'}
 $taskText=$taskStdout.Result
 [IO.File]::WriteAllText((Join-Path $OutputDirectory 'capture.txt'),$taskText)
 [IO.File]::WriteAllText((Join-Path $OutputDirectory 'capture-error.txt'),$taskStderr.Result)
 $taskText
 if($taskChild.ExitCode -ne 0 -or $taskText -notmatch 'passed=1'){throw 'Continuous five-second capture did not pass.'}
 'Saved clip: '+$taskClip
}
