# do-pinned.ps1 - ASCII only
# Official sequence from add-OemPreload.ps1 Convert-ProvisionedPackagesToPinned:
#   REG DELETE  AppxAllUserStore\Applications\<PackageFullName>
#   REG ADD     AppxAllUserStore\Pinned\<PackageFamilyName>
$ErrorActionPreference = 'Continue'

$base = 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore'
$apps = "$base\Applications"
$pinned = "$base\Pinned"

Write-Output "=== step 1: delete provisioned Applications entries ==="
$targets = @(Get-ChildItem $apps -EA SilentlyContinue | Where-Object { $_.PSChildName -match '^WindowsWorkload\.' })
foreach ($t in $targets) {
    Write-Output ("  deleting " + $t.PSChildName)
    & reg.exe delete "$apps\$($t.PSChildName)" /f 2>&1 | Out-Null
}

Write-Output ""
Write-Output "=== step 2: add Pinned entries by family name ==="
if (-not (Test-Path $pinned)) { New-Item -Path $pinned -Force | Out-Null }
$fams = @()
foreach ($t in $targets) {
    # WindowsWorkload.ScrRegDetection.Lnl.1_1.2509.1022.0_x64__8wekyb3d8bbwe
    #   -> WindowsWorkload.ScrRegDetection.Lnl.1_8wekyb3d8bbwe
    $parts = $t.PSChildName -split '_'
    if ($parts.Count -ge 3) {
        $fam = $parts[0] + '_' + $parts[-1]
        $fams += $fam
    }
}
# 也把当前用户已注册的 5 个包一并 pin
foreach ($pk in @(Get-AppxPackage -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' })) {
    if ($fams -notcontains $pk.PackageFamilyName) { $fams += $pk.PackageFamilyName }
}

foreach ($f in ($fams | Sort-Object -Unique)) {
    & reg.exe add "$pinned\$f" /f 2>&1 | Out-Null
    Write-Output ("  pinned " + $f)
}

Write-Output ""
Write-Output "=== verify ==="
& reg.exe query "$pinned" 2>&1 | ForEach-Object { "  " + $_ }
Write-Output ""
Write-Output "Applications remaining WindowsWorkload:"
@(Get-ChildItem $apps -EA SilentlyContinue | Where-Object { $_.PSChildName -match '^WindowsWorkload\.' }) | ForEach-Object { "  " + $_.PSChildName }

Write-Output ""
Write-Output "=== restart services ==="
foreach ($s in @('WSAIFabricSvc','StateRepository')) {
    try { Restart-Service $s -Force -ErrorAction Stop; Write-Output ("  " + $s + " restarted") }
    catch { Write-Output ("  " + $s + ": " + $_.Exception.Message) }
}
Start-Sleep -Seconds 10
Get-Service WSAIFabricSvc,StateRepository,AppXSvc -EA SilentlyContinue | ForEach-Object { "  " + $_.Name + " = " + $_.Status }
Write-Output "DONE"
