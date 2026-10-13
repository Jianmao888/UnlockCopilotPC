# monitor-during-hang.ps1 - ASCII only
$ErrorActionPreference = 'Continue'

function Snap($label) {
    Write-Output ""
    Write-Output ("--- " + $label + " ---")

    $svcPid = (Get-CimInstance Win32_Service -Filter "Name='WSAIFabricSvc'" -EA SilentlyContinue).ProcessId
    if ($svcPid) {
        $p = Get-Process -Id $svcPid -EA SilentlyContinue
        if ($p) {
            Write-Output ("  WSAIFabricSvc pid=" + $svcPid + "  CPU=" + [math]::Round($p.TotalProcessorTime.TotalSeconds,2) + "s  WS=" + [math]::Round($p.WorkingSet64/1MB,1) + "MB  Threads=" + $p.Threads.Count)
        }
    } else { Write-Output "  WSAIFabricSvc: no pid" }

    $sr = Get-Process -Name StateRepository -EA SilentlyContinue
    if ($sr) { Write-Output ("  StateRepository   CPU=" + [math]::Round($sr.TotalProcessorTime.TotalSeconds,2) + "s") }

    $wu = @(Get-Process -EA SilentlyContinue | Where-Object { $_.ProcessName -match 'MoUsoCoreWorker|TiWorker|TrustedInstaller|wuauclt|UsoClient|WaaSMedic' })
    if ($wu.Count -gt 0) {
        foreach ($x in $wu) { Write-Output ("  WU-PROC " + $x.ProcessName + " pid=" + $x.Id + " CPU=" + [math]::Round($x.TotalProcessorTime.TotalSeconds,2) + "s") }
    } else { Write-Output "  WU-PROC: none" }

    $wl = @(Get-Process -EA SilentlyContinue | Where-Object { $_.ProcessName -match 'Workload|AIFabric|LocalSkills' })
    if ($wl.Count -gt 0) {
        foreach ($x in $wl) { Write-Output ("  WL-PROC " + $x.ProcessName + " pid=" + $x.Id + " CPU=" + [math]::Round($x.TotalProcessorTime.TotalSeconds,2) + "s") }
    } else { Write-Output "  WL-PROC: none" }

    $conns = @(Get-NetTCPConnection -State Established,SynSent -EA SilentlyContinue |
               Where-Object { $_.RemoteAddress -notmatch '^(127\.|::1|0\.0\.0\.0|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)' })
    Write-Output ("  external TCP conns: " + $conns.Count)
    $conns | Select-Object -First 12 | ForEach-Object {
        $pn = (Get-Process -Id $_.OwningProcess -EA SilentlyContinue).ProcessName
        Write-Output ("      " + $_.RemoteAddress + ":" + $_.RemotePort + "  <- " + $pn + "  state=" + $_.State)
    }
}

Write-Output "############ T0 baseline ############"
Snap "T0"

Write-Output ""
Write-Output "############ launch EnsureReadyAsync probe (background) ############"
$job = Start-Job -ScriptBlock {
    $env:PYTHONIOENCODING='utf-8'
    & python -u 'C:\Users\jianm\Code\DeepseekHarness\ensure_ready_probe.py' 2>&1
}
Write-Output ("  job id: " + $job.Id)

Start-Sleep -Seconds 12
Write-Output ""
Write-Output "############ T1 (hang ~12s) ############"
Snap "T1"

Start-Sleep -Seconds 25
Write-Output ""
Write-Output "############ T2 (hang ~37s) ############"
Snap "T2"

Start-Sleep -Seconds 30
Write-Output ""
Write-Output "############ T3 (hang ~67s) ############"
Snap "T3"

Write-Output ""
Write-Output "############ probe output ############"
Receive-Job $job -EA SilentlyContinue | Select-Object -Last 20
Remove-Job $job -Force -EA SilentlyContinue
Write-Output "DONE"
