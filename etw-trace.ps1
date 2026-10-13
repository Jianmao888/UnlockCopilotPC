# etw-trace.ps1 - ASCII only
# Capture ETW from WU / AppX / StateRepository providers while EnsureReadyAsync runs.
$ErrorActionPreference = 'Continue'

$sess = 'DSHWU'
$etl  = 'C:\Users\jianm\Code\DeepseekHarness\etw-ensure.etl'
$out  = 'C:\Users\jianm\Code\DeepseekHarness\etw-ensure'
$env:PYTHONIOENCODING = 'utf-8'

# providers
$providers = @(
  'Microsoft-Windows-WindowsUpdateClient',
  'Microsoft-Windows-AppXDeployment',
  'Microsoft-Windows-AppXDeployment-Server',
  'Microsoft-Windows-StateRepository',
  'Microsoft-Windows-AppReadiness'
)

Write-Output "=== cleanup any prior session ==="
& logman.exe stop $sess -ets 2>&1 | Out-Null
& logman.exe delete $sess -ets 2>&1 | Out-Null

Write-Output "=== create trace session ==="
& logman.exe create trace $sess -o $etl -ets -ow 2>&1 | Select-Object -First 5 | ForEach-Object { "  " + $_ }

foreach ($p in $providers) {
  # try keywords 0xffffffffffffffff, level 5 (verbose)
  $r = & logman.exe update trace $sess -ets -p $p 0xffffffffffffffff 5 2>&1
  Write-Output ("  + " + $p + "  -> " + ($r -join ' '))
}

Write-Output ""
Write-Output "=== start capture + launch probe ==="
$job = Start-Job -ScriptBlock {
    $env:PYTHONIOENCODING='utf-8'
    & python -u 'C:\Users\jianm\Code\DeepseekHarness\ensure_ready_probe.py' 2>&1
}
Write-Output ("  probe job: " + $job.Id)

# probe runs 120s; capture for 70s
Start-Sleep -Seconds 70

Write-Output ""
Write-Output "=== stop session ==="
& logman.exe stop $sess -ets 2>&1 | Select-Object -First 5 | ForEach-Object { "  " + $_ }
Start-Sleep -Seconds 3

Write-Output ""
Write-Output "=== etl size ==="
Get-Item $etl -EA SilentlyContinue | ForEach-Object { "  " + $_.Length + " bytes" }

Write-Output ""
Write-Output "=== convert to CSV with tracerpt ==="
& tracerpt.exe $etl -o "$out.csv" -of CSV -y 2>&1 | Select-Object -First 6 | ForEach-Object { "  " + $_ }
Get-Item "$out.csv" -EA SilentlyContinue | ForEach-Object { "  csv: " + $_.Length + " bytes" }

Write-Output ""
Write-Output "=== probe output ==="
Receive-Job $job -EA SilentlyContinue | Select-Object -Last 6
Remove-Job $job -Force -EA SilentlyContinue
Write-Output "DONE"
