# find-appx-tasks.ps1 - ASCII only
$ErrorActionPreference = 'Continue'
Write-Output "=== scheduled tasks under AppX / Deployment paths ==="
Get-ScheduledTask -ErrorAction SilentlyContinue |
  Where-Object { $_.TaskPath -match 'Appx|Deployment|WindowsUpdate|InstallService' -or $_.TaskName -match 'Appx|Deploy' } |
  Select-Object TaskPath, TaskName, State | Format-Table -AutoSize

Write-Output ""
Write-Output "=== all tasks with 'AppX' in name/path ==="
Get-ScheduledTask -ErrorAction SilentlyContinue |
  Where-Object { ($_.TaskPath + $_.TaskName) -match 'AppX' } |
  ForEach-Object { "  " + $_.TaskPath + $_.TaskName + "   [" + $_.State + "]" }

Write-Output ""
Write-Output "=== is there a ShellExperienceHost / UserMgr staged-package task? ==="
Get-ScheduledTask -ErrorAction SilentlyContinue |
  Where-Object { ($_.TaskPath + $_.TaskName) -match 'Staged|PackageInstaller|UserMgr' } |
  ForEach-Object { "  " + $_.TaskPath + $_.TaskName + "   [" + $_.State + "]" }

Write-Output ""
Write-Output "=== AppXSvc / AppReadiness service state ==="
foreach ($s in @('AppXSvc','AppReadiness','StateRepository','ClipSVC')) {
  $svc = Get-Service $s -ErrorAction SilentlyContinue
  if ($svc) { "  " + $svc.Name + " = " + $svc.Status + "  (StartType " + $svc.StartType + ")" }
}

Write-Output ""
Write-Output "=== registry marker for logon-time package install ==="
$k = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\EndOfStagedPackages'
foreach ($p in @(
  'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore',
  'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\InboxApplications')) {
  if (Test-Path $p) { Write-Output ("  EXISTS " + $p) } else { Write-Output ("  none   " + $p) }
}
Write-Output ""
Write-Output "=== pending/staged entries for WindowsWorkload ==="
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore' -Recurse -EA SilentlyContinue |
  Where-Object { $_.Name -match 'WindowsWorkload' } |
  Select-Object -First 20 -ExpandProperty Name | ForEach-Object { "  " + $_ }
Write-Output "DONE"
