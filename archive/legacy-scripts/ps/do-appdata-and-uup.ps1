# do-appdata-and-uup.ps1 - ASCII only
# Step A: create ApplicationData\<family>\Machine with LocalService ACL (take ownership first)
# Step B: insert UupProduct / UupProductPackage rows into StateRepository
$ErrorActionPreference = 'Continue'

$appdata = 'C:\ProgramData\Microsoft\Windows\AppRepository\Families\ApplicationData'

Write-Output "=== A1. take ownership of ApplicationData ==="
& takeown.exe /f "$appdata" /a 2>&1 | Select-Object -Last 1 | ForEach-Object { "  " + $_ }
& icacls.exe "$appdata" /grant "*S-1-5-32-544:(OI)(CI)F" /t 2>&1 | Select-Object -Last 2 | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== A2. create Machine folders + LocalService ACL ==="
$dirs = @(Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -EA SilentlyContinue |
          Where-Object { $_.Name -match '^WindowsWorkload\.' })
$made = 0
foreach ($d in $dirs) {
    $parts = $d.Name -split '_'
    if ($parts.Count -lt 3) { continue }
    $fam = $parts[0] + '_' + $parts[-1]
    $t = Join-Path $appdata "$fam\Machine"
    if (-not (Test-Path $t)) {
        try { New-Item -Path $t -ItemType Directory -Force -EA Stop | Out-Null; $made++ }
        catch { Write-Output ("  mkdir failed " + $fam + " : " + $_.Exception.Message); continue }
    }
    try {
        $acl = Get-Acl $t
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule("NT AUTHORITY\LOCAL SERVICE","Modify, ListDirectory","ContainerInherit, ObjectInherit","None","Allow")
        $acl.SetAccessRule($rule)
        Set-Acl -Path $t -AclObject $acl
    } catch { Write-Output ("  acl failed " + $fam + " : " + $_.Exception.Message) }
}
Write-Output ("  created " + $made + " new, processed " + $dirs.Count)
@(Get-ChildItem $appdata -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' }) | ForEach-Object { "    " + $_.Name }

Write-Output ""
Write-Output "=== B. stop StateRepository before writing DB ==="
try { Stop-Service StateRepository -Force -EA Stop; Write-Output "  stopped" }
catch { Write-Output ("  stop failed: " + $_.Exception.Message) }
Start-Sleep -Seconds 5
Get-Service StateRepository | ForEach-Object { "  StateRepository = " + $_.Status }

Write-Output ""
Write-Output "=== B2. insert UupProduct rows ==="
$py = @'
import sqlite3, os, shutil, sys

DB = r"C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd"
BAK = r"C:\Users\jianm\Code\DeepseekHarness\srd-before-uupwrite.srd"
if not os.path.exists(BAK):
    shutil.copy2(DB, BAK)
    print("  backup written")

c = sqlite3.connect(DB)
cur = c.cursor()

# map productId -> list of PackageIdentity._PackageIdentityID
targets = {
    "Windows.Workload.ContentExtraction.365.amd64": ["TextRecognition.365.1"],
    "Windows.Workload.Analysis.365.amd64":          ["SemanticText.365.1"],
    "Windows.Workload.ImageSearch.365.amd64":       ["ImageSearch.365.3"],
}
# also add all packages that belong to each workload (from the minimal workloads.json families)
WORKLOAD_FAMS = {
    "Windows.Workload.ContentExtraction.365.amd64": [
        "WindowsWorkload.Data.ContentExtraction.365.1",
        "WindowsWorkload.Manager.1",
        "WindowsWorkload.PSOnnxRuntime.365.3.7",
        "WindowsWorkload.ScrRegDetection.365.1",
        "WindowsWorkload.ScrRegDetection.Data.1",
        "WindowsWorkload.SessionManager.1",
        "WindowsWorkload.TextRecognition.365.1"],
    "Windows.Workload.Analysis.365.amd64": [
        "WindowsWorkload.Data.Analysis.365.1",
        "WindowsWorkload.Manager.1",
        "WindowsWorkload.PSOnnxRuntime.365.3.7",
        "WindowsWorkload.PSTokenizer.365.2.7",
        "WindowsWorkload.PSTokenizerShared.365.3.7",
        "WindowsWorkload.QueryProcessor.365.1",
        "WindowsWorkload.SemanticText.365.1",
        "WindowsWorkload.SessionManager.1"],
    "Windows.Workload.ImageSearch.365.amd64": [
        "WindowsWorkload.Data.ImageSearch.365.1",
        "WindowsWorkload.ImageSearch.365.3",
        "WindowsWorkload.ImageTextSearch.365.3",
        "WindowsWorkload.Manager.1",
        "WindowsWorkload.PSOnnxRuntime.365.3.7",
        "WindowsWorkload.PSTokenizerShared.365.3.7",
        "WindowsWorkload.SessionManager.1"],
}

def pid_of(fam):
    row = cur.execute(
        "SELECT _PackageIdentityID, Version FROM PackageIdentity WHERE PackageFullName LIKE ? LIMIT 1",
        (fam + "_%",)).fetchone()
    if not row:
        return None
    return row[0]

def ver_of(fam):
    row = cur.execute(
        "SELECT Version FROM Package WHERE PackageFullName LIKE ? LIMIT 1",
        (fam + "_%",)).fetchone()
    return row[0] if row else 0

added_p = added_pp = 0
for product in sorted(WORKLOAD_FAMS):
    ver = 0
    for fam in WORKLOAD_FAMS[product]:
        v = ver_of(fam)
        if v: ver = v; break
    existing = cur.execute("SELECT _UupProductID FROM UupProduct WHERE ProductID=?", (product,)).fetchone()
    if existing:
        upid = existing[0]
        print("  product exists: " + product)
    else:
        cur.execute("INSERT INTO UupProduct(_Revision,ProductID,Version,Flags,_Dictionary) VALUES(1,?,?,0,NULL)",
                    (product, ver))
        upid = cur.lastrowid
        added_p += 1
        print("  + product %s  ver=%d  0x%X" % (product, ver, ver))
    for fam in WORKLOAD_FAMS[product]:
        pkgid = pid_of(fam)
        if pkgid is None:
            print("      !! no PackageIdentity for " + fam); continue
        ex = cur.execute("SELECT _UupProductPackageID FROM UupProductPackage WHERE UupProduct=? AND PackageIdentity=?",
                         (upid, pkgid)).fetchone()
        if ex: continue
        cur.execute("INSERT INTO UupProductPackage(_Revision,UupProduct,PackageIdentity,Flags,_Dictionary) VALUES(1,?,?,0,NULL)",
                    (upid, pkgid))
        added_pp += 1
        print("      + pkg %s (id=%d)" % (fam, pkgid))
c.commit()
print("  added products=%d packages=%d" % (added_p, added_pp))
print("  totals now: UupProduct=%d UupProductPackage=%d" % (
    cur.execute("SELECT COUNT(*) FROM UupProduct").fetchone()[0],
    cur.execute("SELECT COUNT(*) FROM UupProductPackage").fetchone()[0]))
c.close()
'@
$py | Out-File -Encoding utf8 "$env:TEMP\uup_insert.py"
python "$env:TEMP\uup_insert.py"

Write-Output ""
Write-Output "=== start StateRepository ==="
try { Start-Service StateRepository -EA Stop; Write-Output "  started" } catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 10
Get-Service StateRepository | ForEach-Object { "  StateRepository = " + $_.Status }
Write-Output "DONE"
