$ErrorActionPreference = 'Continue'
$w = 'C:\Users\jianm\Code\DeepseekHarness\wse'
$log = "$w\fix3.log"
Remove-Item $log -ErrorAction SilentlyContinue
function W($s) { "$(Get-Date -Format 'HH:mm:ss') $s" | Out-File $log -Append -Encoding utf8 }

W "=== 0. previous attempt result (fix2 sections F/G) ==="
$prev = Get-Content "$w\fix2.log" -ErrorAction SilentlyContinue | Select-String -Pattern '=== F|=== G|id=7|hr：|hr:' 
$prev | Select-Object -Last 8 | ForEach-Object { W ("  " + $_.Line.Trim()) }

W ""
W "=== 1. did PnP generate SWD\DRIVERENUM component devices for MEP? ==="
$swd = 'HKLM:\SYSTEM\CurrentControlSet\Enum\SWD\DRIVERENUM'
$entries = Get-ChildItem $swd -ErrorAction SilentlyContinue
W ("  total SWD\DRIVERENUM devices: " + ($entries | Measure-Object).Count)
$entries | ForEach-Object { W ("     " + $_.PSChildName) }
W ("  any mentioning MEP: " + (($entries | Where-Object { $_.PSChildName -match '(?i)mep' }) | Measure-Object).Count)

W ""
W "=== 2. add CompatibleIDs + Capabilities (as the real template has) ==="
foreach ($id in 'MEP_VEN_8086_DEV_B03E', 'MEP_CAM_VEN_8086_DEV_B03E', 'MEP_AUD_VEN_8086_VOICEFOCUS_V2') {
    $k = "HKLM:\SYSTEM\CurrentControlSet\Enum\ROOT\$id\0000"
    if (-not (Test-Path $k)) { W ("  missing " + $id); continue }
    try {
        New-ItemProperty -Path $k -Name 'CompatibleIDs' -PropertyType MultiString `
            -Value @('SWC\Generic', 'SWD\GenericRaw', 'SWD\Generic') -Force -ErrorAction Stop | Out-Null
        Set-ItemProperty -Path $k -Name 'Capabilities' -Value 208 -Type DWord -ErrorAction Stop
        $c = (Get-ItemProperty $k -Name CompatibleIDs).CompatibleIDs -join ' | '
        W ("  " + $id + "  CompatibleIDs=" + $c + "  Capabilities=" + (Get-ItemProperty $k -Name Capabilities).Capabilities)
    } catch { W ("  FAILED " + $id + " : " + $_.Exception.Message) }
}

W ""
W "=== 3. re-enumerate the devices ==="
foreach ($id in 'MEP_VEN_8086_DEV_B03E', 'MEP_CAM_VEN_8086_DEV_B03E') {
    $inst = "ROOT\$id\0000"
    & pnputil.exe /disable-device $inst *> $null
    Start-Sleep -Seconds 3
    & pnputil.exe /enable-device $inst *> $null
    Start-Sleep -Seconds 2
    $d = Get-PnpDevice -InstanceId $inst -ErrorAction SilentlyContinue
    W ("  " + $id + "  status=" + $d.Status + " problem=" + $d.Problem)
}

W ""
W "=== 4. restart frame server + trigger camera ==="
Restart-Service -Name 'FrameServer' -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5
Remove-Item "$w\fs3.txt" -ErrorAction SilentlyContinue
Start-Process 'microsoft.windows.camera:' -ErrorAction SilentlyContinue
Start-Sleep -Seconds 20

W ""
W "=== 5. newest FsProxy results (target: no longer 0x80070002) ==="
Get-WinEvent -FilterHashtable @{LogName = 'Microsoft-Windows-MF-FrameServer/Camera_FrameServer'; StartTime = (Get-Date).AddMinutes(-4)} -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -eq 7 } | Sort-Object TimeCreated | Select-Object -Last 6 | ForEach-Object {
        $m = (($_.Message -replace "`r`n", ' ') -replace '\s+', ' ')
        $hr = if ($m -match 'hr：\s*([0-9a-fx]+)') { $matches[1] } else { '?' }
        W ("  " + $_.TimeCreated.ToString('HH:mm:ss') + "  hr=" + $hr)
        W ("      " + $m.Substring(0, [Math]::Min(180, $m.Length)))
    }
W ""
W "=== 6. is the camera usable now? (device state) ==="
Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | ForEach-Object { W ("  " + $_.Status + " problem=" + $_.Problem + "  " + $_.FriendlyName) }
W "DONE"
