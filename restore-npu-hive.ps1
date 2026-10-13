# restore-npu-hive.ps1 - ASCII only; restore original values (5 GUIDs = 0, remove my 3)
$ErrorActionPreference = 'Continue'
$k = 'HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\UnattendSettings\WaaS\Device\Detect\Hardware\NPU'

Write-Output "=== remove the 3 GUIDs I added ==="
foreach ($g in @('A6EEA85C-3D59-4FF8-A673-F88D85107D0C',
                 'B2D7B485-2A57-48EA-9032-07D6BD4B3F87',
                 'FF3398C2-DC93-4A64-8959-EE363977FB1A')) {
    & reg.exe delete "$k" /v "$g" /f 2>&1 | Out-Null
    Write-Output ("  deleted " + $g)
}

Write-Output ""
Write-Output "=== restore the 5 original GUIDs to REG_SZ 0 ==="
foreach ($g in @('C6F8EADC-D476-4AB1-9002-C82AD73DBAC6',
                 'CA8FB730-23E5-46AA-88F2-BC40FA5C0A9E',
                 'D8B960FE-013E-40C4-8B75-BA7CAC2F5E13',
                 'DBCD1198-617B-49D3-843C-B9FF903A6B26',
                 'F55B0D37-9ACE-423C-8868-8F1601C03398')) {
    & reg.exe add "$k" /v "$g" /t REG_SZ /d "0" /f | Out-Null
    Write-Output ("  restored " + $g + " = REG_SZ 0")
}

Write-Output ""
Write-Output "=== final NPU hive ==="
& reg.exe query "$k" 2>&1 | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== restart services ==="
foreach ($s in @('WSAIFabricSvc','StateRepository')) {
    try { Restart-Service $s -Force -ErrorAction Stop; Write-Output ("  " + $s + " restarted") }
    catch { Write-Output ("  " + $s + ": " + $_.Exception.Message) }
}
Start-Sleep -Seconds 8
Get-Service WSAIFabricSvc,StateRepository,AppXSvc -EA SilentlyContinue | ForEach-Object { "  " + $_.Name + " = " + $_.Status }
Write-Output "DONE"
