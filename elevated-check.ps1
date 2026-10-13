# elevated-check.ps1 - ASCII only
$ErrorActionPreference = 'Continue'
Write-Output "=== AllUsers view ==="
$all = @(Get-AppxPackage -AllUsers -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' })
Write-Output ("  count = " + $all.Count)
$all | Select-Object Name, Version, Status | Format-Table -AutoSize

Write-Output "=== provisioned ==="
$prov = @(Get-AppxProvisionedPackage -Online -EA SilentlyContinue | Where-Object { $_.DisplayName -match 'WindowsWorkload' })
Write-Output ("  count = " + $prov.Count)
$prov | Select-Object DisplayName, Version | Format-Table -AutoSize

Write-Output "=== on-disk dirs ==="
$d1 = @(Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -EA SilentlyContinue | Where-Object { $_.Name -match 'WindowsWorkload' })
Write-Output ("  WindowsApps = " + $d1.Count)
$d1 | Select-Object -ExpandProperty Name

Write-Output ""
Write-Output "=== AppReadiness ==="
Get-Service AppReadiness | ForEach-Object { "  " + $_.Name + " = " + $_.Status + " (" + $_.StartType + ")" }
Write-Output "DONE"
