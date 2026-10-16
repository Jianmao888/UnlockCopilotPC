# write-uup-rows3.ps1 - ASCII only
# Copy DB out, edit the copy, copy back. Avoids the live-file readonly behaviour.
$ErrorActionPreference = 'Continue'
$db  = 'C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd'
$svc = 'StateRepository'
$tmp = 'C:\Users\jianm\Code\DeepseekHarness\srd-edit.srd'

Write-Output "=== stop service ==="
try { Stop-Service $svc -Force -EA Stop } catch {}
for ($i=0; $i -lt 20; $i++) { Start-Sleep -Seconds 1; if ((Get-Service $svc -EA SilentlyContinue).Status -eq 'Stopped') { break } }
Get-Service $svc | ForEach-Object { "  " + $_.Status }

Write-Output ""
Write-Output "=== copy out ==="
Copy-Item $db $tmp -Force -EA SilentlyContinue
$fi = Get-Item $tmp
Write-Output ("  copied " + $fi.Length + " bytes -> " + $tmp)

Write-Output ""
Write-Output "=== edit the copy ==="
$py = @'
import sqlite3, os
DB = r"C:\Users\jianm\Code\DeepseekHarness\srd-edit.srd"
c = sqlite3.connect(DB)
cur = c.cursor()
print("  writable copy:", os.access(DB, os.W_OK))

WORKLOAD_FAMS = {
    "Windows.Workload.ContentExtraction.365.amd64": [
        "WindowsWorkload.Data.ContentExtraction.365.1","WindowsWorkload.Manager.1",
        "WindowsWorkload.PSOnnxRuntime.365.3.7","WindowsWorkload.ScrRegDetection.365.1",
        "WindowsWorkload.ScrRegDetection.Data.1","WindowsWorkload.SessionManager.1",
        "WindowsWorkload.TextRecognition.365.1"],
    "Windows.Workload.Analysis.365.amd64": [
        "WindowsWorkload.Data.Analysis.365.1","WindowsWorkload.Manager.1",
        "WindowsWorkload.PSOnnxRuntime.365.3.7","WindowsWorkload.PSTokenizer.365.2.7",
        "WindowsWorkload.PSTokenizerShared.365.3.7","WindowsWorkload.QueryProcessor.365.1",
        "WindowsWorkload.SemanticText.365.1","WindowsWorkload.SessionManager.1"],
    "Windows.Workload.ImageSearch.365.amd64": [
        "WindowsWorkload.Data.ImageSearch.365.1","WindowsWorkload.ImageSearch.365.3",
        "WindowsWorkload.ImageTextSearch.365.3","WindowsWorkload.Manager.1",
        "WindowsWorkload.PSOnnxRuntime.365.3.7","WindowsWorkload.PSTokenizerShared.365.3.7",
        "WindowsWorkload.SessionManager.1"],
}

def pkgident(fam):
    r = cur.execute("SELECT _PackageIdentityID FROM PackageIdentity WHERE PackageFullName LIKE ? LIMIT 1",(fam+"_%",)).fetchone()
    return r[0] if r else None
def ver(fam):
    r = cur.execute("SELECT Version FROM Package WHERE PackageFullName LIKE ? LIMIT 1",(fam+"_%",)).fetchone()
    return r[0] if r else 0

ap=app=0
for prod in sorted(WORKLOAD_FAMS):
    v=0
    for f in WORKLOAD_FAMS[prod]:
        x=ver(f)
        if x: v=x; break
    row = cur.execute("SELECT _UupProductID FROM UupProduct WHERE ProductID=?",(prod,)).fetchone()
    if row: upid=row[0]
    else:
        cur.execute("INSERT INTO UupProduct(_Revision,ProductID,Version,Flags,_Dictionary) VALUES(1,?,?,0,NULL)",(prod,v))
        upid=cur.lastrowid; ap+=1
        print("  + product %s  ver=%d" % (prod, v))
    for f in WORKLOAD_FAMS[prod]:
        pid=pkgident(f)
        if pid is None: print("      !! no identity: "+f); continue
        ex=cur.execute("SELECT 1 FROM UupProductPackage WHERE UupProduct=? AND PackageIdentity=?",(upid,pid)).fetchone()
        if ex: continue
        cur.execute("INSERT INTO UupProductPackage(_Revision,UupProduct,PackageIdentity,Flags,_Dictionary) VALUES(1,?,?,0,NULL)",(upid,pid))
        app+=1
        print("      + pkg %s (id=%d)" % (f,pid))
c.commit()
print("  added products=%d packages=%d" % (ap,app))
print("  totals: UupProduct=%d UupProductPackage=%d" % (
    cur.execute("SELECT COUNT(*) FROM UupProduct").fetchone()[0],
    cur.execute("SELECT COUNT(*) FROM UupProductPackage").fetchone()[0]))
c.close()
'@
$py | Out-File -Encoding utf8 "$env:TEMP\uup_insert2.py"
python "$env:TEMP\uup_insert2.py"

Write-Output ""
Write-Output "=== copy back ==="
try {
    Copy-Item $tmp $db -Force -EA Stop
    Write-Output "  copied back"
} catch { Write-Output ("  copy back failed: " + $_.Exception.Message) }
Get-Item $db | ForEach-Object { "  db size = " + $_.Length }

Write-Output ""
Write-Output "=== start service ==="
try { Start-Service $svc -EA Stop; Write-Output "  started" } catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 12
Get-Service $svc | ForEach-Object { "  " + $_.Name + " = " + $_.Status }

Write-Output ""
Write-Output "=== verify from live DB ==="
Remove-Item 'C:\Users\jianm\Code\DeepseekHarness\srd-verify.srd' -Force -EA SilentlyContinue
Copy-Item $db 'C:\Users\jianm\Code\DeepseekHarness\srd-verify.srd' -Force -EA SilentlyContinue
python -c "import sqlite3;c=sqlite3.connect(r'C:\Users\jianm\Code\DeepseekHarness\srd-verify.srd');print('  UupProduct =',c.execute('SELECT COUNT(*) FROM UupProduct').fetchone()[0]);print('  UupProductPackage =',c.execute('SELECT COUNT(*) FROM UupProductPackage').fetchone()[0]);[print('   ',r) for r in c.execute('SELECT ProductID,Version FROM UupProduct')]"
Write-Output "DONE"
