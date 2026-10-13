# register-dynamic.ps1 - ASCII only
# Register our UUP product IDs the way AmperageKit did:
#   HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo\DynamicInstalled\<ProductId>
#       Version = <version>   REG_SZ
$ErrorActionPreference = 'Continue'

$ti = 'HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo\DynamicInstalled'
$apps = 'C:\Program Files\WindowsApps'

Write-Output "=== BEFORE: existing DynamicInstalled entries ==="
& reg.exe query "$ti" 2>&1 | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== register our product IDs ==="
$seen = @{}
foreach ($d in @(Get-ChildItem $apps -Directory -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload\.' })) {
    $mf = Join-Path $d.FullName 'AppxManifest.xml'
    if (-not (Test-Path $mf)) { continue }
    $raw = Get-Content $mf -Raw
    $ids = [regex]::Matches($raw, '<UupProduct\s+Id="([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
    if ($ids.Count -eq 0) { continue }
    $parts = $d.Name -split '_'
    $ver = if ($parts.Count -ge 2) { $parts[1] } else { '0.0.0.0' }
    foreach ($id in $ids) {
        if ($seen[$id]) { continue }
        $seen[$id] = $true
        & reg.exe add "$ti\$id" /v Version /t REG_SZ /d "$ver" /f 2>&1 | Out-Null
        Write-Output ("  " + $id + "  Version=" + $ver)
    }
}

Write-Output ""
Write-Output "=== also register LegacyUUP-style names with .amd64 suffix already included ==="
# some consumers look for Windows.Workload.<name>.<silicon> - we already have those
Write-Output "  (done above)"

Write-Output ""
Write-Output "=== AFTER: DynamicInstalled entries ==="
& reg.exe query "$ti" 2>&1 | Where-Object { $_ -match 'Windows.Workload' } | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== restart services ==="
foreach ($s in @('WSAIFabricSvc','StateRepository','wuauserv')) {
    try { Restart-Service $s -Force -ErrorAction Stop; Write-Output ("  " + $s + " restarted") }
    catch { Write-Output ("  " + $s + ": " + $_.Exception.Message) }
}
Start-Sleep -Seconds 15
Write-Output ""
Write-Output "=== re-check StateRepository UupProduct after service restart ==="
$dst = 'C:\Users\jianm\Code\DeepseekHarness\srd-copy4.srd'
Copy-Item 'C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd' $dst -Force -EA SilentlyContinue
python -c "import sqlite3;c=sqlite3.connect(r'$dst');print('  UupProduct rows =',c.execute('SELECT COUNT(*) FROM UupProduct').fetchone()[0]);print('  UupProductPackage rows =',c.execute('SELECT COUNT(*) FROM UupProductPackage').fetchone()[0])"
Write-Output "DONE"
