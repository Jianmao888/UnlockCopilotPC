# try-both-hacks.ps1 - ASCII only
# Test 1: register UUP products (official format from add-OemPreload.ps1)
# Test 2: write official Copilot+ silicon GUID into NPU detection hive
$ErrorActionPreference = 'Continue'

Write-Output "=================== BEFORE ==================="
$uup = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\UUPProducts'
Write-Output ("UUPProducts exists: " + (Test-Path $uup))
$npu = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\UnattendSettings\WaaS\Device\Detect\Hardware\NPU'
Write-Output ("NPU detect hive exists: " + (Test-Path $npu))

Write-Output ""
Write-Output "=================== TEST 1: UUPProducts ==================="
# 从 WindowsApps 里读带 <UupProduct> 的 manifest
$installed = @(Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -EA SilentlyContinue |
               Where-Object { $_.Name -match '^WindowsWorkload\.' })
Write-Output ("WindowsWorkload dirs: " + $installed.Count)

$regs = @()
foreach ($d in $installed) {
    $mf = Join-Path $d.FullName 'AppxManifest.xml'
    if (-not (Test-Path $mf)) { continue }
    $raw = Get-Content $mf -Raw
    $ids = [regex]::Matches($raw, '<UupProduct\s+Id="([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
    if ($ids.Count -eq 0) { continue }
    $parts = $d.Name -split '_'
    $ver = if ($parts.Count -ge 2) { $parts[1] } else { '0.0.0.0' }
    foreach ($id in $ids) {
        $regs += [pscustomobject]@{ ProductId = $id; PackageFullName = $d.Name; Version = $ver }
        Write-Output ("  found: " + $id)
        Write-Output ("      <- " + $d.Name + "  v" + $ver)
    }
}

if ($regs.Count -eq 0) {
    Write-Output "  (no <UupProduct> found)"
} else {
    foreach ($r in $regs) {
        $key = "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\UUPProducts\" + $r.ProductId
        & reg.exe add "$key" /v Version  /t REG_SZ    /d "$($r.Version)" /f | Out-Null
        & reg.exe add "$key" /v IsPinned /t REG_DWORD /d 1 /f | Out-Null
        & reg.exe add "$key\$($r.PackageFullName)" /f | Out-Null
        Write-Output ("  registered: " + $r.ProductId + " <- " + $r.PackageFullName)
    }
}

Write-Output ""
Write-Output "=================== TEST 2: silicon GUID ==================="
if (-not (Test-Path $npu)) { New-Item -Path $npu -Force | Out-Null }
# Intel Core Ultra 200V  (official GUID from MS ai-model-preinstallation doc)
& reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\UnattendSettings\WaaS\Device\Detect\Hardware\NPU" /v "A6EEA85C-3D59-4FF8-A673-F88D85107D0C" /t REG_DWORD /d 1 /f | Out-Null
& reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\UnattendSettings\WaaS\Device\Detect\Hardware\NPU" /v "B2D7B485-2A57-48EA-9032-07D6BD4B3F87" /t REG_DWORD /d 1 /f | Out-Null
& reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\UnattendSettings\WaaS\Device\Detect\Hardware\NPU" /v "FF3398C2-DC93-4A64-8959-EE363977FB1A" /t REG_DWORD /d 1 /f | Out-Null
Write-Output "  wrote 3 official Copilot+ silicon GUIDs"

Write-Output ""
Write-Output "=================== AFTER ==================="
& reg.exe query "$uup" /s 2>&1 | Select-Object -First 30 | ForEach-Object { "  " + $_ }
Write-Output ""
& reg.exe query "$npu" 2>&1 | ForEach-Object { "  " + $_ }
Write-Output "DONE"
