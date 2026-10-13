# diag-store.ps1 - ASCII only
$ErrorActionPreference = 'Continue'
$base = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore'
$apps = Join-Path $base 'Applications'

Write-Output "=== sample of Applications entries (non-WindowsWorkload) ==="
$all = @(Get-ChildItem $apps -EA SilentlyContinue)
Write-Output ("  total entries: " + $all.Count)
$n = 0
foreach ($e in $all) {
    if ($e.PSChildName -match '^WindowsWorkload') { continue }
    $v = Get-ItemProperty $e.PSPath -EA SilentlyContinue
    $names = @($v.PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' } | ForEach-Object { $_.Name })
    Write-Output ("  " + $e.PSChildName)
    Write-Output ("      values: " + ($names -join ', '))
    $n++
    if ($n -ge 6) { break }
}

Write-Output ""
Write-Output "=== count of entries having RequiresAllUserStoreRefresh ==="
$withFlag = 0; $withoutFlag = 0
foreach ($e in $all) {
    $v = Get-ItemProperty $e.PSPath -EA SilentlyContinue
    if ($v -and ($v.PSObject.Properties.Name -contains 'RequiresAllUserStoreRefresh')) { $withFlag++ } else { $withoutFlag++ }
}
Write-Output ("  with flag   : " + $withFlag)
Write-Output ("  without flag: " + $withoutFlag)

Write-Output ""
Write-Output "=== AI-related events (last 30 min) ==="
$since = (Get-Date).AddMinutes(-30)
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-AppXDeploymentServer/Operational'; StartTime=$since} -EA SilentlyContinue |
  Select-Object -First 12 | ForEach-Object {
    $m = $_.Message
    if ($m.Length -gt 160) { $m = $m.Substring(0,160) }
    Write-Output ("  [" + $_.TimeCreated.ToString('HH:mm:ss') + " id=" + $_.Id + "] " + ($m -replace "`r?`n", " "))
  }

Write-Output ""
Write-Output "=== WSAIFabricSvc events ==="
Get-WinEvent -LogName 'Application' -MaxEvents 200 -EA SilentlyContinue |
  Where-Object { $_.ProviderName -match 'WSAIFabric|Workload|AIFabric' } |
  Select-Object -First 8 | ForEach-Object {
    $m = $_.Message; if ($m.Length -gt 160) { $m = $m.Substring(0,160) }
    Write-Output ("  [" + $_.TimeCreated.ToString('HH:mm:ss') + "] " + ($m -replace "`r?`n"," "))
  }
Write-Output "DONE"
