# diag-write.ps1 - ASCII only
$ErrorActionPreference = 'Continue'
$db  = 'C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd'
$dir = 'C:\ProgramData\Microsoft\Windows\AppRepository'

Write-Output "=== 1. effective ACL on the .srd file ==="
& icacls.exe $db 2>&1 | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== 2. can we create a file in that directory? ==="
$probe = Join-Path $dir '_dsh_write_probe.tmp'
try {
    'x' | Out-File $probe -Encoding ascii -EA Stop
    Write-Output "  directory writable: YES"
    Remove-Item $probe -Force
} catch { Write-Output ("  directory writable: NO  " + $_.Exception.Message) }

Write-Output ""
Write-Output "=== 3. can we append to the .srd file itself? ==="
try {
    $fs = [System.IO.File]::Open($db, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::ReadWrite)
    Write-Output "  file open RW: YES"
    $fs.Close()
} catch { Write-Output ("  file open RW: NO  " + $_.Exception.Message) }

Write-Output ""
Write-Output "=== 4. who has the file open? ==="
$names = @(Get-Process -EA SilentlyContinue | Where-Object { $_.ProcessName -match 'StateRepository|AppXSvc|svchost' } |
           Select-Object -ExpandProperty Id)
Write-Output ("  candidate pids: " + ($names -join ', '))
Get-Service StateRepository,AppXSvc -EA SilentlyContinue | ForEach-Object { "  " + $_.Name + " = " + $_.Status }

Write-Output ""
Write-Output "=== 5. try sqlite write via python directly (verbose) ==="
$py = @'
import sqlite3, os, traceback
db = r"C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd"
print("  os.access W:", os.access(db, os.W_OK))
print("  file mode  :", oct(os.stat(db).st_mode))
d = os.path.dirname(db)
try:
    t = os.path.join(d, "_pyprobe.tmp")
    open(t,"w").write("x"); os.remove(t); print("  dir writable: True")
except Exception as e:
    print("  dir writable: False ->", e)
try:
    c = sqlite3.connect(db, timeout=5)
    c.execute("BEGIN IMMEDIATE")
    print("  BEGIN IMMEDIATE: ok")
    c.rollback()
    c.close()
except Exception as e:
    print("  write attempt:", e)
    traceback.print_exc()
'@
$py | Out-File -Encoding utf8 "$env:TEMP\diagw.py"
python "$env:TEMP\diagw.py"
Write-Output "DONE"
