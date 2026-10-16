# register-current-user.ps1 - register the provisioned packages for the current user
$ErrorActionPreference = 'Continue'
Write-Output "=== 预置包（全机）==="
Get-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue |
  Where-Object { $_.DisplayName -match 'WindowsWorkload' } |
  Select-Object DisplayName, Version, PackageName | Format-Table -AutoSize

Write-Output ""
Write-Output "=== 落盘目录 ==="
Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match 'WindowsWorkload' } | Select-Object -ExpandProperty Name

Write-Output ""
Write-Output "=== 尝试 1: Add-AppxPackage 再次安装 ==="
foreach ($p in @(
  'C:\Users\jianm\Code\DeepseekHarness\ai-packages-legacy\99c8c976-ccf8-753b-683d-07c62b9e7e6c_1.2509.1022.0_x64.msix',
  'C:\Users\jianm\Code\DeepseekHarness\ai-packages\WindowsWorkload.TextRecognition.Lnl.1_1.2608.951.0_x64.msix')) {
  $n = Split-Path $p -Leaf
  try {
    Add-AppxPackage -Path $p -ForceUpdateFromAnyVersion -ErrorAction Stop
    Write-Output ("  OK   " + $n)
  } catch {
    Write-Output ("  ERR  " + $n + " -> " + $_.Exception.Message)
  }
}

Write-Output ""
Write-Output "=== 尝试 2: 对已落盘清单 -Register ==="
foreach ($d in (Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match 'WindowsWorkload' })) {
  $mf = Join-Path $d.FullName 'AppxManifest.xml'
  if (-not (Test-Path $mf)) { continue }
  if ($d.Name -notmatch 'Lnl|ScrReg|TextRecog') { continue }
  try {
    Add-AppxPackage -Register $mf -DisableDevelopmentMode -ErrorAction Stop
    Write-Output ("  OK   " + $d.Name)
  } catch {
    Write-Output ("  ERR  " + $d.Name + " -> " + $_.Exception.Message)
  }
}
Write-Output "DONE"
