# try-provision.ps1 - try alternative registration paths for accessControl packages
$ErrorActionPreference = 'Continue'
$pkg = 'C:\Users\jianm\Code\DeepseekHarness\ai-packages-legacy\99c8c976-ccf8-753b-683d-07c62b9e7e6c_1.2509.1022.0_x64.msix'
$pkg2 = 'C:\Users\jianm\Code\DeepseekHarness\ai-packages\WindowsWorkload.TextRecognition.Lnl.1_1.2608.951.0_x64.msix'

Write-Output "=== A) 当前身份与权限 ==="
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
Write-Output ("  User: " + $id.Name)
Write-Output ("  Admin: " + (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))

Write-Output ""
Write-Output "=== B) 相关策略 ==="
foreach ($k in @('HKLM:\SOFTWARE\Policies\Microsoft\Windows\Appx',
                 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock',
                 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Appx\AppxAllUserStore')) {
    if (Test-Path $k) {
        Write-Output ("  " + $k)
        (Get-ItemProperty $k | Select-Object * -Exclude PS* | Out-String).Trim() -split "`n" | ForEach-Object { "      " + $_ }
    } else { Write-Output ("  (不存在) " + $k) }
}

Write-Output ""
Write-Output "=== C) 尝试 Add-AppxProvisionedPackage ==="
foreach ($p in @($pkg, $pkg2)) {
    Write-Output ("  -- " + (Split-Path $p -Leaf))
    try {
        $r = Add-AppxProvisionedPackage -Online -PackagePath $p -SkipLicense -ErrorAction Stop
        Write-Output ("     OK: " + ($r | Out-String).Trim())
    } catch {
        Write-Output ("     ERR: " + $_.Exception.Message)
    }
}

Write-Output ""
Write-Output "=== D) 尝试 DISM /Add-ProvisionedAppxPackage ==="
foreach ($p in @($pkg, $pkg2)) {
    Write-Output ("  -- " + (Split-Path $p -Leaf))
    $o = & dism.exe /Online /Add-ProvisionedAppxPackage /PackagePath:"$p" /SkipLicense 2>&1
    ($o | Select-Object -Last 6) | ForEach-Object { "     " + $_ }
}
Write-Output "DONE"
