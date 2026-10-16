# post-reboot-check.ps1 - ASCII only
# Run after reboot to see whether the workload registration materialized.
$ErrorActionPreference = 'Continue'

Write-Output "=== 1. packages present ==="
@(Get-AppxPackage -AllUsers -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' }) |
    Group-Object Name | ForEach-Object { "  " + $_.Name + "  (" + $_.Count + ")" }

Write-Output ""
Write-Output "=== 2. StateRepository UupProduct rows ==="
$dst = 'C:\Users\jianm\Code\DeepseekHarness\srd-postreboot.srd'
Copy-Item 'C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd' $dst -Force -EA SilentlyContinue
python -c "import sqlite3;c=sqlite3.connect(r'$dst');print('  UupProduct rows =',c.execute('SELECT COUNT(*) FROM UupProduct').fetchone()[0]);print('  UupProductPackage rows =',c.execute('SELECT COUNT(*) FROM UupProductPackage').fetchone()[0]);[print('   ',r) for r in c.execute('SELECT * FROM UupProduct LIMIT 10')]"

Write-Output ""
Write-Output "=== 3. registry UUPProducts ==="
& reg.exe query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\UUPProducts" /s 2>&1 | Select-Object -First 25 | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== 4. workloads.json still swapped? ==="
$gen = 'C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\workloads.json'
$t = Get-Content $gen -Raw
Write-Output ("  length = " + $t.Length + "   (12066 = our minimal version)")
if ($t -match 'WindowsWorkload\.\w+\.365') { Write-Output "  contains .365. families: YES" } else { Write-Output "  contains .365. families: NO  <-- reverted!" }

Write-Output ""
Write-Output "=== 5. services ==="
Get-Service WSAIFabricSvc,StateRepository,AppXSvc,AppReadiness -EA SilentlyContinue |
    ForEach-Object { "  " + $_.Name + " = " + $_.Status }

Write-Output ""
Write-Output "=== 6. recent RegisterByPackageFamilyName ==="
@(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-AppXDeploymentServer/Operational'; StartTime=(Get-Date).AddMinutes(-10)} -EA SilentlyContinue |
   Where-Object { $_.Id -eq 603 -and $_.Message -match 'RegisterByPackageFamilyName' }) |
  Select-Object -First 25 | ForEach-Object {
    if ($_.Message -match '(\S+_8wekyb3d8bbwe)') { Write-Output ("  [" + $_.TimeCreated.ToString('HH:mm:ss') + "] " + $Matches[1]) }
  }
Write-Output "DONE"
