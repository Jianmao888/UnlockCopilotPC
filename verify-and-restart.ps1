# verify-and-restart.ps1 - ASCII only
$ErrorActionPreference = 'Continue'

Write-Output "=== UUPProducts actual content ==="
$k = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\UUPProducts'
if (Test-Path $k) {
    Get-ChildItem $k | ForEach-Object {
        Write-Output ("  [" + $_.PSChildName + "]")
        $p = Get-ItemProperty $_.PSPath -EA SilentlyContinue
        if ($p) {
            foreach ($prop in $p.PSObject.Properties) {
                if ($prop.Name -notlike 'PS*') { Write-Output ("      " + $prop.Name + " = " + $prop.Value) }
            }
        }
        Get-ChildItem $_.PSPath -EA SilentlyContinue | ForEach-Object { "      subkey: " + $_.PSChildName }
    }
} else { Write-Output "  (does not exist)" }

Write-Output ""
Write-Output "=== NPU detect hive actual content ==="
$n = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\UnattendSettings\WaaS\Device\Detect\Hardware\NPU'
if (Test-Path $n) {
    $p = Get-ItemProperty $n -EA SilentlyContinue
    foreach ($prop in $p.PSObject.Properties) {
        if ($prop.Name -notlike 'PS*') { Write-Output ("  " + $prop.Name + " = " + $prop.Value) }
    }
} else { Write-Output "  (does not exist)" }

Write-Output ""
Write-Output "=== restart services to invalidate caches ==="
foreach ($s in @('WSAIFabricSvc','StateRepository','AppXSvc')) {
    $svc = Get-Service $s -EA SilentlyContinue
    if (-not $svc) { continue }
    Write-Output ("  " + $s + " = " + $svc.Status)
    try {
        Restart-Service $s -Force -ErrorAction Stop
        Write-Output "     restarted"
    } catch {
        Write-Output ("     restart failed: " + $_.Exception.Message)
    }
}
Start-Sleep -Seconds 8
foreach ($s in @('WSAIFabricSvc','StateRepository','AppXSvc')) {
    Get-Service $s -EA SilentlyContinue | ForEach-Object { "  " + $_.Name + " = " + $_.Status }
}
Write-Output "DONE"
