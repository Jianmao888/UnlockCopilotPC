# etw-list.ps1 - ASCII only
$ErrorActionPreference = 'Continue'

Write-Output "=== WU / Update / USO related ETW providers ==="
$all = & logman.exe query providers 2>$null
$lines = $all -split "`r?`n"
$cur = $null
$out = @()
foreach ($l in $lines) {
    if ($l -match '^\s*\[?\{?[0-9a-fA-F\-]{36}' -or $l -match '^\s*\S.*\{[0-9a-fA-F\-]{36}\}') {
        $cur = $l.Trim()
    }
}
# simpler: grep provider name lines
$all | Select-String -Pattern 'WindowsUpdate|WU-|USO|UpdateSession|UsoSvc|wuau|AppXDeployment|StateRepository|AppReadiness|Workload|AIFabric|PackageManager' |
  Select-Object -First 60 | ForEach-Object { "  " + $_.Line.Trim() }
Write-Output ""
Write-Output "=== providers containing 'Update' ==="
$all | Select-String -Pattern 'Update' | Select-Object -First 60 | ForEach-Object { "  " + $_.Line.Trim() }
Write-Output ""
Write-Output "=== logman / tracerpt / wpr availability ==="
foreach ($e in 'logman.exe','tracerpt.exe','wpr.exe','wevtutil.exe') {
    $p = Join-Path $env:SystemRoot "System32\$e"
    Write-Output ("  " + $e + " : " + (Test-Path $p))
}
Write-Output ""
Write-Output "=== existing ETW sessions ==="
& logman.exe query -ets 2>&1 | Select-Object -First 30 | ForEach-Object { "  " + $_ }
Write-Output "DONE"
