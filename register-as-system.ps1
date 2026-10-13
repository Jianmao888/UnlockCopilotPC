# register-as-system.ps1 - run package registration as SYSTEM via scheduled task
$ErrorActionPreference = 'Continue'
$HERE = 'C:\Users\jianm\Code\DeepseekHarness'
$inner = Join-Path $HERE '_register-inner.ps1'
$log   = Join-Path $HERE 'install-experiment\register-system.log'

$body = @'
$ErrorActionPreference = 'Continue'
$log = 'C:\Users\jianm\Code\DeepseekHarness\install-experiment\register-system.log'
"=== running as: $([Security.Principal.WindowsIdentity]::GetCurrent().Name) ===" | Out-File $log -Encoding utf8
$pkgs = @(
  'C:\Program Files\WindowsApps\WindowsWorkload.TextRecognition.Lnl.1_1.2608.951.0_x64__8wekyb3d8bbwe\AppxManifest.xml',
  'C:\Program Files\WindowsApps\WindowsWorkload.ScrRegDetection.Lnl.1_1.2509.1022.0_x64__8wekyb3d8bbwe\AppxManifest.xml'
)
foreach ($m in $pkgs) {
  if (-not (Test-Path $m)) { "MISSING $m" | Out-File $log -Append -Encoding utf8; continue }
  try {
    Add-AppxPackage -Register $m -DisableDevelopmentMode -ErrorAction Stop
    "OK   $m" | Out-File $log -Append -Encoding utf8
  } catch {
    "ERR  $m -> $($_.Exception.Message)" | Out-File $log -Append -Encoding utf8
  }
}
"DONE" | Out-File $log -Append -Encoding utf8
'@

New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
Set-Content -LiteralPath $inner -Value $body -Encoding ascii
Write-Output ("inner script written: " + (Test-Path $inner))

Write-Output "=== run registration as SYSTEM ==="
$taskName = 'DSH-RegisterWorkload'
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $inner + '"')
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 30
$st = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Write-Output ("  task state: " + $st.State)
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Write-Output ""
Write-Output "=== SYSTEM side log ==="
if (Test-Path $log) { Get-Content $log } else { Write-Output "  (no log)" }

Write-Output ""
Write-Output "=== current user packages ==="
Get-AppxPackage -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' } |
  Select-Object Name, Version, Status | Format-Table -AutoSize
Write-Output "DONE"
