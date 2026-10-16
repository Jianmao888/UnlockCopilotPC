$ErrorActionPreference = 'Continue'
$w = 'C:\Users\jianm\Code\DeepseekHarness\wse'
$log = "$w\fix2.log"
Remove-Item $log -ErrorAction SilentlyContinue
function W($s) { "$(Get-Date -Format 'HH:mm:ss') $s" | Out-File $log -Append -Encoding utf8 }

W "=== A. pick a real, properly-installed software component as template ==="
$tmpl = Get-PnpDevice -Class SoftwareComponent -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like 'SWD\DRIVERENUM*' } | Select-Object -First 3
$tmpl | ForEach-Object { W ("  candidate: " + $_.FriendlyName + "  " + $_.InstanceId) }

$t = $tmpl | Select-Object -First 1
if ($t) {
    $tkey = "HKLM:\SYSTEM\CurrentControlSet\Enum\$($t.InstanceId)"
    W ("  TEMPLATE KEY: " + $tkey)
    W "  --- values ---"
    (Get-ItemProperty $tkey -ErrorAction SilentlyContinue).PSObject.Properties |
        Where-Object { $_.Name -notlike 'PS*' } | ForEach-Object { W ("     " + $_.Name + " = " + $_.Value) }
    W "  --- subkeys ---"
    Get-ChildItem $tkey -ErrorAction SilentlyContinue | ForEach-Object { W ("     " + $_.PSChildName) }
    $propKey = Join-Path $tkey 'Properties'
    if (Test-Path $propKey) {
        W "  --- Properties structure (first 12) ---"
        Get-ChildItem $propKey -ErrorAction SilentlyContinue | Select-Object -First 12 | ForEach-Object {
            $set = $_.PSChildName
            Get-ChildItem $_.PSPath -ErrorAction SilentlyContinue | ForEach-Object {
                $vals = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).PSObject.Properties |
                        Where-Object { $_.Name -notlike 'PS*' } | ForEach-Object { $_.Name }
                W ("     " + $set + "\" + $_.PSChildName + "   values: " + ($vals -join ', '))
            }
        }
    }
    & reg.exe export $tkey "$w\template-device.reg" /y | Out-Null
    W ("  exported -> template-device.reg  (" + (Test-Path "$w\template-device.reg") + ")")
}

W ""
W "=== B. our devices: current values ==="
foreach ($id in 'MEP_VEN_8086_DEV_B03E', 'MEP_CAM_VEN_8086_DEV_B03E') {
    $k = "HKLM:\SYSTEM\CurrentControlSet\Enum\ROOT\$id\0000"
    W ("  " + $id)
    (Get-ItemProperty $k -ErrorAction SilentlyContinue).PSObject.Properties |
        Where-Object { $_.Name -notlike 'PS*' } | ForEach-Object { W ("     " + $_.Name + " = " + $_.Value) }
    Get-ChildItem $k -ErrorAction SilentlyContinue | ForEach-Object { W ("     [subkey] " + $_.PSChildName) }
}

W ""
W "=== C. apply missing values (FriendlyName, plain DeviceDesc, shared ContainerID) ==="
$sharedCid = '{11111111-2222-3333-4444-555555555555}'
$apply = @{
    'MEP_VEN_8086_DEV_B03E'             = @{ FriendlyName = 'Windows Studio Effects Driver'; DeviceDesc = 'Windows Studio Effects Driver' }
    'MEP_CAM_VEN_8086_DEV_B03E'         = @{ FriendlyName = 'Windows Camera Effects';        DeviceDesc = 'Windows Camera Effects' }
    'MEP_AUD_VEN_8086_VOICEFOCUS_V2'    = @{ FriendlyName = 'MSVoiceClarity APO';            DeviceDesc = 'MSVoiceClarity APO' }
}
foreach ($id in $apply.Keys) {
    $k = "HKLM:\SYSTEM\CurrentControlSet\Enum\ROOT\$id\0000"
    if (-not (Test-Path $k)) { continue }
    foreach ($n in $apply[$id].Keys) {
        try { Set-ItemProperty -Path $k -Name $n -Value $apply[$id][$n] -Type String -ErrorAction Stop; W ("  set " + $id + "." + $n) }
        catch { W ("  FAILED " + $id + "." + $n + " : " + $_.Exception.Message) }
    }
    try { Set-ItemProperty -Path $k -Name 'ContainerID' -Value $sharedCid -Type String -ErrorAction Stop; W ("  set " + $id + ".ContainerID = " + $sharedCid) }
    catch { W ("  FAILED ContainerID " + $id + " : " + $_.Exception.Message) }
}

W ""
W "=== D. re-enumerate devices so PnP can (re)build the property store ==="
foreach ($id in 'MEP_VEN_8086_DEV_B03E', 'MEP_CAM_VEN_8086_DEV_B03E') {
    $inst = "ROOT\$id\0000"
    (& pnputil.exe /disable-device $inst 2>&1) | Select-Object -Last 1 | ForEach-Object { W ("  disable: " + $_) }
    Start-Sleep -Seconds 3
    (& pnputil.exe /enable-device $inst 2>&1) | Select-Object -Last 1 | ForEach-Object { W ("  enable : " + $_) }
}
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match 'MEP_VEN_8086|MEP_CAM' } |
    ForEach-Object { W ("  state: " + $_.Status + " problem=" + $_.Problem + "  " + $_.InstanceId) }

W ""
W "=== E. did the property store appear now? ==="
$k = 'HKLM:\SYSTEM\CurrentControlSet\Enum\ROOT\MEP_CAM_VEN_8086_DEV_B03E\0000'
foreach ($p in 'FriendlyName', 'DeviceDesc', 'ContainerID') {
    $v = (Get-ItemProperty $k -Name $p -ErrorAction SilentlyContinue).$p
    W ("  " + $p + " = " + $v)
}
W ("  Properties subkey exists = " + (Test-Path "$k\Properties"))

W ""
W "=== F. restart frame server and trigger camera ==="
Restart-Service -Name 'FrameServer' -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5
Start-Process 'microsoft.windows.camera:' -ErrorAction SilentlyContinue
Start-Sleep -Seconds 18

W ""
W "=== G. newest FsProxy result (was 0x80070002) ==="
Get-WinEvent -FilterHashtable @{LogName = 'Microsoft-Windows-MF-FrameServer/Camera_FrameServer'; StartTime = (Get-Date).AddMinutes(-3)} -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -eq 7 } | Sort-Object TimeCreated | Select-Object -Last 5 | ForEach-Object {
        $m = (($_.Message -replace "`r`n", ' ') -replace '\s+', ' ')
        W ("  " + $_.TimeCreated.ToString('HH:mm:ss') + "  " + $m.Substring(0, [Math]::Min(200, $m.Length)))
    }
W "DONE"
