# swap-workloads.ps1 - ASCII only
# Replace generic workloads.json with workloads.365.json so the system targets
# the .365. package families that we actually have installed.
$ErrorActionPreference = 'Continue'
$base = 'C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe'
$gen  = Join-Path $base 'workloads.json'
$v365 = Join-Path $base 'workloads.365.json'
$bak  = Join-Path $base 'workloads.json.orig-backup'

if (-not (Test-Path $v365)) { Write-Output "ERROR: workloads.365.json missing"; exit 1 }

Write-Output "=== pre-check ==="
foreach ($f in @($gen,$v365)) {
    $fi = Get-Item $f
    Write-Output ("  " + $fi.Name + "  " + $fi.Length + " bytes  " + $fi.LastWriteTime)
}

if (-not (Test-Path $bak)) {
    Copy-Item $gen $bak -Force
    Write-Output ("  backed up original -> " + $bak)
} else {
    Write-Output "  backup already exists"
}

Write-Output ""
Write-Output "=== take ownership and grant write ==="
& takeown.exe /f "$base" /r /d Y 2>&1 | Select-Object -Last 2 | ForEach-Object { "  " + $_ }
& icacls.exe "$gen" /grant "*S-1-5-32-544:F" 2>&1 | Select-Object -Last 2 | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== swap ==="
try {
    Copy-Item $v365 $gen -Force -ErrorAction Stop
    Write-Output "  copied workloads.365.json -> workloads.json"
} catch {
    Write-Output ("  COPY FAILED: " + $_.Exception.Message)
    exit 1
}
$fi = Get-Item $gen
Write-Output ("  workloads.json now " + $fi.Length + " bytes  " + $fi.LastWriteTime)

Write-Output ""
Write-Output "=== restart WSAIFabricSvc ==="
try { Restart-Service WSAIFabricSvc -Force -ErrorAction Stop; Write-Output "  restarted" }
catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 15
Get-Service WSAIFabricSvc | ForEach-Object { "  " + $_.Name + " = " + $_.Status }
Write-Output "DONE"
