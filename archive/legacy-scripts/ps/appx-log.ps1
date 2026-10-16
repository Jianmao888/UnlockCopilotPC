# appx-log.ps1 - inspect why windows.accessControl.undocked registration is denied
$ErrorActionPreference = 'Continue'

Write-Output "=== A) 最近的 AppX 部署失败事件 ==="
$ev = Get-WinEvent -LogName 'Microsoft-Windows-AppXDeploymentServer/Operational' -MaxEvents 40 -ErrorAction SilentlyContinue |
  Where-Object { $_.Message -match 'accessControl|undocked|0x80070005' }
foreach ($e in ($ev | Select-Object -First 4)) {
  Write-Output ("--- " + $e.TimeCreated + "  Id=" + $e.Id + " ---")
  ($e.Message -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 12) | ForEach-Object { "    " + $_.Trim() }
}

Write-Output ""
Write-Output "=== B) 崩溃/部署错误事件 ==="
Get-WinEvent -LogName 'Microsoft-Windows-AppXDeployment/Operational' -MaxEvents 20 -ErrorAction SilentlyContinue |
  Select-Object -First 6 | ForEach-Object {
    Write-Output ("--- " + $_.TimeCreated + " Id=" + $_.Id + " ---")
    ($_.Message -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 5) | ForEach-Object { "    " + $_.Trim() }
  }

Write-Output ""
Write-Output "=== C) accessControl 相关注册表 ==="
foreach ($k in @('HKLM:\SYSTEM\CurrentControlSet\Control\AccessControl',
                 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AccessControl',
                 'HKLM:\SOFTWARE\Microsoft\WindowsRuntime\Server')) {
  if (Test-Path $k) { Write-Output ("  存在: " + $k) } else { Write-Output ("  无: " + $k) }
}

Write-Output ""
Write-Output "=== D) 包的 accessControl 声明（从落盘 manifest 读）==="
$d = 'C:\Program Files\WindowsApps\WindowsWorkload.TextRecognition.Lnl.1_1.2608.951.0_x64__8wekyb3d8bbwe\AppxManifest.xml'
if (Test-Path $d) {
  $x = [xml](Get-Content $d -Raw)
  $x.Package.Properties.InnerXml -split '><' | Where-Object { $_ -match 'ccess|MachineFolder' } | ForEach-Object { "    " + $_ }
}

Write-Output ""
Write-Output "=== E) 尝试为 SYSTEEM 以外用户注册时是否可用开发者模式绕过 ==="
Write-Output ("  当前 AllowDevelopmentWithoutDevLicense = " + (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock' -ErrorAction SilentlyContinue).AllowDevelopmentWithoutDevLicense)
Write-Output "DONE"
