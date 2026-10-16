$ErrorActionPreference = 'Continue'
$w = 'C:\Users\jianm\Code\DeepseekHarness\wse'
$log = "$w\procmon.log"
Remove-Item $log -ErrorAction SilentlyContinue
function W($s) { "$(Get-Date -Format 'HH:mm:ss') $s" | Out-File $log -Append -Encoding utf8 }

W "=== 1. download Process Monitor (Sysinternals) via proxy ==="
$zip = "$w\ProcessMonitor.zip"
& curl.exe -sSL -x http://127.0.0.1:7890 -o $zip 'https://download.sysinternals.com/files/ProcessMonitor.zip' 2>&1 | ForEach-Object { W ("  " + $_) }
W ("  zip: " + (Test-Path $zip) + "  size=" + (Get-Item $zip -ErrorAction SilentlyContinue).Length)
if (-not (Test-Path $zip)) { W "ABORT: download failed"; W "DONE"; exit 1 }

Remove-Item "$w\pm" -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive $zip -DestinationPath "$w\pm" -Force
$pm = Get-ChildItem "$w\pm" -Filter 'Procmon*.exe' | Select-Object -First 1 -ExpandProperty FullName
W ("  procmon: " + $pm)
if (-not $pm) { W "ABORT: Procmon exe not found"; W "DONE"; exit 1 }

W ""
W "=== 2. start capture (quiet, backing file) ==="
$pml = "$w\cap.pml"
Remove-Item $pml -ErrorAction SilentlyContinue
Start-Process -FilePath $pm -ArgumentList '/Quiet', '/Minimized', '/AcceptEula', '/BackingFile', $pml -WindowStyle Hidden
Start-Sleep -Seconds 8
W ("  capture started, pml exists=" + (Test-Path $pml))

W ""
W "=== 3. trigger the camera with Studio Effects enabled ==="
Start-Process 'microsoft.windows.camera:' -ErrorAction SilentlyContinue
Start-Sleep -Seconds 20

W ""
W "=== 4. stop capture ==="
& $pm /Terminate | Out-Null
Start-Sleep -Seconds 8

W ""
W "=== 5. convert to CSV ==="
$csv = "$w\cap.csv"
Remove-Item $csv -ErrorAction SilentlyContinue
& $pm /OpenLog $pml /SaveAs $csv | Out-Null
Start-Sleep -Seconds 25
W ("  csv exists=" + (Test-Path $csv) + "  size=" + [math]::Round((Get-Item $csv -ErrorAction SilentlyContinue).Length / 1MB, 1) + " MB")

W ""
W "=== 6. filter: NAME NOT FOUND for effect-related paths ==="
$out = "$w\procmon-notfound.txt"
if (Test-Path $csv) {
    & findstr.exe /i /c:"NAME NOT FOUND" $csv > $out 2>$null
    W ("  raw NOT FOUND lines: " + (Get-Content $out -ErrorAction SilentlyContinue | Measure-Object).Count)
    $hits = Get-Content $out -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '(?i)perception|mep|studio|effect|openvino|models|onnx|driverstore|mepassets' }
    W ("  filtered (effect-related): " + ($hits | Measure-Object).Count)
    $hits | Select-Object -First 40 | ForEach-Object { W ("    " + $_) }
    # also show the top missing paths overall, normalized
    W "  --- most common missing paths (top 25) ---"
    Get-Content $out -ErrorAction SilentlyContinue |
        ForEach-Object { ($_ -split ',')[-2] } |
        Where-Object { $_ } | Group-Object | Sort-Object Count -Descending |
        Select-Object -First 25 | ForEach-Object { W ("    {0,6}  {1}" -f $_.Count, $_.Name) }
}
W "DONE"
