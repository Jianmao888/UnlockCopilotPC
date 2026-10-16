# trigger-appreadiness.ps1 - ASCII only
$ErrorActionPreference = 'Continue'
Write-Output "=== before ==="
Get-Service AppReadiness, AppXSvc, StateRepository | ForEach-Object { "  " + $_.Name + " = " + $_.Status + " (" + $_.StartType + ")" }

Write-Output ""
Write-Output "=== start AppReadiness ==="
try {
  Start-Service AppReadiness -ErrorAction Stop
  Write-Output "  started"
} catch { Write-Output ("  ERR: " + $_.Exception.Message) }
Start-Sleep -Seconds 20
Get-Service AppReadiness | ForEach-Object { "  AppReadiness = " + $_.Status }

Write-Output ""
Write-Output "=== wait and check packages for current user ==="
for ($i = 1; $i -le 6; $i++) {
  Start-Sleep -Seconds 20
  $n = @(Get-AppxPackage -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' }).Count
  Write-Output ("  [" + $i + "] WindowsWorkload packages for current user: " + $n)
  if ($n -ge 7) { break }
}

Write-Output ""
Write-Output "=== final: all users view ==="
Get-AppxPackage -AllUsers -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' } |
  Select-Object Name, Version, Status | Format-Table -AutoSize

Write-Output ""
Write-Output "=== recent AppX deployment events ==="
Get-WinEvent -LogName 'Microsoft-Windows-AppXDeploymentServer/Operational' -MaxEvents 12 -EA SilentlyContinue |
  Select-Object -First 8 | ForEach-Object {
    $m = $_.Message
    if ($m.Length -gt 150) { $m = $m.Substring(0,150) }
    Write-Output ("  [" + $_.Id + "] " + ($m -replace "`r?`n"," "))
  }
Write-Output "DONE"
