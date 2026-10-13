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
