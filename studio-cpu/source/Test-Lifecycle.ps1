$ErrorActionPreference='Stop'
$taskRoot=Join-Path $env:ProgramData 'CodexStudioCpuBridge';$taskResults=@()
function Wait-Bridge([int]$DifferentWorker=0){
 $taskEnd=[datetime]::UtcNow.AddSeconds(55)
 do{try{$s=Get-Content -LiteralPath (Join-Path $taskRoot 'status.json') -Raw | ConvertFrom-Json;$svc=Get-Service CodexStudioCpuBridge;if($svc.Status -eq 'Running' -and $s.active -and $s.worker_pid -ne $DifferentWorker -and [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-[double]$s.time -lt 5){return $s}}catch{};Start-Sleep -Milliseconds 250}while([datetime]::UtcNow -lt $taskEnd)
 throw 'Bridge did not become recently attached within 30 seconds'
}
function Probe([string]$Label){
 $taskProbe=Join-Path $taskRoot 'CameraDurationProbe.exe';$taskOutput=Join-Path $taskRoot ($Label+'.mp4')
 $taskProcess=New-Object Diagnostics.Process;$taskProcess.StartInfo.FileName=$taskProbe;$taskProcess.StartInfo.Arguments='--seconds 5 --match "vid_1bcf&pid_2d03" --output "'+$taskOutput+'"';$taskProcess.StartInfo.UseShellExecute=$false;$taskProcess.StartInfo.CreateNoWindow=$true;$taskProcess.StartInfo.RedirectStandardOutput=$true;$taskProcess.StartInfo.RedirectStandardError=$true
 [void]$taskProcess.Start();$taskText=$taskProcess.StandardOutput.ReadToEndAsync();$taskError=$taskProcess.StandardError.ReadToEndAsync();if(-not $taskProcess.WaitForExit(25000)){$taskProcess.Kill();throw 'Capture timed out'}
 $taskValue=[pscustomobject]@{test=$Label;exit=$taskProcess.ExitCode;output=$taskText.Result;stderr=$taskError.Result;video=$taskOutput}
 Write-Host ($taskValue | ConvertTo-Json -Compress)
 if($taskProcess.ExitCode -ne 0 -or $taskText.Result -notmatch 'passed=1'){throw ('Capture failed: '+$Label)}
 return $taskValue
}
Stop-Service CodexStudioSoftwareHostV2
Stop-Service CodexStudioCpuBridge
foreach($taskFile in @('worker.py','runtime-agent.js')){Copy-Item -LiteralPath (Join-Path $taskRoot $taskFile) -Destination (Join-Path $taskRoot ($taskFile+'.before-lifecycle'));Copy-Item -LiteralPath (Join-Path (Join-Path $PSScriptRoot 'payload') $taskFile) -Destination $taskRoot -Force}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Verify-Bridge.ps1') -Destination $taskRoot -Force
Start-Service CodexStudioCpuBridge;Start-Service CodexStudioSoftwareHostV2
Wait-Bridge | Out-Null
$taskResults+=Probe 'service-restart-5sec'
$taskBefore=Wait-Bridge
$taskWorker=Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$taskBefore.worker_pid)
$taskService=Get-CimInstance Win32_Service -Filter "Name='CodexStudioCpuBridge'"
if($taskWorker.ExecutablePath -ine (Join-Path $taskRoot 'python\python.exe') -or $taskWorker.ParentProcessId -ne $taskService.ProcessId){throw 'Worker identity check failed; refusing fault injection'}
Stop-Process -Id ([int]$taskWorker.ProcessId) -Force
$taskAfter=Wait-Bridge ([int]$taskBefore.worker_pid)
$taskResults+=[pscustomobject]@{test='worker-crash-recovery';oldWorker=$taskBefore.worker_pid;newWorker=$taskAfter.worker_pid;passed=$true}
Stop-Service FrameServer -ErrorAction SilentlyContinue
Wait-Bridge | Out-Null;Start-Sleep -Seconds 1
$taskResults+=Probe 'worker-recovery-5sec'
$taskLast=Get-Content -LiteralPath (Join-Path $taskRoot 'status.json') -Raw | ConvertFrom-Json
$taskReport=[pscustomobject]@{tests=$taskResults;final=$taskLast;host=(Get-Service CodexStudioSoftwareHostV2).Status.ToString();rebootVerified=$false}
$taskReport | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'lifecycle-results.json') -Encoding utf8
$taskReport | ConvertTo-Json -Depth 7
