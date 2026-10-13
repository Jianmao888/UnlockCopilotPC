# try-localservice.ps1 - ASCII only; attempt registration as NT AUTHORITY\LOCAL SERVICE
$ErrorActionPreference = 'Continue'
$HERE = 'C:\Users\jianm\Code\DeepseekHarness'
$inner = Join-Path $HERE '_ls-inner.ps1'
$log = Join-Path $HERE 'install-experiment\register-localservice.log'

$body = @'
$ErrorActionPreference = 'Continue'
$log = 'C:\Users\jianm\Code\DeepseekHarness\install-experiment\register-localservice.log'
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
Remove-Item $log -Force -ErrorAction SilentlyContinue

foreach ($acct in @('NT AUTHORITY\LOCAL SERVICE', 'NT AUTHORITY\NETWORK SERVICE')) {
  Write-Output ("=== try as " + $acct + " ===")
  $taskName = 'DSH-RegLS'
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
  try {
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $inner + '"')
    $principal = New-ScheduledTaskPrincipal -UserId $acct -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName $taskName
    Start-Sleep -Seconds 25
    $st = Get-ScheduledTask -TaskName $taskName -EA SilentlyContinue
    Write-Output ("  task state: " + $st.State)
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
  } catch {
    Write-Output ("  task error: " + $_.Exception.Message)
  }
  if (Test-Path $log) { Get-Content $log | ForEach-Object { "    " + $_ }; Remove-Item $log -Force }
}

Write-Output ""
Write-Output "=== current user packages ==="
Get-AppxPackage -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' } |
  ForEach-Object { "  " + $_.Name + "  v" + $_.Version }
Write-Output "DONE"
