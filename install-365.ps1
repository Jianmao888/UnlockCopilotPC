# install-365.ps1 - ASCII only
# Install the 14 MSIX required by the three satisfiable 365 workloads,
# then swap in the minimal workloads.json and restart the service.
$ErrorActionPreference = 'Continue'

$listFile = 'C:\Users\jianm\Code\DeepseekHarness\_install-list.txt'
$base = 'C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe'
$gen = Join-Path $base 'workloads.json'
$backup = Join-Path $base 'workloads.json.orig-backup'

$paths = @(Get-Content $listFile | Where-Object { $_.Trim() -ne '' })
Write-Output ("=== installing " + $paths.Count + " MSIX ===")

# pass 1
foreach ($p in $paths) {
    $n = Split-Path $p -Leaf
    try {
        Add-AppxPackage -Path $p -ForceApplicationShutdown -ErrorAction Stop
        Write-Output ("  ok      " + $n)
    } catch {
        Write-Output ("  retry?  " + $n + " : " + $_.Exception.Message.Split([Environment]::NewLine)[0])
    }
}

Write-Output ""
Write-Output "=== pass 2 (dependencies may need a second try) ==="
foreach ($p in $paths) {
    $n = Split-Path $p -Leaf
    try {
        Add-AppxPackage -Path $p -ForceApplicationShutdown -ErrorAction Stop
        Write-Output ("  ok      " + $n)
    } catch {
        Write-Output ("  FAIL    " + $n + " : " + $_.Exception.Message.Split([Environment]::NewLine)[0])
    }
}

Write-Output ""
Write-Output "=== installed WindowsWorkload packages ==="
@(Get-AppxPackage | Where-Object { $_.Name -match '^WindowsWorkload' }) |
    Sort-Object Name | ForEach-Object { "  " + $_.Name + "  " + $_.Version + "  " + $_.Status }

Write-Output ""
Write-Output "=== swap in minimal workloads.json ==="
if (-not (Test-Path $backup)) { Copy-Item $gen $backup -Force; Write-Output "  original backed up" }
& takeown.exe /f "$base" /r /d Y 2>&1 | Out-Null
& icacls.exe "$gen" /grant "*S-1-5-32-544:F" 2>&1 | Out-Null
python 'C:\Users\jianm\Code\DeepseekHarness\build_min_workloads.py'

Write-Output ""
Write-Output "=== restart WSAIFabricSvc ==="
try { Restart-Service WSAIFabricSvc -Force -ErrorAction Stop; Write-Output "  restarted" }
catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 20
Get-Service WSAIFabricSvc | ForEach-Object { "  " + $_.Name + " = " + $_.Status }
Write-Output "DONE"
