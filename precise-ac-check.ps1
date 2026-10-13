# precise-ac-check.ps1 - ASCII only; find which packages truly declare accessControl Register
$ErrorActionPreference = 'Continue'
Write-Output "=== packages on disk and their exact accessControl/appdata usage ==="
foreach ($d in (Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -EA SilentlyContinue |
                Where-Object { $_.Name -match '^WindowsWorkload' })) {
  $mf = Join-Path $d.FullName 'AppxManifest.xml'
  if (-not (Test-Path $mf)) { continue }
  $raw = Get-Content $mf -Raw
  $hasRegister = $raw -match '<accesscontrol:Register'
  $hasFolder   = $raw -match '<appdata:MachineFolder'
  $hasInteg    = $raw -match 'uap10:PackageIntegrity'
  $hasPkgExt   = $raw -match 'windows.packageExtension'
  $tag = $d.Name
  if ($tag.Length -gt 56) { $tag = $tag.Substring(0,56) }
  Write-Output ("  " + $tag)
  Write-Output ("      Register=" + $hasRegister + "  MachineFolder=" + $hasFolder +
                "  Integrity=" + $hasInteg + "  pkgExtension=" + $hasPkgExt)
}

Write-Output ""
Write-Output "=== which of the 7 are registered for CURRENT user ==="
Get-AppxPackage -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' } |
  ForEach-Object { "  REG  " + $_.Name + "  v" + $_.Version }

Write-Output ""
Write-Output "=== which are provisioned (all-users) ==="
Get-AppxProvisionedPackage -Online -EA SilentlyContinue |
  Where-Object { $_.DisplayName -match 'WindowsWorkload' } |
  ForEach-Object { "  PROV " + $_.DisplayName + "  v" + $_.Version }

Write-Output ""
Write-Output "=== does the AIFabric AIComponentManager see anything? (registry view) ==="
$k = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModel\StateChange\PackageFamilyList'
@(Get-ChildItem $k -EA SilentlyContinue | Where-Object { $_.PSChildName -match 'WindowsWorkload' }).Count
Write-Output "  (count of WindowsWorkload families in StateChange list)"

Write-Output ""
Write-Output "=== AppxAllUserStore: are the workload packages there? ==="
$k2 = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Applications'
@(Get-ChildItem $k2 -EA SilentlyContinue | Where-Object { $_.PSChildName -match 'WindowsWorkload' }).Count
Write-Output "  (count)"
Get-ChildItem $k2 -EA SilentlyContinue | Where-Object { $_.PSChildName -match 'WindowsWorkload' } |
  Select-Object -First 10 -ExpandProperty PSChildName
Write-Output "DONE"
