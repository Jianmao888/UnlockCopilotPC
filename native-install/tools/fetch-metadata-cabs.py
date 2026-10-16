"""Fetch the AggregatedMetadata cabs for our build and look for workload product
metadata (RUM) of the NEW generation (1.2608.x), which matches the payloads we
already have locally.

Small downloads only (metadata cabs are KB..low-MB).
"""
import json
import os
import pathlib
import shutil
import subprocess
import time
import urllib.request

ROOT = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
WORK = ROOT / ".dsh-tmp" / "meta"
WORK.mkdir(parents=True, exist_ok=True)
LOG = WORK / "meta.log"
PROXY = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY
opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))


def log(m):
    line = "%s %s" % (time.strftime("%H:%M:%S"), m)
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def api(path, timeout=180):
    for i in range(4):
        try:
            req = urllib.request.Request("https://api.uupdump.net/" + path, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as ex:
            log("  retry %d: %s" % (i + 1, ex))
            time.sleep(10 * (i + 1))
    return None


UUID = "fe47c57f-a77f-41e3-9012-00b4187e3462"   # build 26300.9550 (our machine)

log("################ metadata fetch start")
j = api("get.php?id=%s&pack=0&edition=0" % UUID)
files = ((j or {}).get("response", {}) or {}).get("files") or {}
log("build 26300.9550 file list: %d files" % len(files))

cabs = [(int(m.get("size") or 0), n, m.get("url"), m.get("sha1")) for n, m in files.items()
        if n.endswith(".AggregatedMetadata.cab")]
cabs.sort()
log("aggregated-metadata cabs: %d" % len(cabs))
for s, n, u, h in cabs:
    log("   %9d B  %s" % (s, n))

downloaded = []
for s, n, u, h in cabs[:12]:
    target = WORK / n
    if target.exists() and target.stat().st_size == s:
        downloaded.append(target)
        continue
    try:
        log("  downloading %s (%.1f KB)" % (n, s / 1024))
        with opener.open(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
            data = r.read()
        target.write_bytes(data)
        downloaded.append(target)
    except Exception as ex:
        log("   failed: %s" % ex)

# expand and scan
found_products = {}
for cab in downloaded:
    out = WORK / (cab.stem + "_x")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["expand.exe", str(cab), "-F:*", str(out)], capture_output=True, timeout=300)
    except Exception as ex:
        log("  expand failed for %s: %s" % (cab.name, ex))
        continue
    hits = 0
    for f in out.rglob("*"):
        if not f.is_file():
            continue
        try:
            txt = f.read_bytes().decode("utf-8", "ignore")
        except Exception:
            continue
        if "Windows.Workload" not in txt:
            continue
        import re
        for m in re.finditer(r'"(ProductIdentifier|ProductVersion|EntityName|PayloadName)"\s*:\s*"([^"]+)"', txt):
            k, v = m.group(1), m.group(2)
            if "Workload" in v or k in ("ProductIdentifier", "ProductVersion"):
                found_products.setdefault(v, set()).add(cab.name)
                hits += 1
    log("  %s -> extracted %d files, workload mentions: %d" % (cab.name, len(list(out.rglob('*'))), hits))

log("")
log("== distinct workload identifiers seen in metadata ==")
for v in sorted(found_products):
    log("   %-56s %s" % (v, ",".join(sorted(found_products[v]))[:80]))
(WORK / "meta-summary.json").write_text(json.dumps({k: sorted(v) for k, v in found_products.items()}, indent=2), encoding="utf-8")
log("DONE")
