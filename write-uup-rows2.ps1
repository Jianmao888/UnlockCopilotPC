# write-uup-rows2.ps1 - ASCII only
# Disable StateRepository so it cannot re-open the DB, write the rows, then restore.
$ErrorActionPreference = 'Continue'
$db = 'C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd'
$svc = 'StateRepository'

Write-Output "=== record original start type ==="
$orig = (Get-Service $svc).StartType
Write-Output ("  original StartType = " + $orig)

Write-Output ""
Write-Output "=== disable + stop service ==="
& sc.exe config $svc start= disabled 2>&1 | Select-Object -First 2 | ForEach-Object { "  " + $_ }
try { Stop-Service $svc -Force -EA Stop; Write-Output "  stop requested" } catch { Write-Output ("  " + $_.Exception.Message) }
for ($i=0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    $s = (Get-Service $svc -EA SilentlyContinue).Status
    if ($s -eq 'Stopped') { break }
}
Get-Service $svc | ForEach-Object { "  status = " + $_.Status }
$proc = @(Get-Process -Name StateRepository -EA SilentlyContinue)
Write-Output ("  StateRepository process count = " + $proc.Count)

Write-Output ""
Write-Output "=== write UupProduct rows ==="
python "$env:TEMP\uup_insert.py"

Write-Output ""
Write-Output "=== restore service start type + start ==="
if ($orig -eq 'Automatic') { & sc.exe config $svc start= auto 2>&1 | Out-Null }
elseif ($orig -eq 'Manual') { & sc.exe config $svc start= demand 2>&1 | Out-Null }
else { & sc.exe config $svc start= auto 2>&1 | Out-Null }
try { Start-Service $svc -EA Stop; Write-Output "  started" } catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 12
Get-Service $svc | ForEach-Object { "  " + $_.Name + " = " + $_.Status + "  StartType=" + $_.StartType }

Write-Output ""
Write-Output "=== final row counts ==="
python -c "import sqlite3;c=sqlite3.connect(r'C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd');print('  UupProduct =',c.execute('SELECT COUNT(*) FROM UupProduct').fetchone()[0]);print('  UupProductPackage =',c.execute('SELECT COUNT(*) FROM UupProductPackage').fetchone()[0])"
Write-Output "DONE"
