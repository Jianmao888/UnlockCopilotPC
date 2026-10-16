"""Unwrap the new-generation RUM cabs and lay out installable product packages on
disk (NO installation is performed).

For every Windows.Workload.*.rum.json.cab found in the staging area:
  * recursively expand nested cabs until the product-definition JSON appears
  * parse it to learn the product's entities and their PayloadName(s)
  * build  ai-products\\<ProductID>\\{load, metadata, install.ps1, INVENTORY.md}
      load\\      payloads named exactly as the RUM's PayloadName, taken from the
                 local MSIX whose manifest identity (name+version) matches
      metadata\\  engine + plugins + this product's RUM cab
  * report exact / version-mismatch / missing per product
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
STAGE = ROOT / ".dsh-tmp" / "onepkg" / "x"
OUT = ROOT / "ai-products"
ENGINE = ROOT / "native-install" / "source-analysis365" / "metadata"
LOG = ROOT / ".dsh-tmp" / "prepare-products.log"
UNWRAP = ROOT / ".dsh-tmp" / "onepkg" / "unwrap2"

if UNWRAP.exists():
    shutil.rmtree(UNWRAP)
UNWRAP.mkdir(parents=True, exist_ok=True)


def log(m):
    print(m, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def expand(cab, dest):
    dest.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["expand.exe", str(cab), "-F:*", str(dest)],
                       capture_output=True, timeout=900)
    except Exception as ex:
        log("   expand error %s: %s" % (cab.name, ex))
    return [p for p in dest.rglob("*") if p.is_file()]


def unwrap(cab):
    """Return the path of the JSON inside this (possibly nested) cab."""
    cur = [(cab, 0)]
    seen = 0
    while cur and seen < 40:
        c, depth = cur.pop(0)
        seen += 1
        d = UNWRAP / ("%s_d%d_%d" % (re.sub(r"[^A-Za-z0-9]+", "_", c.stem)[:40], depth, seen))
        files = expand(c, d)
        for f in files:
            if f.suffix.lower() == ".json" and f.stat().st_size > 500:
                return f
        for f in files:
            if f.suffix.lower() == ".cab":
                cur.append((f, depth + 1))
    return None


# ---- local MSIX identity index
local = {}
for tree in list(pathlib.Path(r"C:\Users\jianm\Downloads").glob("Windows-AI-*")) + \
        [ROOT / "native-install" / "source-analysis365", ROOT / "ai-packages", ROOT / "ai-packages" / "lnl-extra"]:
    for f in tree.rglob("*.msix"):
        try:
            if f.stat().st_size < 10000:
                continue
            with zipfile.ZipFile(f) as z:
                if "AppxManifest.xml" not in z.namelist():
                    continue
                root = ET.fromstring(z.read("AppxManifest.xml"))
            ident = next(n for n in root if n.tag.endswith("Identity"))
            local.setdefault((ident.attrib["Name"], ident.attrib["Version"]), f)
        except Exception:
            continue
log("local MSIX identities: %d" % len(local))

cabs = sorted(STAGE.glob("*.rum.json.cab"))
log("staged RUM cabs: %d" % len(cabs))
summary = []

for cab in cabs:
    meta_file = unwrap(cab)
    if meta_file is None:
        log("  %-52s -> JSON not found" % cab.name)
        summary.append((cab.name, "no-json", 0, 0, 0))
        continue
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8", errors="replace"))
    except Exception as ex:
        log("  %-52s -> parse failed: %s" % (cab.name, ex))
        summary.append((cab.name, "bad-json", 0, 0, 0))
        continue

    up = meta["UpdateProduct"][0]
    pid = up["ProductIdentifier"] + "." + up.get("ProductArchitecture", "amd64")
    pdir = OUT / pid
    load = pdir / "load"
    mdir = pdir / "metadata"
    if pdir.exists():
        shutil.rmtree(pdir)
    load.mkdir(parents=True)
    mdir.mkdir(parents=True)

    for f in ENGINE.iterdir():
        if f.is_file() and (f.suffix.lower() == ".dll" or f.name in ("msix.installer.json", "hardware.installer.json")):
            shutil.copy2(f, mdir / f.name)
    shutil.copy2(cab, mdir / cab.name)

    exact = vmis = miss = 0
    rows = []
    for ent in up.get("UpdateEntityCollection", []):
        pkg = ent["EntityIdentifier"]["EntityName"].split("_")[0]
        pays = ent.get("EntityPayload", {}).get("Canonical", []) or []
        if not pays:
            rows.append((pkg, "-", "no-payload"))
            continue
        for pl in pays:
            pname = pl["PayloadName"]
            if not pname.endswith(".msix"):
                continue
            ver = pname.split("_")[1]
            src = local.get((pkg, ver))
            if src:
                shutil.copy2(src, load / pname)
                exact += 1
                rows.append((pkg, ver, "exact"))
            else:
                have = [v for (n, v) in local if n == pkg]
                if have:
                    vmis += 1
                    rows.append((pkg, ver, "VERSION-MISMATCH (have %s)" % ",".join(sorted(have))))
                else:
                    miss += 1
                    rows.append((pkg, ver, "MISSING"))
    lines = ["# %s" % pid, "", "RUM: `%s` (new generation)" % cab.name, "",
             "| package | needed version | status |", "|---|---|---|"]
    for r in rows:
        lines.append("| `%s` | %s | %s |" % r)
    lines += ["", "**exact=%d  version-mismatch=%d  missing=%d**" % (exact, vmis, miss), ""]
    lines.append("> " + ("载荷齐备，可直接 `install.ps1`（本次未安装）" if (vmis == 0 and miss == 0)
                         else "存在缺件，安装会因 fileRequestCount>0 被守卫拦下"))
    (pdir / "INVENTORY.md").write_text("\n".join(lines), encoding="utf-8")

    install = """# product: %(pid)s   (prepare-only; run ELEVATED and one at a time)
param([Parameter(Mandatory=$true)][string]$RunName)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = 'C:\\Users\\jianm\\AppData\\Local\\Programs\\Python\\Python312\\python.exe'
$launcher = 'C:\\Users\\jianm\\Code\\DeepseekHarness\\native-install\\tools\\run_install.py'
& $py -u $launcher $RunName $here '%(cab)s' '%(prod)s'
$tools = Split-Path -Parent $launcher
$ev = Join-Path $tools ($RunName + '.events.txt')
if (Test-Path $ev) { Get-Content $ev | Select-String 'fileRequestCount|guard|install\\.end' }
""" % {"pid": pid, "cab": cab.name, "prod": up["ProductIdentifier"]}
    (pdir / "install.ps1").write_text(install, encoding="utf-8")

    log("  %-46s ents=%-3d exact=%-3d mismatch=%-3d missing=%-3d" %
        (pid, len(up.get("UpdateEntityCollection", [])), exact, vmis, miss))
    summary.append((pid, cab.name, exact, vmis, miss))

log("")
log("== summary ==")
for pid, c, e, v, m in summary:
    log("  %-46s exact=%-3d mismatch=%-3d missing=%-3d" % (pid, e, v, m))
(OUT / "new-generation-products.json").write_text(
    json.dumps([dict(product=p, rum=c, exact=e, mismatch=v, missing=m) for p, c, e, v, m in summary], indent=2),
    encoding="utf-8")
log("DONE")
