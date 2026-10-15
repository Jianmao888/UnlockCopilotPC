"""Route A, the real replication: pull `onepackage.AggregatedMetadata.cab` out of
the KB5124010 MSU (80 KB, by byte range) and read the workload RUMs it carries.

This is the same file the previous pool contained (which yielded the OLD RUMs);
taking it from the NEW LCU should yield the NEW-generation product definitions.
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
WORK = ROOT / ".dsh-tmp" / "onepkg"
WORK.mkdir(parents=True, exist_ok=True)
LOG = WORK / "onepkg.log"
PROXY = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY
opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
UUID = "fe47c57f-a77f-41e3-9012-00b4187e3462"     # build 26300.9550


def log(m):
    line = "%s %s" % (time.strftime("%H:%M:%S"), m)
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# index that carries offsets for KB5124010
idx_path = None
for d in os.listdir(r"C:\Users\jianm\OneDrive"):
    p = pathlib.Path(r"C:\Users\jianm\OneDrive") / d / "ChatGPT" / "2026-10-12" / "qing" / "outputs" / "Windows-AI-包获取核验" / "提取工具" / "msu-payloads.json"
    if p.exists():
        idx_path = p
        break
entries = json.loads(idx_path.read_text(encoding="utf-8"))
log("index: %s (%d entries)" % (idx_path, len(entries)))

# fresh MSU url
j = None
for i in range(4):
    try:
        req = urllib.request.Request("https://api.uupdump.net/get.php?id=%s&pack=0&edition=0" % UUID,
                                     headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=180) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        break
    except Exception as ex:
        log("  url retry %d: %s" % (i + 1, ex))
        time.sleep(15 * (i + 1))
files = ((j or {}).get("response", {}) or {}).get("files") or {}
msu = None
for n, m in files.items():
    if n.startswith("Windows11.0-KB5124010") and n.endswith(".msu"):
        msu = m["url"]
        break
log("fresh MSU url: %s" % (msu[:80] if msu else "(none)"))

targets = [e for e in entries if e.get("name", "").lower() == "onepackage.aggregatedmetadata.cab"]
log("targets in index: %s" % [(e["name"], e["size"]) for e in targets])
for e in targets:
    start, size = int(e["offset"]), int(e["size"])
    out = WORK / "onepackage.AggregatedMetadata.cab"
    req = urllib.request.Request(msu, headers={"Range": "bytes=%d-%d" % (start, start + size - 1),
                                               "User-Agent": "Mozilla/5.0"})
    with opener.open(req, timeout=180) as r:
        data = r.read()
    out.write_bytes(data)
    log("  downloaded %s (%d bytes)" % (out.name, len(data)))
    x = WORK / "x"
    if x.exists():
        shutil.rmtree(x)
    x.mkdir(parents=True, exist_ok=True)
    subprocess.run(["expand.exe", str(out), "-F:*", str(x)], capture_output=True, timeout=300)
    allf = [f for f in x.rglob("*") if f.is_file()]
    log("  expanded files: %d" % len(allf))
    # second pass for nested cabs
    for f in list(allf):
        if f.suffix.lower() == ".cab":
            y = WORK / ("y_" + re.sub(r"[^A-Za-z0-9]+", "_", f.name)[:60])
            if y.exists():
                shutil.rmtree(y)
            y.mkdir(parents=True, exist_ok=True)
            subprocess.run(["expand.exe", str(f), "-F:*", str(y)], capture_output=True, timeout=300)
            allf += [g for g in y.rglob("*") if g.is_file()]
    log("  total files after nested expand: %d" % len(allf))
    products = {}
    for f in allf:
        raw = f.read_bytes()
        txt = raw.decode("utf-8", "ignore")
        for m in re.finditer(r'"ProductIdentifier"\s*:\s*"([^"]+)"', txt):
            pid = m.group(1)
            ver = None
            mv = re.search(r'"ProductVersion"\s*:\s*"([^"]+)"', txt)
            if mv:
                ver = mv.group(1)
            ents = re.findall(r'"EntityName"\s*:\s*"([^"]+)"', txt)
            pays = re.findall(r'"PayloadName"\s*:\s*"([^"]+)"', txt)
            products["%s|%s" % (pid, ver)] = dict(file=f.name, entities=len(ents),
                                                 payloads=len(pays),
                                                 payload_versions=sorted({p.split("_")[1] for p in pays if "_" in p}))
        if "Windows.Workload" in txt:
            names = sorted(set(re.findall(r"Windows\.Workload\.[A-Za-z0-9_.]+", txt)))
            log("   %s -> %d workload names" % (f.name[:50], len(names)))
    log("")
    log("== products found in onepackage.AggregatedMetadata.cab ==")
    for k, v in sorted(products.items()):
        log("   %-52s ents=%-3d payloads=%-3d versions=%s" % (k, v["entities"], v["payloads"], ",".join(v["payload_versions"])))
    (WORK / "onepkg-products.json").write_text(json.dumps(products, indent=2), encoding="utf-8")
log("DONE")
