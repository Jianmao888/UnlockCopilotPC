# fix-npu-type.ps1 - ASCII only; system uses REG_SZ not REG_DWORD
$ErrorActionPreference = 'Continue'
$k = 'HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\UnattendSettings\WaaS\Device\Detect\Hardware\NPU'

Write-Output "=== delete the DWORD entries I wrote ==="
& reg.exe delete "$k" /v "A6EEA85C-3D59-4FF8-A673-F88D85107D0C" /f 2>&1 | Out-Null
& reg.exe delete "$k" /v "B2D7B485-2A57-48EA-9032-07D6BD4B3F87" /f 2>&1 | Out-Null
& reg.exe delete "$k" /v "FF3398C2-DC93-4A64-8959-EE363977FB1A" /f 2>&1 | Out-Null

Write-Output "=== rewrite as REG_SZ (matching the system's own format) ==="
foreach ($g in @('A6EEA85C-3D59-4FF8-A673-F88D85107D0C',
                 'B2D7B485-2A57-48EA-9032-07D6BD4B3F87',
                 'FF3398C2-DC93-4A64-8959-EE363977FB1A',
                 'C6F8EADC-D476-4AB1-9002-C82AD73DBAC6',
                 'CA8FB730-23E5-46AA-88F2-BC40FA5C0A9E',
                 'D8B960FE-013E-40C4-8B75-BA7CAC2F5E13',
                 'DBCD1198-617B-49D3-843C-B9FF903A6B26',
                 'F55B0D37-9ACE-423C-8868-8F1601C03398')) {
    & reg.exe add "$k" /v "$g" /t REG_SZ /d "1" /f | Out-Null
    Write-Output ("  set " + $g + " = REG_SZ 1")
}

Write-Output ""
Write-Output "=== restart services ==="
foreach ($s in @('WSAIFabricSvc','StateRepository')) {
    try { Restart-Service $s -Force -ErrorAction Stop; Write-Output ("  " + $s + " restarted") }
    catch { Write-Output ("  " + $s + " failed: " + $_.Exception.Message) }
}
Start-Sleep -Seconds 10

Write-Output ""
Write-Output "=== final registry ==="
& reg.exe query "$k" 2>&1 | ForEach-Object { "  " + $_ }
Write-Output "DONE"
