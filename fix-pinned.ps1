# fix-pinned.ps1 - ASCII only; ensure all 7 packages are pinned
$ErrorActionPreference = 'Continue'
$base = 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore'
$pinned = "$base\Pinned"

Write-Output "=== all WindowsWorkload dirs on disk ==="
$dirs = @(Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -EA SilentlyContinue |
          Where-Object { $_.Name -match '^WindowsWorkload\.' })
$fams = @()
foreach ($d in $dirs) {
    $parts = $d.Name -split '_'
    if ($parts.Count -ge 3) {
        $fam = $parts[0] + '_' + $parts[-1]
        $fams += $fam
        Write-Output ("  " + $d.Name + "  ->  " + $fam)
    }
}

Write-Output ""
Write-Output "=== ensure Pinned entries ==="
if (-not (Test-Path $pinned)) { New-Item -Path $pinned -Force | Out-Null }
$existing = @(Get-ChildItem $pinned -EA SilentlyContinue | Select-Object -ExpandProperty PSChildName)
foreach ($f in ($fams | Sort-Object -Unique)) {
    if ($existing -contains $f) { Write-Output ("  already: " + $f); continue }
    & reg.exe add "$pinned\$f" /f 2>&1 | Out-Null
    Write-Output ("  pinned : " + $f)
}

Write-Output ""
Write-Output "=== Pinned final ==="
& reg.exe query "$pinned" 2>&1 | Where-Object { $_ -match 'WindowsWorkload' } | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== restart WSAIFabricSvc ==="
try { Restart-Service WSAIFabricSvc -Force -ErrorAction Stop; Write-Output "  restarted" } catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 15
Get-Service WSAIFabricSvc | ForEach-Object { "  " + $_.Name + " = " + $_.Status }

Write-Output ""
Write-Output "=== check if WSAIFabricSvc loaded the workload DLLs ==="
$p = Get-Process -Name 'svchost' -EA SilentlyContinue
Write-Output "  (checking via tasklist for WSAIFabricSvc host)"
& tasklist.exe /svc /fi "IMAGENAME eq svchost.exe" 2>&1 | Select-String 'WSAIFabricSvc' | ForEach-Object { "  " + $_.Line.Trim() }
Write-Output "DONE"
