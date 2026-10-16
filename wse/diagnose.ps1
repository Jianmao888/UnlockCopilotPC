$ErrorActionPreference = 'Continue'
$root = 'C:\Users\jianm\Code\DeepseekHarness'
$log = "$root\wse\diagnose.log"
Remove-Item $log -ErrorAction SilentlyContinue
function W($s) { "$(Get-Date -Format 'HH:mm:ss') $s" | Out-File $log -Append -Encoding utf8 }

W "############ 1. DriverStore payload folders"
foreach ($pat in 'mep_camera_component.inf_amd64_*', 'microsofteffectpack.inf_amd64_*', 'mep_audio_component.inf_amd64_*') {
    Get-ChildItem 'C:\Windows\System32\DriverStore\FileRepository' -Directory -Filter $pat -ErrorAction SilentlyContinue | ForEach-Object {
        W ("  DIR " + $_.FullName)
        Get-ChildItem $_.FullName -File -ErrorAction SilentlyContinue | Sort-Object Length -Descending |
            Select-Object -First 15 | ForEach-Object { W ("      {0,12:N0} B  {1}" -f $_.Length, $_.Name) }
    }
}

W ""
W "############ 2. device registry keys (MEP engine device)"
foreach ($id in 'MEP_VEN_8086_DEV_B03E', 'MEP_CAM_VEN_8086_DEV_B03E', 'MEP_AUD_VEN_8086_VOICEFOCUS_V2') {
    $k = "HKLM:\SYSTEM\CurrentControlSet\Enum\ROOT\$id\0000"
    W ("  KEY " + $k + "  exists=" + (Test-Path $k))
    if (Test-Path $k) {
        (Get-ItemProperty $k -ErrorAction SilentlyContinue) | Out-String | ForEach-Object { W ("     " + ($_ -replace "`r`n", "`n     ")) }
    }
}

W ""
W "############ 3. CLSID + interface registration"
$cls = 'HKLM:\SOFTWARE\Classes\CLSID\{C1D740A8-BC18-43F4-A500-6BDF91839FDE}'
W ("  CLSID key exists=" + (Test-Path $cls))
if (Test-Path $cls) {
    (Get-ItemProperty "$cls" -ErrorAction SilentlyContinue) | Out-String | ForEach-Object { W ("     " + $_) }
    (Get-ItemProperty "$cls\InprocServer32" -ErrorAction SilentlyContinue) | Out-String | ForEach-Object { W ("     InprocServer32: " + ($_ -replace "`r`n", " ")) }
    $dll = (Get-ItemProperty "$cls\InprocServer32" -Name '(default)' -ErrorAction SilentlyContinue).'(default)'
    W ("     resolved dll: " + $dll + "  exists=" + (Test-Path $dll))
    if ($dll -and (Test-Path $dll)) {
        $dir = Split-Path $dll -Parent
        W ("     sibling files in " + $dir + ":")
        Get-ChildItem $dir -File -ErrorAction SilentlyContinue | ForEach-Object { W ("        " + $_.Name) }
    }
}
$ifk = Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses' -ErrorAction SilentlyContinue |
    Where-Object { $_.PSChildName -match '(?i)1d813233' }
if ($ifk) { W ("  interface class key present: " + $ifk.PSChildName) } else { W "  interface class key MISSING" }

W ""
W "############ 4. recent errors: Application / Kernel-PnP / Camera"
$since = (Get-Date).AddMinutes(-40)
foreach ($ln in 'Application', 'System') {
    Get-WinEvent -FilterHashtable @{LogName = $ln; StartTime = $since; Level = 1, 2, 3} -ErrorAction SilentlyContinue |
        Where-Object { $_.Message -match 'camera|相机|WindowsEffect|PerceptionCore|openvino|npu|MEP|FrameServer|Studio' } |
        Select-Object -First 12 | ForEach-Object {
            W ("  [" + $ln + "] " + $_.TimeCreated + "  " + $_.ProviderName + "  id=" + $_.Id)
            W ("      " + (($_.Message -replace "`r`n", " ") -replace '\s+', ' ').Substring(0, [Math]::Min(300, $_.Message.Length)))
        }
}
Get-WinEvent -ListLog *camera* -ErrorAction SilentlyContinue | Select-Object -First 5 LogName | ForEach-Object { W ("  camera log: " + $_.LogName) }
Get-WinEvent -ListLog *FrameServer* -ErrorAction SilentlyContinue | Select-Object -First 5 LogName | ForEach-Object { W ("  frameserver log: " + $_.LogName) }

W ""
W "############ 5. NPU presence (expected: none)"
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match '8086&DEV_B03E|8086&DEV_7D1D|8086&DEV_AD1D|8086&DEV_643E' } |
    ForEach-Object { W ("  " + $_.Status + " " + $_.FriendlyName + " " + $_.InstanceId) }
W ("  npu_kmd service: " + (Get-Service -Name 'npu_kmd' -ErrorAction SilentlyContinue).Status)
Get-ChildItem 'C:\Windows\System32\drivers\npu_kmd.sys' -ErrorAction SilentlyContinue | ForEach-Object { W ("  npu_kmd.sys present: " + $_.Length) }
Get-ChildItem 'C:\Windows\System32\DriverStore\FileRepository' -Directory -Filter 'npu*' -ErrorAction SilentlyContinue | ForEach-Object { W ("  npu driverstore: " + $_.Name) }

W ""
W "############ 6. camera device state right now"
Get-PnpDevice -Class Camera,Image -ErrorAction SilentlyContinue | ForEach-Object {
    W ("  " + $_.Status + "  problem=" + $_.Problem + "  " + $_.FriendlyName + "  " + $_.InstanceId)
}
W "DONE"
