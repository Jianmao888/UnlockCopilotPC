$ErrorActionPreference = 'Continue'
$w = 'C:\Users\jianm\Code\DeepseekHarness\wse'
$log = "$w\fix1.log"
Remove-Item $log -ErrorAction SilentlyContinue
function W($s) { "$(Get-Date -Format 'HH:mm:ss') $s" | Out-File $log -Append -Encoding utf8 }

$eff = 'C:\Windows\System32\DriverStore\FileRepository\microsofteffectpack.inf_amd64_a8654f8af65b3ccb'
$cam = 'C:\Windows\System32\DriverStore\FileRepository\mep_camera_component.inf_amd64_bb062a76c6d49e64'

W "=== 1. set MEPAssets on both MEP device keys ==="
foreach ($id in 'MEP_VEN_8086_DEV_B03E', 'MEP_CAM_VEN_8086_DEV_B03E') {
    $k = "HKLM:\SYSTEM\CurrentControlSet\Enum\ROOT\$id\0000"
    try {
        Set-ItemProperty -Path $k -Name 'MEPAssets' -Value ($eff + '\') -Type String -ErrorAction Stop
        W ("  set MEPAssets at " + $id + " = " + (Get-ItemProperty $k -Name MEPAssets).MEPAssets)
    } catch { W ("  FAILED " + $id + " : " + $_.Exception.Message) }
}

W ""
W "=== 2. take ownership of the camera-component folder and copy dependencies ==="
(& takeown.exe /f $cam /r /d y) 2>&1 | ForEach-Object { W ("  " + $_) }
(& icacls.exe $cam /grant '*S-1-5-32-544:F' /t /c) 2>&1 | Select-Object -Last 3 | ForEach-Object { W ("  " + $_) }

$files = 'PerceptionCore.dll', 'PerceptionCoreResources.dll', 'openvino.dll',
         'openvino_onnx_frontend.dll', 'openvino_intel_npu_plugin.dll',
         'ps-onnxruntime.dll', 'onnxruntime_providers_openvino.dll',
         'onnxruntime_providers_shared.dll', 'tbb12.dll'
foreach ($f in $files) {
    try {
        Copy-Item (Join-Path $eff $f) (Join-Path $cam $f) -Force -ErrorAction Stop
        W ("  copied " + $f)
    } catch { W ("  FAILED " + $f + " : " + $_.Exception.Message) }
}
W "  --- now in the camera-component folder ---"
Get-ChildItem $cam -File | ForEach-Object { W ("     {0,12:N0} B  {1}" -f $_.Length, $_.Name) }

W ""
W "=== 3. restart the camera frame server ==="
$svc = Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'FrameServer' -or $_.DisplayName -match 'Camera' }
$svc | ForEach-Object { W ("  service: " + $_.Name + "  " + $_.Status + "  " + $_.DisplayName) }
foreach ($n in @('FrameServer', 'Windows Camera Frame Server', 'Wcmsvc')) {
    $s = Get-Service -Name $n -ErrorAction SilentlyContinue
    if ($s) {
        try { Restart-Service -Name $n -Force -ErrorAction Stop; W ("  restarted " + $n) }
        catch { W ("  restart failed " + $n + " : " + $_.Exception.Message) }
    }
}

W ""
W "=== 4. newest camera frame server events (last 5 min) ==="
Start-Sleep -Seconds 8
$since = (Get-Date).AddMinutes(-5)
Get-WinEvent -FilterHashtable @{LogName = 'Microsoft-Windows-MF-FrameServer/Camera_FrameServer'; StartTime = $since} -ErrorAction SilentlyContinue |
    Sort-Object TimeCreated | Select-Object -Last 14 | ForEach-Object {
        $m = (($_.Message -replace "`r`n", ' ') -replace '\s+', ' ')
        W ("  " + $_.TimeCreated.ToString('HH:mm:ss') + " id=" + $_.Id + " " + $m.Substring(0, [Math]::Min(220, $m.Length)))
    }
W "DONE"
