"""Look for workload product metadata (RUM) in every metadata-ish cab offered by
UUP for the builds we care about, including the newest one.

Scans both text and raw bytes for 'Workload' and prints every product identifier
found, so we can tell which generation each metadata set belongs to.
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
WORK = ROOT / ".dsh-tmp" / "meta2"
WORK.mkdir(parents=True, exist_ok=True)
LOG = WORK / "meta2.log"
PROXY = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY
opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))

BUILDS = [("26300.9711", "2b22470a-8b6f-498f-9c88-66f7b9fb56b1"),
          ("26300.9550", "fe47c57f-a77f-41e3-9012-00b4187e3462")]


def log(m):
    line = "%s %s" % (time.strftime("%H:%M:%S"), m)
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def api(path, timeout=240):
    for i in range(4):
        try:
            req = urllib.request.Request("https://api.uupdump.net/" + path, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as ex:
            log("  retry %d: %s" % (i + 1, ex))
            time.sleep(15 * (i + 1))
    return None


products = {}
for tag, uuid in BUILDS:
    log("== build %s" % tag)
    j = api("get.php?id=%s&pack=0&edition=0" % uuid)
    files = ((j or {}).get("response", {}) or {}).get("files") or {}
    log("   files: %d" % len(files))
    cands = [(int(m.get("size") or 0), n, m.get("url")) for n, m in files.items()
             if ("aggregatedmetadata" in n.lower() or "onepackage" in n.lower()
                 or n.lower().endswith(".cab") and ("meta" in n.lower() or "comp" in n.lower()))]
    cands.sort()
    log("   metadata-ish cabs: %d" % len(cands))
    for s, n, u in cands[:14]:
        log("      %10d B  %s" % (s, n))
    for s, n, u in cands[:14]:
        if s > 200 * 1024 * 1024:
            log("      skip (>200MB): %s" % n)
            continue
        target = WORK / n
        if not (target.exists() and target.stat().st_size == s):
            try:
                with opener.open(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=300) as r:
                    target.write_bytes(r.read())
            except Exception as ex:
                log("      download failed %s: %s" % (n, ex))
                continue
        out = WORK / (re.sub(r"[^A-Za-z0-9]+", "_", n)[:60] + "_x")
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["expand.exe", str(target), "-F:*", str(out)], capture_output=True, timeout=600)
        except Exception as ex:
            log("      expand failed: %s" % ex)
            continue
        hits = 0
        for f in list(out.rglob("*"))[:4000]:
            if not f.is_file():
                continue
            try:
                raw = f.read_bytes()
            except Exception:
                continue
            for m in re.finditer(rb"(Windows\.Workload\.[A-Za-z0-9_.]+)", raw):
                products.setdefault(m.group(1).decode(), set()).add("%s:%s" % (tag, n[:28]))
                hits += 1
        log("      %s -> workload identifiers: %d" % (n[:50], hits))

log("")
log("== distinct workload products found ==")
for p in sorted(products):
    log("   %-56s %s" % (p, ",".join(sorted(products[p]))[:70]))
(WORK / "products.json").write_text(json.dumps({k: sorted(v) for k, v in products.items()}, indent=2), encoding="utf-8")
log("DONE")
