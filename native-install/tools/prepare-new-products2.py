"""Find a working CAB extractor, then unwrap the 11 new-generation RUM cabs and
lay out installable product packages on disk (no installation).

Extractor order: 7z -> extrac32 -> expand.  Recursive: keep unpacking nested
cabinets until the product-definition JSON appears.
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
LOG = ROOT / ".dsh-tmp" / "prepare2.log"
WORK = ROOT / ".dsh-tmp" / "onepkg" / "unwrap3"
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir(parents=True, exist_ok=True)


def log(m):
    print(m, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def candidates():
    c = []
    for p in (r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\7z.exe")):
        if pathlib.Path(p).exists():
            c.append(("7z", p))
    c.append(("extrac32", "extrac32.exe"))
    c.append(("expand", "expand.exe"))
    return c


EXTRACTORS = candidates()
log("extractors available: %s" % [e[0] for e in EXTRACTORS])


def try_extract(cab, dest):
    """Return list of produced files."""
    dest.mkdir(parents=True, exist_ok=True)
    for kind, exe in EXTRACTORS:
        try:
            if kind == "7z":
                subprocess.run([exe, "x", str(cab), "-o" + str(dest), "-y"],
                               capture_output=True, timeout=600)
            elif kind == "extrac32":
                subprocess.run([exe, "/Y", str(cab), str(dest) + "\\"],
                               capture_output=True, timeout=600)
            else:
                subprocess.run([exe, str(cab), "-F:*", str(dest)],
                               capture_output=True, timeout=600)
        except Exception as ex:
            log("   %s failed on %s: %s" % (kind, cab.name, ex))
            continue
        files = [p for p in dest.rglob("*") if p.is_file()]
        if files:
            return kind, files
    return None, []


def unwrap(cab):
    queue = [(cab, 0)]
    n = 0
    while queue and n < 60:
        c, depth = queue.pop(0)
        n += 1
        d = WORK / ("%s_%d_%d" % (re.sub(r"[^A-Za-z0-9]+", "_", c.stem)[:36], depth, n))
        kind, files = try_extract(c, d)
        if not files:
            continue
        for f in files:
            if f.suffix.lower() == ".json" and f.stat().st_size > 300:
                return f, kind
        for f in files:
            if f.suffix.lower() == ".cab":
                queue.append((f, depth + 1))
    return None, None


# local MSIX identities
local = {}
for tree in list(pathlib.Path(r"C:\Users\jianm\Downloads").glob("Windows-AI-*")) + \
        [ROOT / "native-install" / "source-analysis365", ROOT / "ai-packages", ROOT / "ai-packages" / "lnl-extra"]:
    for f in tree.rglob("*.msix"):
        try:
            if f.stat().st_size < 10000:
                continue
            with zipfile.ZipFile(f) as z:
                root = ET.fromstring(z.read("AppxManifest.xml"))
            ident = next(x for x in root if x.tag.endswith("Identity"))
            local.setdefault((ident.attrib["Name"], ident.attrib["Version"]), f)
        except Exception:
            continue
log("local MSIX identities: %d" % len(local))

summary = []
for cab in sorted(STAGE.glob("*.rum.json.cab")):
    js, kind = unwrap(cab)
    if js is None:
        log("  %-52s -> JSON not found (extractors tried: %s)" % (cab.name, [e[0] for e in EXTRACTORS]))
        summary.append(dict(product=cab.stem, rum=cab.name, status="no-json", exact=0, mismatch=0, missing=0))
        continue
    meta = json.loads(js.read_text(encoding="utf-8", errors="replace"))
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
        for pl in ent.get("EntityPayload", {}).get("Canonical", []) or []:
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
                have = sorted({v for (nm, v) in local if nm == pkg})
                if have:
                    vmis += 1
                    rows.append((pkg, ver, "VERSION-MISMATCH (have %s)" % ",".join(have)))
                else:
                    miss += 1
                    rows.append((pkg, ver, "MISSING"))
    lines = ["# %s" % pid, "", "RUM: `%s` (new generation, via %s)" % (cab.name, kind), "",
             "| package | needed version | status |", "|---|---|---|"]
    for r in rows:
        lines.append("| `%s` | %s | %s |" % r)
    lines += ["", "**exact=%d  version-mismatch=%d  missing=%d**" % (exact, vmis, miss), ""]
    lines.append("> " + ("载荷齐备：安装条件已就绪（本次未安装）" if vmis == 0 and miss == 0
                         else "存在缺件，安装会被 fileRequestCount 守卫拦下"))
    (pdir / "INVENTORY.md").write_text("\n".join(lines), encoding="utf-8")
    install = """# %(pid)s -- prepare-only package; run ELEVATED, one install at a time
param([Parameter(Mandatory=$true)][string]$RunName)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
& 'C:\\Users\\jianm\\AppData\\Local\\Programs\\Python\\Python312\\python.exe' -u `
   'C:\\Users\\jianm\\Code\\DeepseekHarness\\native-install\\tools\\run_install.py' `
   $RunName $here '%(cab)s' '%(prod)s'
""" % {"pid": pid, "cab": cab.name, "prod": up["ProductIdentifier"]}
    (pdir / "install.ps1").write_text(install, encoding="utf-8")
    log("  %-46s extractor=%-8s ents=%-3d exact=%-3d mismatch=%-3d missing=%-3d" %
        (pid, kind, len(up.get("UpdateEntityCollection", [])), exact, vmis, miss))
    summary.append(dict(product=pid, rum=cab.name, status="ready" if (vmis == 0 and miss == 0) else "incomplete",
                        exact=exact, mismatch=vmis, missing=miss))

log("")
log("== summary ==")
for s in summary:
    log("  %-46s %-11s exact=%-3d mismatch=%-3d missing=%-3d" % (s["product"], s["status"], s["exact"], s["mismatch"], s["missing"]))
(OUT / "new-generation-products.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
log("DONE")
