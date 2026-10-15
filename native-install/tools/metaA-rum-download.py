"""Route A, final step: download the Windows.Workload.*.rum.json.cab files that
the AggregatedMetadata cab references, expand them, and report each product's
declared payload versions -- so we can compare against what we have locally."""
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
LOG = WORK / "rum-download.log"
PROXY = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY
opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))

# newest build first, then ours
BUILDS = [("26300.9711", "2b22470a-8b6f-498f-9c88-66f7b9fb56b1"),
          ("26300.9550", "fe47c57f-a77f-41e3-9012-00b4187e3462")]


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


products = {}
for tag, uuid in BUILDS:
    log("== build %s" % tag)
    j = api("get.php?id=%s&pack=0&edition=0" % uuid)
    files = ((j or {}).get("response", {}) or {}).get("files") or {}
    rums = [(int(m.get("size") or 0), n, m.get("url")) for n, m in files.items() if n.endswith(".rum.json.cab")]
    log("   rum.json.cab files in listing: %d" % len(rums))
    if not rums:
        log("   (none in this build)")
        continue
    for s, n, u in sorted(rums):
        target = WORK / ("%s_%s" % (tag, n))
        if not (target.exists() and target.stat().st_size == s):
            try:
                with opener.open(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=180) as r:
                    target.write_bytes(r.read())
            except Exception as ex:
                log("      download failed %s: %s" % (n, ex))
                continue
        out = WORK / ("x_" + re.sub(r"[^A-Za-z0-9]+", "_", n)[:58])
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run(["expand.exe", str(target), "-F:*", str(out)], capture_output=True, timeout=300)
        for f in out.rglob("*"):
            if not f.is_file():
                continue
            try:
                meta = json.loads(f.read_bytes().decode("utf-8", "replace"))
            except Exception:
                continue
            for up in meta.get("UpdateProduct", []):
                pid = up.get("ProductIdentifier")
                ver = up.get("ProductVersion")
                ents = up.get("UpdateEntityCollection", [])
                pv = set()
                for e in ents:
                    for pl in e.get("EntityPayload", {}).get("Canonical", []) or []:
                        pn = pl["PayloadName"]
                        if "_" in pn:
                            pv.add(pn.split("_")[1])
                products["%s|%s" % (pid, ver)] = dict(entities=len(ents),
                                                     payload_versions=sorted(pv),
                                                     build=tag)
                log("   %-46s %-16s ents=%-3d payloads=%s" % (pid, ver, len(ents), ",".join(sorted(pv))))

log("")
log("== summary ==")
for k in sorted(products):
    log("   %-64s %s" % (k, products[k]))
(WORK / "A-rum-products.json").write_text(json.dumps(products, indent=2), encoding="utf-8")
log("DONE")
