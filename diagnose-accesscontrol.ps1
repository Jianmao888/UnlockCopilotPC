# diagnose-accesscontrol.ps1 - ASCII only
$ErrorActionPreference = 'Continue'
$HERE = 'C:\Users\jianm\Code\DeepseekHarness'
$reg  = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock'

Write-Output "=== A) extensions declared by installed packages ==="
foreach ($d in (Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -EA SilentlyContinue |
                Where-Object { $_.Name -match '^WindowsWorkload' })) {
  $mf = Join-Path $d.FullName 'AppxManifest.xml'
  if (-not (Test-Path $mf)) { continue }
  $x = [xml](Get-Content $mf -Raw)
  $cats = @($x.Package.Extensions.Extension | ForEach-Object { $_.Category }) -join ','
  $ac = 'no'
  if ($x.Package.Properties -and $x.Package.Properties.InnerXml -match 'AccessControl') { $ac = 'YES' }
  $short = $d.Name
  if ($short.Length -gt 58) { $short = $short.Substring(0,58) }
  Write-Output ("  " + $short + "  ext=[" + $cats + "]  accessControl=" + $ac)
}

Write-Output ""
Write-Output "=== B) non-elevated install test ==="
$p = Join-Path $HERE 'ai-packages\WindowsWorkload.TextRecognition.Lnl.1_1.2608.951.0_x64.msix'
$cmd = "try { Add-AppxPackage -Path '" + $p + "' -ErrorAction Stop; 'OK' } catch { 'ERR: ' + `$_.Exception.Message }"
$o = & powershell.exe -NoProfile -Command $cmd 2>&1
@($o) | Select-Object -First 4 | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== C) developer mode current value ==="
$v = (Get-ItemProperty $reg -EA SilentlyContinue).AllowDevelopmentWithoutDevLicense
Write-Output ("  AllowDevelopmentWithoutDevLicense = " + $v)

Write-Output ""
Write-Output "=== D) WindowsRuntime Server key (first 10) ==="
& reg.exe query "HKLM\SOFTWARE\Microsoft\WindowsRuntime\Server" 2>&1 | Select-Object -First 10 |
  ForEach-Object { "    " + $_ }

Write-Output ""
Write-Output "=== E) policy keys ==="
foreach ($k in @('HKLM:\SOFTWARE\Policies\Microsoft\Windows\Appx',
                 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx',
                 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModel\StateChange')) {
  if (Test-Path $k) {
    Write-Output ("  EXISTS " + $k)
    Get-ChildItem $k -Recurse -EA SilentlyContinue | Select-Object -First 10 -ExpandProperty Name |
      ForEach-Object { "      " + $_ }
  } else { Write-Output ("  none   " + $k) }
}
Write-Output "DONE"
