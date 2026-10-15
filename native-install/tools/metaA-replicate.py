"""Replicate exactly what was done to obtain the OLD workload RUMs, but for the
new generation.

Their phase9 fetch_metadata.py refreshed UUP metadata for two builds
(26300.9550 and 26100.6899) and pulled every *.AggregatedMetadata.cab. Their
resulting pool (KB5066835) contains onepackage.AggregatedMetadata.cab plus
Windows.Workload.*.rum.json files.

So: pull the same two builds, take every AggregatedMetadata / onepackage cab,
expand, and scan for Windows.Workload product identifiers. Report which cab /
build carries which product and which versions/entities it declares.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import time
import urllib.request

ROOT = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
WORK = ROOT / ".dsh-tmp" / "metaA"
WORK.mkdir(parents=True, exist_ok=True)
LOG = WORK / "metaA.log"
PROXY = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY
opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))

# exactly the two builds their script used
BUILDS = [("26300.9550", "fe47c57f-a77f-41e3-9012-00b4187e3462"),
          ("26100.6899", "15127f8d-75c8-4150-98d1-5020aa815a35")]


def log(m):
    line = "%s %s" % (time.strftime("%H:%M:%S"), m)
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def api(path, timeout=300):
    for i in range(5):
        try:
            req = urllib.request.Request("https://api.uupdump.net/" + path, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as ex:
            log("  retry %d: %s" % (i + 1, ex))
            time.sleep(15 * (i + 1))
    return None


found = {}     # product -> {cabs}
detail = {}    # product -> {version, entities}
for tag, uuid in BUILDS:
    log("== build %s  (id %s)" % (tag, uuid))
    j = api("get.php?id=%s&pack=0&edition=0" % uuid)
    files = ((j or {}).get("response", {}) or {}).get("files") or {}
    log("   files: %d" % len(files))
    cabs = [(int(m.get("size") or 0), n, m.get("url")) for n, m in files.items()
            if n.lower().endswith(".cab") and ("aggregatedmetadata" in n.lower() or "onepackage" in n.lower())]
    cabs.sort()
    log("   aggregated/onepackage cabs: %d" % len(cabs))
    for s, n, u in cabs:
        log("      %12d B  %s" % (s, n))
    for s, n, u in cabs:
        target = WORK / ("%s_%s" % (tag, n))
        if not (target.exists() and target.stat().st_size == s):
            try:
                log("      downloading %s (%.1f KB)" % (n, s / 1024))
                with opener.open(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=300) as r:
                    target.write_bytes(r.read())
            except Exception as ex:
                log("      download failed: %s" % ex)
                continue
        out = WORK / (re.sub(r"[^A-Za-z0-9]+", "_", "%s_%s" % (tag, n))[:70] + "_x")
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["expand.exe", str(target), "-F:*", str(out)], capture_output=True, timeout=600)
        except Exception as ex:
            log("      expand failed: %s" % ex)
            continue
        hits = 0
        for f in list(out.rglob("*"))[:6000]:
            if not f.is_file():
                continue
            try:
                raw = f.read_bytes()
            except Exception:
                continue
            txt = raw.decode("utf-8", "ignore") + "\n" + raw.decode("utf-16-le", "ignore")
            for m in re.finditer(r"Windows\.Workload\.[A-Za-z0-9_.]+", txt):
                p = m.group(0)
                found.setdefault(p, set()).add("%s:%s" % (tag, n[:30]))
                hits += 1
            # also capture product version / entity names near any Workload mention
            for m in re.finditer(r'"(?:ProductIdentifier|ProductVersion|EntityName|PayloadName)"\s*:\s*"([^"]{4,120})"', txt):
                v = m.group(1)
                if "Workload" in v:
                    detail.setdefault(v, set()).add(tag)
        log("      %s -> workload mentions: %d" % (n[:46], hits))

log("")
log("== distinct workload identifiers ==")
for p in sorted(found):
    log("   %-58s %s" % (p, ",".join(sorted(found[p]))[:60]))
log("")
log("== entity/version strings ==")
for v in sorted(detail):
    log("   %-64s %s" % (v, ",".join(sorted(detail[v]))))
(WORK / "A-products.json").write_text(json.dumps(dict(products={k: sorted(v) for k, v in found.items()},
                                                      detail={k: sorted(v) for k, v in detail.items()}), indent=2),
                                      encoding="utf-8")
log("DONE")
