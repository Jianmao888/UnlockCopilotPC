# diag-deploy.ps1 - ASCII only
$ErrorActionPreference = 'Continue'

Write-Output "=== all WindowsWorkload-related deployment events (last 6h) ==="
$since = (Get-Date).AddHours(-6)
$ev = @(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-AppXDeploymentServer/Operational'; StartTime=$since} -EA SilentlyContinue |
        Where-Object { $_.Message -match 'WindowsWorkload' })
Write-Output ("  count = " + $ev.Count)
foreach ($e in ($ev | Select-Object -First 25)) {
    $m = $e.Message
    if ($m.Length -gt 230) { $m = $m.Substring(0,230) }
    Write-Output ("  [" + $e.TimeCreated.ToString('MM-dd HH:mm:ss') + " id=" + $e.Id + " lvl=" + $e.LevelDisplayName + "]")
    Write-Output ("      " + ($m -replace "`r?`n", " "))
}

Write-Output ""
Write-Output "=== any ERROR/CRITICAL deployment events (last 2h) ==="
$since2 = (Get-Date).AddHours(-2)
@(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-AppXDeploymentServer/Operational'; StartTime=$since2; Level=2} -EA SilentlyContinue) |
  Select-Object -First 15 | ForEach-Object {
    $m = $_.Message; if ($m.Length -gt 240) { $m = $m.Substring(0,240) }
    Write-Output ("  [" + $_.TimeCreated.ToString('HH:mm:ss') + " id=" + $_.Id + "] " + ($m -replace "`r?`n"," "))
  }

Write-Output ""
Write-Output "=== current Applications entries for WindowsWorkload ==="
$apps = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Applications'
@(Get-ChildItem $apps -EA SilentlyContinue | Where-Object { $_.PSChildName -match 'WindowsWorkload' }) | ForEach-Object {
    Write-Output ("  " + $_.PSChildName)
    $v = Get-ItemProperty $_.PSPath -EA SilentlyContinue
    $v.PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' } | ForEach-Object { "      " + $_.Name + " = " + $_.Value }
}

Write-Output ""
Write-Output "=== packages registered for LocalService (S-1-5-19) ? ==="
$sid = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\S-1-5-19'
Write-Output ("  S-1-5-19 key exists: " + (Test-Path $sid))
if (Test-Path $sid) {
    Get-ChildItem $sid -EA SilentlyContinue | ForEach-Object { "    " + $_.PSChildName }
}
Write-Output "DONE"
