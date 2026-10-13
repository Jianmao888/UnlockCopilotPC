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
