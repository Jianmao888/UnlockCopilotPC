# find-oneocr.ps1 - ASCII only; locate oneocr.dll on this machine
$ErrorActionPreference = 'Continue'
Write-Output "=== Snipping Tool / ScreenSketch packages ==="
$dirs = @(Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -EA SilentlyContinue |
          Where-Object { $_.Name -match 'ScreenSketch|SnippingTool' })
if ($dirs.Count -eq 0) { Write-Output "  (none)" }
foreach ($p in $dirs) {
    Write-Output ("--- " + $p.Name + " ---")
    $hits = @(Get-ChildItem $p.FullName -Recurse -Include 'oneocr*','onnxruntime.dll' -EA SilentlyContinue)
    if ($hits.Count -eq 0) { Write-Output "    (no oneocr / onnxruntime)" }
    foreach ($h in $hits) {
        Write-Output ("    {0,10:N2} MB  {1}" -f ($h.Length/1MB), $h.FullName.Substring($p.FullName.Length+1))
    }
}

Write-Output ""
Write-Output "=== full search: oneocr.dll under WindowsApps + System32 ==="
$all = @(Get-ChildItem 'C:\Program Files\WindowsApps','C:\Windows\System32' -Recurse -Filter 'oneocr.dll' -EA SilentlyContinue)
if ($all.Count -eq 0) { Write-Output "  (not found)" }
foreach ($f in $all) {
    Write-Output ("    {0,10:N2} MB  {1}" -f ($f.Length/1MB), $f.FullName)
}

Write-Output ""
Write-Output "=== full search: oneocr.onemodel ==="
$m = @(Get-ChildItem 'C:\Program Files\WindowsApps','C:\Windows\System32' -Recurse -Filter 'oneocr.onemodel' -EA SilentlyContinue)
if ($m.Count -eq 0) { Write-Output "  (not found)" }
foreach ($f in $m) {
    Write-Output ("    {0,10:N2} MB  {1}" -f ($f.Length/1MB), $f.FullName)
}
Write-Output "DONE"
