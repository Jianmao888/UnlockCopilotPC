$ErrorActionPreference = 'Continue'
$w = 'C:\Users\jianm\Code\DeepseekHarness\wse'
$log = "$w\A-B-run.log"
Remove-Item $log -ErrorAction SilentlyContinue
function W($s) { "$(Get-Date -Format 'HH:mm:ss') $s" | Out-File $log -Append -Encoding utf8 }

W "=== compile MepDev ==="
(& 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe' /nologo /target:exe /out:"$w\MepDev.exe" "$w\MepDev.cs" 2>&1) |
    ForEach-Object { W ("  " + $_) }

W ""
W "=== A: create the software-component devices ==="
(& "$w\MepDev.exe" 2>&1) | ForEach-Object { W ("  " + $_) }

W ""
W "=== A results ==="
$devs = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match 'MEP_VEN_8086|MEP_CAM|MEP_AUD' }
if ($devs) {
    $devs | ForEach-Object {
        W ("  " + $_.Status + "  " + $_.Class + "  " + $_.FriendlyName + "  " + $_.InstanceId)
        Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_DriverInfPath','DEVPKEY_Device_ProblemCode' -ErrorAction SilentlyContinue |
            ForEach-Object { W ("       " + $_.KeyName + " = " + $_.Data) }
    }
} else { W "  (no MEP devices)" }

W "  --- KSCATEGORY_WINDOWS_CAMERAEFFECTS interface ---"
$iface = Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses' -ErrorAction SilentlyContinue |
    Where-Object { $_.PSChildName -match '(?i)1d813233' }
if ($iface) { $iface | ForEach-Object { W ("    FOUND " + $_.PSChildName) } } else { W "    not registered" }

W "  --- effects CLSID ---"
$cls = Test-Path 'HKLM:\SOFTWARE\Classes\CLSID\{C1D740A8-BC18-43F4-A500-6BDF91839FDE}'
W ("    CLSID {C1D740A8-...} present: " + $cls)

W "  --- Media Source DLL landed? ---"
$dll = Get-ChildItem 'C:\Windows\System32\DriverStore\FileRepository' -Recurse -Filter 'WindowsEffectsCameraMediaSource.dll' -ErrorAction SilentlyContinue | Select-Object -First 2
if ($dll) { $dll | ForEach-Object { W ("    " + $_.FullName) } } else { W "    not found" }

W ""
W "=== B: associate our camera (FSMEnableMsEffects = 1) ==="
$backup = "$w\camera-keys-backup.reg"
(& reg.exe export 'HKLM\SYSTEM\CurrentControlSet\Control\DeviceClasses\{E5323777-F976-4f5b-9B55-B94699C46E44}' $backup /y) | Out-Null
W ("  backup: " + (Test-Path $backup))

$ifaceKey = 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\{E5323777-F976-4f5b-9B55-B94699C46E44}\##?#USB#VID_1BCF&PID_2D03&MI_00#6&37d1e05&0&0000#{e5323777-f976-4f5b-9b55-b94699c46e44}\#GLOBAL'
foreach ($k in @($ifaceKey, "HKLM:\SYSTEM\CurrentControlSet\Enum\USB\VID_1BCF&PID_2D03&MI_00\6&37D1E05&0&0000\Device Parameters")) {
    try {
        if (-not (Test-Path $k)) { New-Item -Path $k -Force | Out-Null }
        Set-ItemProperty -Path $k -Name 'FSMEnableMsEffects' -Value 1 -Type DWord -ErrorAction Stop
        $v = (Get-ItemProperty -Path $k -Name 'FSMEnableMsEffects' -ErrorAction SilentlyContinue).FSMEnableMsEffects
        W ("  set FSMEnableMsEffects=" + $v + "  at " + $k)
    } catch { W ("  FAILED at " + $k + " : " + $_.Exception.Message) }
}

W ""
W "=== final: any Studio Effects surface? ==="
foreach ($k in 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CameraEffects',
               'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\StudioEffects',
               'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsStudioEffects') {
    W ("  " + $k + " exists=" + (Test-Path $k))
}
W "DONE"
