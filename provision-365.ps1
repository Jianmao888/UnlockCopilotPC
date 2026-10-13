# provision-365.ps1 - ASCII only
# Provision the packages that Add-AppxPackage cannot register (accessControl extension),
# then complete registration via AppReadiness.
$ErrorActionPreference = 'Continue'

$listFile = 'C:\Users\jianm\Code\DeepseekHarness\_install-list.txt'
$paths = @(Get-Content $listFile | Where-Object { $_.Trim() -ne '' })

$fail = @(
  'WindowsWorkload.ImageSearch.365.3_1.2608.951.0_x64.msix',
  'WindowsWorkload.ImageTextSearch.365.3_1.2608.951.0_x64.msix',
  'WindowsWorkload.QueryProcessor.365.1_1.2608.951.0_x64.msix',
  'WindowsWorkload.ScrRegDetection.365.1_1.2608.951.0_x64.msix',
  'WindowsWorkload.SemanticText.365.1_1.2608.951.0_x64.msix',
  'WindowsWorkload.TextRecognition.365.1_1.2608.951.0_x64.msix'
)

Write-Output "=== provision via Add-AppxProvisionedPackage ==="
foreach ($p in $paths) {
    $n = Split-Path $p -Leaf
    if ($fail -notcontains $n) { continue }
    try {
        Add-AppxProvisionedPackage -Online -PackagePath $p -SkipLicense -ErrorAction Stop | Out-Null
        Write-Output ("  provisioned  " + $n)
    } catch {
        Write-Output ("  FAIL         " + $n + " : " + $_.Exception.Message.Split([Environment]::NewLine)[0])
    }
}

Write-Output ""
Write-Output "=== start AppReadiness to complete registration ==="
try {
    Start-Service AppReadiness -ErrorAction Stop
    Write-Output "  AppReadiness started"
} catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 25

Write-Output ""
Write-Output "=== packages now visible ==="
@(Get-AppxPackage -AllUsers -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' }) |
    Sort-Object Name, Version | ForEach-Object { "  " + $_.Name + "  " + $_.Version + "  " + $_.Status }

Write-Output ""
Write-Output "=== restart WSAIFabricSvc ==="
try { Restart-Service WSAIFabricSvc -Force -ErrorAction Stop; Write-Output "  restarted" }
catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 20
Get-Service WSAIFabricSvc,AppReadiness | ForEach-Object { "  " + $_.Name + " = " + $_.Status }
Write-Output "DONE"
