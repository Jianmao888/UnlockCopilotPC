# try-devmode.ps1 - ASCII only; test whether developer mode unblocks accessControl.undocked
$ErrorActionPreference = 'Continue'
$reg = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock'
$before = (Get-ItemProperty $reg -EA SilentlyContinue).AllowDevelopmentWithoutDevLicense
Write-Output ("before AllowDevelopmentWithoutDevLicense = " + $before)

if (-not (Test-Path $reg)) { New-Item -Path $reg -Force | Out-Null }
Set-ItemProperty -Path $reg -Name 'AllowDevelopmentWithoutDevLicense' -Value 1 -Type DWord -Force
Set-ItemProperty -Path $reg -Name 'AllowAllTrustedApps' -Value 1 -Type DWord -Force
$after = (Get-ItemProperty $reg).AllowDevelopmentWithoutDevLicense
Write-Output ("after  AllowDevelopmentWithoutDevLicense = " + $after)

Write-Output ""
Write-Output "=== retry registration with developer mode ON ==="
$pkgs = @(
  'C:\Users\jianm\Code\DeepseekHarness\ai-packages-legacy\99c8c976-ccf8-753b-683d-07c62b9e7e6c_1.2509.1022.0_x64.msix',
  'C:\Users\jianm\Code\DeepseekHarness\ai-packages\WindowsWorkload.TextRecognition.Lnl.1_1.2608.951.0_x64.msix'
)
foreach ($p in $pkgs) {
  $n = Split-Path $p -Leaf
  try {
    Add-AppxPackage -Path $p -ForceUpdateFromAnyVersion -ErrorAction Stop
    Write-Output ("  OK   " + $n)
  } catch {
    Write-Output ("  ERR  " + $n + " -> " + $_.Exception.Message)
  }
}

Write-Output ""
Write-Output "=== current user packages ==="
Get-AppxPackage -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' } |
  ForEach-Object { "  " + $_.Name + "  v" + $_.Version }

Write-Output ""
Write-Output "=== restore developer mode to original value ==="
Set-ItemProperty -Path $reg -Name 'AllowDevelopmentWithoutDevLicense' -Value $before -Type DWord -Force
Write-Output ("  restored to " + (Get-ItemProperty $reg).AllowDevelopmentWithoutDevLicense)
Write-Output "DONE"
