# try-ls2.ps1 - ASCII only; LocalService registration with preserved log
$ErrorActionPreference = 'Continue'
$HERE = 'C:\Users\jianm\Code\DeepseekHarness'
$inner = Join-Path $HERE '_ls2-inner.ps1'
$log = Join-Path $HERE 'install-experiment\ls2.log'
$outdir = Join-Path $HERE 'install-experiment'
New-Item -ItemType Directory -Force -Path $outdir | Out-Null
Remove-Item $log -Force -ErrorAction SilentlyContinue

$body = @'
$ErrorActionPreference = 'Continue'
$log = 'C:\Users\jianm\Code\DeepseekHarness\install-experiment\ls2.log'
function W($s) { $s | Out-File $log -Append -Encoding utf8 }
W ("=== running as: " + [Security.Principal.WindowsIdentity]::GetCurrent().Name)
$pkgs = @(
  'C:\Program Files\WindowsApps\WindowsWorkload.TextRecognition.Lnl.1_1.2608.951.0_x64__8wekyb3d8bbwe\AppxManifest.xml',
  'C:\Program Files\WindowsApps\WindowsWorkload.ScrRegDetection.Lnl.1_1.2509.1022.0_x64__8wekyb3d8bbwe\AppxManifest.xml'
)
foreach ($m in $pkgs) {
  if (-not (Test-Path $m)) { W ("MISSING " + $m); continue }
  try {
    Add-AppxPackage -Register $m -DisableDevelopmentMode -ErrorAction Stop
    W ("OK   " + $m)
  } catch {
    W ("ERR  " + $m)
    W ("     " + $_.Exception.Message)
  }
}
W "DONE"
'@
Set-Content -LiteralPath $inner -Value $body -Encoding ascii
icacls $outdir /grant '*S-1-5-19:(OI)(CI)F' /T 2>&1 | Out-Null
icacls $outdir /grant '*S-1-5-20:(OI)(CI)F' /T 2>&1 | Out-Null

$taskName = 'DSH-LS2'
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $inner + '"')
$principal = New-ScheduledTaskPrincipal -UserId 'NT AUTHORITY\LOCAL SERVICE' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 30
$st = Get-ScheduledTask -TaskName $taskName -EA SilentlyContinue
Write-Output ("task state: " + $st.State)
$inf = Get-ScheduledTaskInfo -TaskName $taskName -EA SilentlyContinue
Write-Output ("last result: " + $inf.LastTaskResult)
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Write-Output ""
Write-Output "=== LS log ==="
if (Test-Path $log) { Get-Content $log } else { Write-Output "(no log - service account may lack write access)" }

Write-Output ""
Write-Output "=== current user packages ==="
Get-AppxPackage -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' } |
  ForEach-Object { "  " + $_.Name + "  v" + $_.Version }
Write-Output "DONE"
