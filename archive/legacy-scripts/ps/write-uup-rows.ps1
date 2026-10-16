# write-uup-rows.ps1 - ASCII only
$ErrorActionPreference = 'Continue'
$db = 'C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd'
$dir = 'C:\ProgramData\Microsoft\Windows\AppRepository'

Write-Output "=== before ==="
& icacls.exe $db 2>&1 | Select-Object -First 8 | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== stop StateRepository ==="
try { Stop-Service StateRepository -Force -EA Stop; Write-Output "  stopped" } catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 5
Get-Service StateRepository | ForEach-Object { "  " + $_.Status }

Write-Output ""
Write-Output "=== take ownership + grant full control ==="
& takeown.exe /f "$dir" /a 2>&1 | Select-Object -Last 1 | ForEach-Object { "  " + $_ }
& takeown.exe /f "$db" /a 2>&1 | Select-Object -Last 1 | ForEach-Object { "  " + $_ }
& icacls.exe "$dir" /grant "*S-1-5-32-544:(OI)(CI)F" /t 2>&1 | Select-Object -Last 1 | ForEach-Object { "  " + $_ }
& icacls.exe "$db" /grant "*S-1-5-32-544:F" 2>&1 | Select-Object -Last 1 | ForEach-Object { "  " + $_ }
& attrib.exe -R "$db" 2>&1 | ForEach-Object { "  " + $_ }
Get-Item $db | ForEach-Object { "  IsReadOnly = " + $_.IsReadOnly + "  attrs = " + $_.Attributes }

Write-Output ""
Write-Output "=== insert rows ==="
python "$env:TEMP\uup_insert.py"

Write-Output ""
Write-Output "=== start StateRepository ==="
try { Start-Service StateRepository -EA Stop; Write-Output "  started" } catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 12
Get-Service StateRepository | ForEach-Object { "  StateRepository = " + $_.Status }
Write-Output "DONE"
