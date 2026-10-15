"""Autonomous fetch: obtain the missing Windows AI workload payloads.

Strategy (no big downloads):
  1. ask uupdump for OUR build (26300.9550) to get a FRESH signed URL for
     Windows11.0-KB5124010-x64.msu (the LCU that carries the AI packages we need)
  2. load the existing WIM resource table (msu-payloads.json) which already has
     {name, offset, size, sha1} for every MSIX inside that MSU
  3. for every product RUM, find entities whose local payload is missing /
     version-mismatched, and range-download exactly those payloads
  4. verify SHA1, keep per-package rules (>500MB => HELD, not downloaded)
"""
import hashlib
import json
import os
import pathlib
import shutil
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
WORK = ROOT / ".dsh-tmp" / "uup"
FETCH = WORK / "fetched"
TOOL = ROOT / "native-install" / "tools"
QING = None
for d in os.listdir(r"C:\Users\jianm\OneDrive"):
    c = pathlib.Path(r"C:\Users\jianm\OneDrive") / d / "ChatGPT" / "2026-10-12" / "qing" / "outputs" / "Windows-AI-UUP-product-metadata" / "KB5066835"
    if c.is_dir():
        QING = c
        break
PROXY = "http://127.0.0.1:7890"
CAP = 500 * 1024 * 1024

LOG = WORK / "auto-fetch.log"
LOG.parent.mkdir(parents=True, exist_ok=True)
FETCH.mkdir(parents=True, exist_ok=True)


def log(msg):
    line = "%s %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))


def get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req, timeout=timeout) as r:
        return r.read()


def api(path):
    for attempt in range(6):
        try:
            return json.loads(get("https://api.uupdump.net/" + path, timeout=120).decode("utf-8", "replace"))
        except Exception as ex:
            log("  uup api retry %d: %s" % (attempt + 1, ex))
            time.sleep(20 * (attempt + 1))
    return None


# ---------------------------------------------------------------- 1. fresh MSU url
def fresh_msu_url():
    log("== step 1: fresh URLs from uupdump for build 26300.9550 (our machine)")
    listing = api("listid.php?search=26300.9550&sortByDate=0&timeSort=desc")
    uuids = []
    if listing and listing.get("response", {}).get("builds"):
        for k, b in listing["response"]["builds"].items():
            if b.get("arch") == "amd64":
                uuids.append((b.get("build", ""), b["uuid"]))
    # also look at the newest overall list in case .9550 is gone
    if not uuids:
        listing = api("listid.php?search=26300&sortByDate=0&timeSort=desc")
        for k, b in (listing or {}).get("response", {}).get("builds", {}).items():
            if b.get("arch") == "amd64":
                uuids.append((b.get("build", ""), b["uuid"]))
    log("  candidate updates: %s" % uuids[:6])
    for build, uuid in uuids:
        j = api("get.php?id=%s" % uuid)
        if not j or "files" not in j.get("response", {}):
            continue
        files = j["response"]["files"]
        for name, meta in files.items():
            if name.startswith("Windows11.0-KB5124010") and name.endswith(".msu"):
                log("  FOUND fresh URL for %s (build %s, %.2f GB)" % (name, build, int(meta["size"]) / 1073741824))
                return name, meta["url"], int(meta["size"])
        log("  build %s has no KB5124010 (files=%d)" % (build, len(files)))
    return None, None, 0


# ---------------------------------------------------------------- 2. payload index
def load_index():
    """Find the WIM resource tables that carry per-payload offsets."""
    idx = {}
    cands = []
    # the tool dir sits next to the metadata pool we already located
    if QING is not None:
        cands += list(QING.parent.parent.glob("**/msu-payloads.json"))
    # explicit well-known locations (Chinese path is fine inside Python)
    cands += [
        pathlib.Path(r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具\msu-payloads.json"),
        pathlib.Path(r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\work\phase3-packages\msu-payloads.json"),
    ]
    seen = set()
    for f in cands:
        try:
            if not f.is_file() or str(f) in seen:
                continue
            seen.add(str(f))
            for e in json.loads(f.read_text(encoding="utf-8")):
                if e.get("name", "").endswith(".msix"):
                    idx.setdefault(e["name"], e)
            log("  payload index from %s (total %d entries)" % (f, len(idx)))
        except Exception as ex:
            log("  skip %s: %s" % (f, ex))
    return idx


# ---------------------------------------------------------------- 3. local identity index
def local_index():
    idx = {}
    trees = list(pathlib.Path(r"C:\Users\jianm\Downloads").glob("Windows-AI-*"))
    trees += [ROOT / "native-install" / "source-analysis365", ROOT / "ai-packages", FETCH]
    for t in trees:
        for f in t.rglob("*.msix"):
            try:
                if f.stat().st_size < 10000:
                    continue
                with zipfile.ZipFile(f) as z:
                    if "AppxManifest.xml" not in z.namelist():
                        continue
                    root = ET.fromstring(z.read("AppxManifest.xml"))
                ident = next(n for n in root if n.tag.endswith("Identity"))
                idx.setdefault(ident.attrib.get("Name"), {})[ident.attrib.get("Version")] = f
            except Exception:
                continue
    log("  local identities indexed: %d names" % len(idx))
    return idx


def main():
    log("################ auto-fetch start")
    _, url, size = fresh_msu_url()
    if not url:
        log("ABORT: no fresh KB5124010 URL found")
        return 1
    idx = load_index()
    if not idx:
        log("ABORT: no payload index")
        return 1
    # The WIM resource table is keyed by the real package file name
    # (WindowsWorkload.Xxx_version_x64__hash.msix); the RUM uses a GUID alias in
    # PayloadName. Build a secondary index keyed by (package, version).
    by_pkg = {}
    for name, e in idx.items():
        parts = name.split("_")
        if len(parts) >= 3 and name.endswith(".msix"):
            by_pkg.setdefault((parts[0], parts[1]), e)
    log("  index keyed by GUID names: %d ; keyed by (package,version): %d" % (len(idx), len(by_pkg)))
    have = local_index()

    # what do we still need?
    need = {}
    for rum in sorted(QING.glob("*.rum.json")):
        meta = json.loads(rum.read_text(encoding="utf-8", errors="replace"))
        for up in meta.get("UpdateProduct", []):
            prod = up["ProductIdentifier"] + "." + up.get("ProductArchitecture", "amd64")
            for ent in up.get("UpdateEntityCollection", []):
                pkg = ent["EntityIdentifier"]["EntityName"].split("_")[0]
                for pl in ent.get("EntityPayload", {}).get("Canonical", []) or []:
                    pname = pl["PayloadName"]
                    if not pname.endswith(".msix"):
                        continue
                    want = pname.split("_")[1]
                    if want in have.get(pkg, {}):
                        continue                     # already have this exact version locally
                    need.setdefault(pname, {"product": prod, "package": pkg, "version": want,
                                            "size": int(pl.get("PayloadSize") or 0)})
    log("== step 2: payloads still needed from the LCU: %d" % len(need))

    # downloads
    report = []
    downloaded = held = nosrc = 0
    for pname, info in sorted(need.items()):
        target = FETCH / pname
        if target.exists() and target.stat().st_size > 10000:
            log("  have already: %s" % pname)
            continue
        e = idx.get(pname) or by_pkg.get((info["package"], info["version"]))
        if not e:
            nosrc += 1
            log("  NO OFFSET in index: %s  (%s / %s)" % (pname, info["package"], info["version"]))
            report.append(dict(payload=pname, status="no-offset", **info))
            continue
        psize = int(e["size"])
        if psize > CAP:
            held += 1
            log("  HELD (>500MB): %s  %.1f MB" % (pname, psize / 1048576))
            report.append(dict(payload=pname, status="held", size=psize, **info))
            continue
        log("  fetching %8.1f MB  %s" % (psize / 1048576, pname))
        start = int(e["offset"])
        req = urllib.request.Request(url, headers={"Range": "bytes=%d-%d" % (start, start + psize - 1)})
        ok = False
        for attempt in range(4):
            try:
                with opener.open(req, timeout=120) as resp:
                    if resp.status != 206:
                        raise RuntimeError("status %s" % resp.status)
                    part = target.with_suffix(".partial")
                    got = 0
                    with part.open("wb") as fh:
                        remaining = psize
                        while remaining:
                            blk = resp.read(min(1 << 20, remaining))
                            if not blk:
                                break
                            fh.write(blk)
                            remaining -= len(blk)
                            got += len(blk)
                data = part.read_bytes()
                if got != psize or hashlib.sha1(data).hexdigest().lower() != e["sha1"].lower():
                    raise RuntimeError("integrity got=%d/%d" % (got, psize))
                part.replace(target)
                ok = True
                break
            except Exception as ex:
                log("    attempt %d failed: %s" % (attempt + 1, ex))
                time.sleep(10 * (attempt + 1))
        if ok:
            downloaded += 1
            report.append(dict(payload=pname, status="downloaded", size=psize, **info))
        else:
            report.append(dict(payload=pname, status="failed", size=psize, **info))

    (WORK / "auto-fetch-report.json").write_text(
        json.dumps(dict(msu_url=url, msu_size=size, needed=len(need), downloaded=downloaded,
                        held=held, no_offset=nosrc, results=report), indent=2), encoding="utf-8")
    log("== done: needed=%d downloaded=%d held=%d no-offset=%d" % (len(need), downloaded, held, nosrc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
