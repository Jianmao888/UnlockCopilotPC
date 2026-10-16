# probe-npudetect.ps1 - ASCII only
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'

Write-Output "=== 1. NPUDetect.dll locations ==="
@(Get-ChildItem 'C:\Windows\SystemApps' -Recurse -Filter 'NPUDetect.dll' -EA SilentlyContinue) |
  ForEach-Object { "  {0,10:N0}  {1}" -f $_.Length, $_.FullName }
@(Get-ChildItem 'C:\Windows\System32' -Recurse -Filter 'NPUDetect.dll' -EA SilentlyContinue) |
  ForEach-Object { "  {0,10:N0}  {1}" -f $_.Length, $_.FullName }

Write-Output ""
Write-Output "=== 2. loaded modules named NPUDetect / Workloads in running processes ==="
Get-Process -EA SilentlyContinue | ForEach-Object {
    $p = $_
    try {
        foreach ($m in $p.Modules) {
            if ($m.ModuleName -match 'NPUDetect|Windows.Workloads|AIFabric|oneocr') {
                Write-Output ("  pid={0,-6} {1,-28} {2}" -f $p.Id, $p.ProcessName, $m.ModuleName)
            }
        }
    } catch {}
}

Write-Output ""
Write-Output "=== 3. parse NPUDetect.dll exports ==="
$py = @'
import struct, os, glob
cands = glob.glob(r"C:\Windows\SystemApps\**\NPUDetect.dll", recursive=True) + \
        glob.glob(r"C:\Windows\System32\**\NPUDetect.dll", recursive=True)
for p in cands:
    d = open(p,"rb").read()
    print(f"--- {p}  ({len(d)} bytes)")
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    nsec = struct.unpack_from("<H", d, pe+6)[0]
    optsz = struct.unpack_from("<H", d, pe+20)[0]
    opt = pe+24
    magic = struct.unpack_from("<H", d, opt)[0]
    ddoff = opt + (112 if magic==0x20b else 96)
    exp_rva, exp_sz = struct.unpack_from("<II", d, ddoff)
    secoff = opt + optsz
    secs=[]
    for i in range(nsec):
        o = secoff + i*40
        name = d[o:o+8].rstrip(b'\0').decode('ascii','ignore')
        vsz, va, rsz, ra = struct.unpack_from("<IIII", d, o+8)
        secs.append((name,va,vsz,ra,rsz))
    def r2o(rva):
        for n,va,vsz,ra,rsz in secs:
            if va <= rva < va+max(vsz,rsz): return ra+(rva-va)
        return None
    if not exp_rva:
        print("   (no exports)"); continue
    eo = r2o(exp_rva)
    nfun, nnam = struct.unpack_from("<II", d, eo+20)
    anames = struct.unpack_from("<I", d, eo+32)[0]
    aoff = r2o(anames)
    print(f"   {nfun} functions, {nnam} named")
    for i in range(nnam):
        nr = struct.unpack_from("<I", d, aoff+i*4)[0]
        no = r2o(nr)
        e = d.find(b'\0', no)
        print("     " + d[no:e].decode('ascii','ignore'))
    # import DLLs
    print("   --- imported DLLs ---")
    seen=set()
    import re
    for m in re.finditer(rb"[A-Za-z0-9_\-\.]{4,40}\.dll", d):
        s=m.group(0).decode("ascii","ignore").lower()
        if s not in seen:
            seen.add(s); print("     " + s)
'@
$py | Out-File -Encoding utf8 "$env:TEMP\probe_npudetect.py"
python "$env:TEMP\probe_npudetect.py"

Write-Output ""
Write-Output "=== 4. which module imports npudetect ==="
$py2 = @'
import glob, re, os
for base in (r"C:\Windows\SystemApps", r"C:\Windows\System32"):
    for f in glob.glob(os.path.join(base, "**", "*.dll"), recursive=True):
        try: sz = os.path.getsize(f)
        except Exception: continue
        if sz < 3000 or sz > 30_000_000: continue
        try: d = open(f,"rb").read()
        except Exception: continue
        if b"npudetect.dll" in d.lower() or b"npudetect_detect" in d:
            import re as _re
            hits = sorted(set(m.group(0).decode("ascii","ignore") for m in _re.finditer(rb"npudetect[A-Za-z0-9_\.]*", d, _re.I)))
            print(f"  {os.path.basename(f)}  ->  {hits[:8]}")
'@
$py2 | Out-File -Encoding utf8 "$env:TEMP\find_npudetect_users.py"
python "$env:TEMP\find_npudetect_users.py"
Write-Output "DONE"
