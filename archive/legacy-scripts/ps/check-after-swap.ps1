# check-after-swap.ps1 - ASCII only
$ErrorActionPreference = 'Continue'

Write-Output "=== workloads.json currently loaded (first 400 chars) ==="
$gen = 'C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\workloads.json'
$txt = Get-Content $gen -Raw
Write-Output ($txt.Substring(0, [Math]::Min(400, $txt.Length)))
Write-Output ""
Write-Output ("  length = " + $txt.Length)

Write-Output ""
Write-Output "=== RegisterByPackageFamilyName attempts in last 20 min ==="
$since = (Get-Date).AddMinutes(-20)
@(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-AppXDeploymentServer/Operational'; StartTime=$since} -EA SilentlyContinue |
   Where-Object { $_.Id -eq 603 -and $_.Message -match 'RegisterByPackageFamilyName' }) |
  Select-Object -First 30 | ForEach-Object {
    $m = $_.Message
    if ($m -match '(\S+_8wekyb3d8bbwe)') { Write-Output ("  [" + $_.TimeCreated.ToString('HH:mm:ss') + "] " + $Matches[1]) }
  }

Write-Output ""
Write-Output "=== register UUP products for ALL installed WindowsWorkload packages ==="
$base = 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore'
$uup = "$base\UUPProducts"
$apps = 'C:\Program Files\WindowsApps'
$n = 0
foreach ($d in @(Get-ChildItem $apps -Directory -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload\.' })) {
    $mf = Join-Path $d.FullName 'AppxManifest.xml'
    if (-not (Test-Path $mf)) { continue }
    $raw = Get-Content $mf -Raw
    $ids = [regex]::Matches($raw, '<UupProduct\s+Id="([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
    if ($ids.Count -eq 0) { continue }
    $parts = $d.Name -split '_'
    $ver = if ($parts.Count -ge 2) { $parts[1] } else { '0.0.0.0' }
    foreach ($id in $ids) {
        $k = "$uup\$id"
        & reg.exe add "$k" /v Version  /t REG_SZ    /d "$ver" /f 2>&1 | Out-Null
        & reg.exe add "$k" /v IsPinned /t REG_DWORD /d 1 /f 2>&1 | Out-Null
        & reg.exe add "$k\$($d.Name)" /f 2>&1 | Out-Null
        Write-Output ("  $id  <- " + $d.Name)
        $n++
    }
}
Write-Output ("  total product entries added: " + $n)

Write-Output ""
Write-Output "=== pin all WindowsWorkload families ==="
$pinned = "$base\Pinned"
foreach ($d in @(Get-ChildItem $apps -Directory -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload\.' })) {
    $parts = $d.Name -split '_'
    if ($parts.Count -lt 3) { continue }
    $fam = $parts[0] + '_' + $parts[-1]
    & reg.exe add "$pinned\$fam" /f 2>&1 | Out-Null
}
Write-Output ("  Pinned entries: " + @(Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Pinned" -EA SilentlyContinue).Count)

Write-Output ""
Write-Output "=== restart services ==="
foreach ($s in @('WSAIFabricSvc','StateRepository')) {
    try { Restart-Service $s -Force -ErrorAction Stop; Write-Output ("  " + $s + " restarted") } catch { Write-Output ("  " + $s + ": " + $_.Exception.Message) }
}
Start-Sleep -Seconds 20
Write-Output "DONE"
