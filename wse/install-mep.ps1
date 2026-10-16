$ErrorActionPreference = 'Continue'
$root = 'C:\Users\jianm\Code\DeepseekHarness'
$mep = "$root\wse\mep"
$log = "$root\wse\install-attempt.log"
Remove-Item $log -ErrorAction SilentlyContinue
function W($s) { "$(Get-Date -Format 'HH:mm:ss') $s" | Out-File $log -Append -Encoding utf8 }

W "=== A. read the camera-component registry contract (EffectsCMS.AddReg) ==="
$inf = Get-Content "$mep\Drivers\CameraComponent\mep_camera_component.inf" -Raw
($inf -split "`n") | Select-Object -Skip 30 | ForEach-Object { W ("  " + $_.TrimEnd()) }

W ""
W "=== B. Xiaomi extension INF ==="
Get-Content "$mep\Drivers\Xiaomi_MEP_Extension_INF_v20286\SpitExMEP.inf" | ForEach-Object { W ("  " + $_.TrimEnd()) }

W ""
W "=== C. snapshot drivers before ==="
(& pnputil.exe /enum-drivers) | Out-File "$root\wse\drivers-before.txt" -Encoding utf8
W ("  saved drivers-before.txt lines=" + (Get-Content "$root\wse\drivers-before.txt" | Measure-Object).Count)

W ""
W "=== D. install the MEP driver package (WHQL-signed) ==="
foreach ($grp in 'AudioComponent', 'CameraComponent', 'ExtensionINF', 'Xiaomi_MEP_Extension_INF_v20286') {
    foreach ($f in Get-ChildItem "$mep\Drivers\$grp" -Filter *.inf) {
        W ("  --- " + $f.FullName.Replace("$mep\", ""))
        (& pnputil.exe /add-driver $f.FullName /install 2>&1) | ForEach-Object { W ("      " + $_) }
    }
}

W ""
W "=== E. are the software devices present now? ==="
foreach ($h in 'SWC\MEP_VEN_8086_DEV_B03E', 'SWC\MEP_CAM&VEN_8086_DEV_B03E') {
    $d = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like "*$h*" }
    if ($d) { $d | ForEach-Object { W ("  FOUND " + $_.Status + "  " + $_.Class + "  " + $_.FriendlyName + "  " + $_.InstanceId) } }
    else { W ("  not present: " + $h) }
}
W "  --- all SoftwareComponent devices ---"
Get-PnpDevice -Class SoftwareComponent -ErrorAction SilentlyContinue |
    ForEach-Object { W ("  " + $_.Status + "  " + $_.FriendlyName + "  " + $_.InstanceId) }

W ""
W "=== F. driver package registered? ==="
(& pnputil.exe /enum-drivers) | Select-String -Pattern 'oem\d+\.inf|MicrosoftEffectPack|mep_|SpitExMEP|8086' -Context 0,3 |
    ForEach-Object { W ("  " + $_.Line.Trim()) }

W ""
W "=== G. Studio Effects related registry / settings surface ==="
foreach ($k in 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CameraEffects',
               'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\StudioEffects',
               'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Camera',
               'HKLM:\SYSTEM\CurrentControlSet\Control\Camera') {
    if (Test-Path $k) {
        W ("  KEY " + $k)
        Get-ItemProperty $k -ErrorAction SilentlyContinue | Out-String | ForEach-Object { W ("      " + ($_ -replace "`r`n", "`n      ")) }
        Get-ChildItem $k -ErrorAction SilentlyContinue | ForEach-Object { W ("      sub: " + $_.PSChildName) }
    } else { W ("  (absent) " + $k) }
}
W "DONE"
