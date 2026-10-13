# check-pinned.ps1 - ASCII only
$ErrorActionPreference = 'Continue'
$base = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore'

Write-Output "=== AppxAllUserStore subkeys ==="
Get-ChildItem $base -EA SilentlyContinue | ForEach-Object { "  " + $_.PSChildName }

Write-Output ""
Write-Output "=== Pinned key ==="
$p = Join-Path $base 'Pinned'
if (Test-Path $p) {
    $kids = @(Get-ChildItem $p -EA SilentlyContinue)
    Write-Output ("  exists, " + $kids.Count + " entries")
    $kids | Select-Object -First 25 | ForEach-Object { "    " + $_.PSChildName }
} else { Write-Output "  (does not exist)" }

Write-Output ""
Write-Output "=== Applications: any WindowsWorkload? ==="
$a = Join-Path $base 'Applications'
$wl = @(Get-ChildItem $a -EA SilentlyContinue | Where-Object { $_.PSChildName -match 'WindowsWorkload' })
Write-Output ("  count = " + $wl.Count)
$wl | ForEach-Object {
    Write-Output ("    " + $_.PSChildName)
    $v = Get-ItemProperty $_.PSPath -EA SilentlyContinue
    if ($v) { $v.PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' } | ForEach-Object { "        " + $_.Name + " = " + $_.Value } }
}

Write-Output ""
Write-Output "=== Staged: WindowsWorkload ==="
$s = Join-Path $base 'Staged'
@(Get-ChildItem $s -EA SilentlyContinue | Where-Object { $_.PSChildName -match 'WindowsWorkload' }) | ForEach-Object { "  " + $_.PSChildName }

Write-Output ""
Write-Output "=== appdata folder for model cache ==="
$ad = 'C:\ProgramData\Microsoft\Windows\AppRepository\Families\ApplicationData'
if (Test-Path $ad) {
    $w = @(Get-ChildItem $ad -EA SilentlyContinue | Where-Object { $_.Name -match 'WindowsWorkload' })
    Write-Output ("  ApplicationData entries: " + $w.Count)
    $w | ForEach-Object { "    " + $_.Name }
} else { Write-Output "  ApplicationData root does not exist" }

Write-Output ""
Write-Output "=== AppRepository\\Families ==="
$fam = 'C:\ProgramData\Microsoft\Windows\AppRepository\Families'
if (Test-Path $fam) {
    @(Get-ChildItem $fam -EA SilentlyContinue | Where-Object { $_.Name -match 'WindowsWorkload' }) | ForEach-Object { "  " + $_.Name }
} else { Write-Output "  (Families root missing)" }
Write-Output "DONE"
