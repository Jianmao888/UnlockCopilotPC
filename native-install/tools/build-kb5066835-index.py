"""Build a fresh WIM payload index for KB5066835 (the LCU that carries the older
1.2509.1022.0 / 1.7.817.0 AI workload packages we are missing).

Everything is done with HTTP range reads; the 3.5 GB MSU is never downloaded.
Written in Python (not PowerShell) because the tool directory path contains
non-ASCII characters that PowerShell 5.1 mis-decodes.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
WORK = ROOT / ".dsh-tmp" / "uup"
WORK.mkdir(parents=True, exist_ok=True)
LOG = WORK / "build-index.log"
PROXY = "http://127.0.0.1:7890"
PY = r"C:\Users\jianm\AppData\Local\Programs\Python\Python312\python.exe"
os.environ["HTTP_PROXY"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY

opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))


def log(m):
    line = "%s %s" % (time.strftime("%H:%M:%S"), m)
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def api(path, timeout=120):
    for i in range(5):
        try:
            req = urllib.request.Request("https://api.uupdump.net/" + path, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as ex:
            log("  api retry %d: %s" % (i + 1, ex))
            time.sleep(15 * (i + 1))
    return None


# ---- locate the other agent's extraction tool directory (Chinese path is fine here)
tool = None
base = pathlib.Path(r"C:\Users\jianm\OneDrive")
for d in base.iterdir():
    cand = d / "ChatGPT" / "2026-10-12" / "qing" / "outputs"
    if not cand.is_dir():
        continue
    for sub in cand.iterdir():
        t = sub / "提取工具"
        if t.is_dir() and (t / "msu_range_probe.py").is_file():
            tool = t
            break
    if tool:
        break
if tool is None:
    log("tool dir not found")
    sys.exit(1)
log("tool dir: %s" % tool)

# ---- fresh URL for KB5066835
log("== step 1: fresh URL for KB5066835 via uupdump")
listing = api("listid.php?search=5066835&sortByDate=0&timeSort=desc")
uuids = []
for k, b in ((listing or {}).get("response", {}).get("builds", {}) or {}).items():
    if b.get("arch") == "amd64":
        uuids.append((b.get("build"), b["uuid"]))
log("  candidate builds: %s" % [u[0] for u in uuids][:8])

found = None
for build, uuid in uuids:
    j = api("get.php?id=%s" % uuid)
    files = ((j or {}).get("response", {}) or {}).get("files") or {}
    for name, meta in files.items():
        if "KB5066835" in name and name.endswith(".msu"):
            found = dict(name=name, size=int(meta["size"]), url=meta["url"], build=build)
            break
    if found:
        break
    log("  build %s: no KB5066835 msu (files=%d)" % (build, len(files)))
    time.sleep(5)
if not found:
    log("ABORT: no KB5066835 msu found in uupdump")
    sys.exit(1)
log("  FOUND %s (build %s, %.2f GB)" % (found["name"], found["build"], found["size"] / 1073741824))

# ---- write the files json the probes expect
files_json = tool / "uup-msu-files.json"
if files_json.exists():
    shutil.copy2(files_json, WORK / "uup-msu-files.orig.json")
files_json.write_text(json.dumps([{"Name": found["name"], "Size": str(found["size"]),
                                   "Url": found["url"], "Sha256": ""}], indent=2), encoding="utf-8")
log("  wrote %s" % files_json)

# ---- run the three probes
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
for script, args in (("msu_range_probe.py", ["uup-msu-files.json", "msu"]),
                     ("wim_metadata_probe.py", ["uup-msu-files.json", "msu"]),
                     ("wim_list_payloads.py", ["msu"])):
    log("== running %s %s" % (script, " ".join(args)))
    try:
        p = subprocess.run([PY, "-u", script] + args, cwd=str(tool), env=env,
                           capture_output=True, text=True, timeout=900)
        for line in (p.stdout or "").splitlines()[-12:]:
            log("   " + line)
        for line in (p.stderr or "").splitlines()[-8:]:
            log("   [err] " + line)
        log("   exit=%s" % p.returncode)
    except Exception as ex:
        log("   FAILED: %s" % ex)

# ---- inspect the produced index
idx = tool / "msu-payloads.json"
if idx.exists():
    try:
        entries = json.loads(idx.read_text(encoding="utf-8"))
        log("  index entries now: %d" % len(entries))
        shutil.copy2(idx, WORK / "msu-payloads-kb5066835.json")
        log("  saved copy -> %s" % (WORK / "msu-payloads-kb5066835.json"))
        names = [e["name"] for e in entries if e.get("name", "").endswith(".msix")]
        log("  payload names in index: %d" % len(names))
        for n in sorted(names)[:40]:
            log("     " + n)
    except Exception as ex:
        log("  index parse failed: %s" % ex)
else:
    log("  no index produced")
log("DONE")
