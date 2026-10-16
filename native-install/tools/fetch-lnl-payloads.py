"""Fetch only the LNL AI workload payloads we are missing, via HTTP Range from the MSU.

Adapted from the other agent's fetch_selected_payloads.py (same source index and
WIM resource table). Rules honoured here:
  * per-package hard cap 500 MB -> anything larger is SKIPPED and marked as held
  * Microsoft download host allowlist
  * SHA1 verification against the WIM resource table before a file is accepted
"""
import hashlib
import json
import pathlib
import sys
import urllib.request
import zipfile

TOOL = pathlib.Path(r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具")
OUT = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness\ai-packages\lnl-extra")
PROXY = "http://127.0.0.1:7890"
CAP = 500 * 1024 * 1024

PREFIXES = [
    "WindowsWorkload.Data.Analysis.Lnl.1_",
    "WindowsWorkload.Data.ImageSearch.Lnl.1_",
    "WindowsWorkload.Data.SettingsModel.Lnl.1_",
    "WindowsWorkload.PSTokenizerShared.Lnl.3.7_",
    "WindowsWorkload.PSTokenizer.Lnl.2.7_",
    "WindowsWorkload.SemanticText.Lnl.1_",
    "WindowsWorkload.QueryProcessor.Lnl.1_",
    "WindowsWorkload.QueryProcessor.Data.1_",
    "WindowsWorkload.SemanticText.Data.1_",
    "WindowsWorkload.ImageSearch.Data.3_",
    "WindowsWorkload.ImageSearch.Lnl.3_",
    "WindowsWorkload.ImageTextSearch.Data.3_",
    "WindowsWorkload.ImageTextSearch.Lnl.3_",
    "WindowsWorkload.ImageContentModeration.Data.1_",
    "WindowsWorkload.ImageContentModeration.1_",
    "WindowsWorkload.SettingsModel.Data.1_",
    "WindowsWorkload.SettingsModel.Lnl.1_",
    "WindowsWorkload.PSTokenizerShared.Data.3.7_",
]

ALLOWED_HOSTS = ("delivery.mp.microsoft.com", "download.windowsupdate.com", "download.microsoft.com")


def check_url(url):
    from urllib.parse import urlsplit
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    if p.scheme not in ("http", "https"):
        raise ValueError("bad scheme")
    if not any(host == d or host.endswith("." + d) for d in ALLOWED_HOSTS):
        raise ValueError("host outside allowlist: %s" % host)
    return url


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = json.loads((TOOL / "uup-msu-files.json").read_text(encoding="utf-8-sig"))
    entries = json.loads((TOOL / "msu-payloads.json").read_text(encoding="utf-8"))

    # prefer the KB5124010 MSU the resource offsets were computed against
    source = None
    for f in files:
        if "KB5124010" in f["Name"]:
            source = f
            break
    if source is None:
        source = max(files, key=lambda x: int(x["Size"]))
    source_url = check_url(source["Url"])
    print("MSU source : %s  (%.2f GB)" % (source["Name"], int(source["Size"]) / 1073741824), flush=True)

    selected, held = [], []
    for e in entries:
        if not e["name"].endswith(".msix"):
            continue
        if not e["name"].startswith(tuple(PREFIXES)):
            continue
        if e["size"] > CAP:
            held.append({"name": e["name"], "size": e["size"], "reason": ">500MB hold rule"})
        else:
            selected.append(e)

    print("selected %d payloads, held %d" % (len(selected), len(held)), flush=True)
    for h in held:
        print("  HELD %8.1f MB  %s" % (h["size"] / 1048576, h["name"]), flush=True)

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )
    report = []
    for e in selected:
        start, size = e["offset"], e["size"]
        target = OUT / e["name"]
        if target.exists() and target.stat().st_size == size:
            print("skip (already have) %s" % e["name"], flush=True)
            continue
        print("fetching %8.1f MB  %s" % (size / 1048576, e["name"]), flush=True)
        req = urllib.request.Request(
            source_url, headers={"Range": "bytes=%d-%d" % (start, start + size - 1)}
        )
        try:
            resp = opener.open(req, timeout=90)
        except Exception as ex:
            print("  ERROR open: %s" % ex, flush=True)
            report.append({"name": e["name"], "ok": False, "error": str(ex)})
            continue
        if resp.status != 206:
            print("  ERROR status=%s (range not honoured)" % resp.status, flush=True)
            report.append({"name": e["name"], "ok": False, "error": "status %s" % resp.status})
            continue
        partial = target.with_suffix(target.suffix + ".partial")
        got = 0
        with partial.open("wb") as fh:
            remaining = size
            while remaining:
                block = resp.read(min(1048576, remaining))
                if not block:
                    break
                fh.write(block)
                remaining -= len(block)
                got += len(block)
        data = partial.read_bytes()
        sha1 = hashlib.sha1(data).hexdigest()
        if got != size or sha1.lower() != e["sha1"].lower():
            print("  ERROR integrity: got %d/%d sha1=%s expected=%s" % (got, size, sha1, e["sha1"]), flush=True)
            report.append({"name": e["name"], "ok": False, "error": "integrity"})
            continue
        partial.replace(target)
        info = {"name": e["name"], "ok": True, "size": size, "sha1": sha1,
                "sha256": hashlib.sha256(data).hexdigest()}
        try:
            with zipfile.ZipFile(target) as z:
                ident = [n for n in z.namelist() if n == "AppxManifest.xml"]
                if ident:
                    (OUT / (e["name"] + ".AppxManifest.xml")).write_bytes(z.read("AppxManifest.xml"))
                info["has_signature"] = "AppxSignature.p7x" in z.namelist()
        except Exception as ex:
            info["zip_warning"] = str(ex)
        print("  OK  %s" % json.dumps({k: v for k, v in info.items() if k != "sha256"}, ensure_ascii=False), flush=True)
        report.append(info)

    (OUT / "download-report.json").write_text(
        json.dumps({"msu": source, "held": held, "results": report}, indent=2), encoding="utf-8"
    )
    print("DONE  ok=%d fail=%d held=%d" % (
        sum(1 for r in report if r.get("ok")),
        sum(1 for r in report if not r.get("ok")),
        len(held)), flush=True)


if __name__ == "__main__":
    sys.exit(main())
