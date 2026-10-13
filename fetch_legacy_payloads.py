#!/usr/bin/env python3
"""
fetch_legacy_payloads.py — 从旧 LCU（KB5066835，3.7 代）按包名下载

KB5066835 里的包文件名是 GUID，身份已由 identify_legacy_packages.py 查明
（结果在 legacy-identified.json）。

用法:
  python fetch_legacy_payloads.py --list                  # 列可选包
  python fetch_legacy_payloads.py --preset 365            # 365 平台所需
  python fetch_legacy_payloads.py --preset lnl            # Lnl 平台所需
  python fetch_legacy_payloads.py --preset core           # 核心（Manager/SessionManager 等）
  python fetch_legacy_payloads.py --name WindowsWorkload.Manager.1 ...
  python fetch_legacy_payloads.py --all --max-size 100    # 全部小于 100MB 的
"""
import argparse
import hashlib
import json
import pathlib
import sys
import time
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

HERE = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
SRC = pathlib.Path(r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具")
OUT = HERE / "ai-packages-legacy"
CHUNK = 1 << 20

PRESETS = {
    # 365 = Windows 365 云 PC 变体（无 NPU，CPU 路径）—— 与本机 workloads.365.json 匹配
    "365": [
        "WindowsWorkload.Manager.1", "WindowsWorkload.SessionManager.1",
        "WindowsWorkload.QueryBlockList.1",
        "WindowsWorkload.Data.ContentExtraction.365.1", "WindowsWorkload.Data.Analysis.365.1",
        "WindowsWorkload.ScrRegDetection.365.1", "WindowsWorkload.SemanticText.365.1",
        "WindowsWorkload.QueryProcessor.365.1", "WindowsWorkload.PSTokenizer.365.2.7",
        "WindowsWorkload.PSOnnxRuntime.365.3.7", "WindowsWorkload.PSTokenizerShared.365.3.7",
        "WindowsWorkload.QueryProcessor.Data.1", "WindowsWorkload.TextRecognition.365.1",
        "WindowsWorkload.PSTokenizerShared.Data.3.7",
    ],
    # Lnl = Intel Lunar Lake，与本机 workloads.lnl.json 匹配
    "lnl": [
        "WindowsWorkload.Manager.1", "WindowsWorkload.SessionManager.1",
        "WindowsWorkload.QueryBlockList.1",
        "WindowsWorkload.Data.ContentExtraction.Lnl.1", "WindowsWorkload.Data.Analysis.Lnl.1",
        "WindowsWorkload.ScrRegDetection.Lnl.1", "WindowsWorkload.SemanticText.Lnl.1",
        "WindowsWorkload.QueryProcessor.Lnl.1", "WindowsWorkload.PSTokenizer.Lnl.2.7",
        "WindowsWorkload.PSOnnxRuntime.Lnl.3.7", "WindowsWorkload.PSTokenizerShared.Lnl.3.7",
        "WindowsWorkload.QueryProcessor.Data.1", "WindowsWorkload.TextRecognition.Lnl.1",
        "WindowsWorkload.ScrRegDetection.Data.1", "WindowsWorkload.SemanticText.Data.1",
    ],
    # 最小核心集
    "core": [
        "WindowsWorkload.Manager.1", "WindowsWorkload.SessionManager.1",
        "WindowsWorkload.QueryBlockList.1",
    ],
}


def microsoft_url(url):
    from urllib.parse import urlsplit, urlunsplit
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    allowed = ("delivery.mp.microsoft.com", "download.windowsupdate.com", "download.microsoft.com")
    if p.scheme not in ("http", "https") or p.username or p.password:
        raise ValueError("unexpected URL form")
    if not any(host == d or host.endswith("." + d) for d in allowed):
        raise ValueError("host outside allowlist")
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))


def sha1_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def download(url, start, size, target, label=""):
    partial = target.with_suffix(target.suffix + ".partial")
    have = partial.stat().st_size if partial.exists() else 0
    if have > size:
        partial.unlink(); have = 0
    if have == size:
        return partial
    req = urllib.request.Request(url, headers={"Range": f"bytes={start+have}-{start+size-1}"})
    t0 = time.time(); done = have
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != 206:
            raise ValueError(f"expected 206 got {r.status}")
        if not r.headers.get("Content-Range", "").startswith(f"bytes {start+have}-{start+size-1}/"):
            raise ValueError("unexpected Content-Range")
        with open(partial, "ab" if have else "wb") as f:
            while True:
                b = r.read(min(CHUNK, size - done))
                if not b:
                    break
                f.write(b); done += len(b)
                if done % (32 << 20) < CHUNK or done == size:
                    el = max(time.time() - t0, 0.01)
                    print(f"\r      {done/1e6:8.2f}/{size/1e6:.2f} MB {(done-have)/el/1e6:6.1f} MB/s",
                          end="", flush=True)
    print()
    if partial.stat().st_size != size:
        raise ValueError("size mismatch")
    return partial


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=list(PRESETS))
    ap.add_argument("--name", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-size", type=float, default=None)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    ident = json.loads((HERE / "legacy-identified.json").read_text(encoding="utf-8"))
    pkgs = ident["packages"]          # {file, package, version, size, sha1, ...}
    entries = {e["name"]: e for e in json.loads((SRC / "oct-msu-payloads.json").read_text(encoding="utf-8"))}
    items = json.loads((SRC / "uup-oct-msu-files.json").read_text(encoding="utf-8-sig"))
    src = max(items, key=lambda x: int(x["Size"]))
    url = microsoft_url(src["Url"])

    # 选择
    if args.preset:
        want = set(PRESETS[args.preset])
        sel = [p for p in pkgs if p["package"] in want]
        got = {p["package"] for p in sel}
        miss = want - got
    elif args.name:
        sel = [p for p in pkgs if p["package"] in set(args.name)]
        miss = set(args.name) - {p["package"] for p in sel}
    elif args.all:
        sel = sorted(pkgs, key=lambda p: p["size"])
        miss = set()
    else:
        sel = []; miss = set()

    if args.max_size:
        sel = [p for p in sel if p["size"] <= args.max_size * 1e6]

    if args.list or not sel:
        print("可用包（已识别 56 个）:")
        for p in sorted(pkgs, key=lambda x: (x["package"] or "")):
            print(f"  {p['size']/1e6:8.2f} MB  {p['package']}  v{p['version']}")
        return 0

    print(f"源 MSU: {src['Name']}")
    print(f"选中 {len(sel)} 个, 共 {sum(p['size'] for p in sel)/1e6:.1f} MB")
    if miss:
        print(f"⚠ 该预设里有 {len(miss)} 个未在旧 MSU 中找到: {sorted(miss)}")
    print()

    OUT.mkdir(parents=True, exist_ok=True)
    ok, failed = [], []
    for i, p in enumerate(sel, 1):
        e = entries.get(p["file"])
        if not e or "offset" not in e:
            print(f"[{i}/{len(sel)}] {p['package']} -> 索引缺 offset，跳过"); continue
        name = p["file"]
        target = OUT / name
        print(f"[{i}/{len(sel)}] {p['package']} v{p['version']}  ({p['size']/1e6:.2f} MB)")
        try:
            if target.exists() and sha1_of(target) == e["sha1"]:
                print("      ✔ 已存在且 SHA1 匹配，跳过"); ok.append(p); continue
            partial = download(url, e["offset"], e["size"], target)
            got = sha1_of(partial)
            if got != e["sha1"]:
                raise ValueError(f"SHA1 mismatch {got}")
            partial.replace(target)
            with zipfile.ZipFile(target) as z:
                mf = z.read("AppxManifest.xml")
                (OUT / (name + ".AppxManifest.xml")).write_bytes(mf)
                root = ET.fromstring(mf)
                ident_el = next((n for n in root if n.tag.endswith("Identity")), None)
                real = dict(ident_el.attrib) if ident_el is not None else {}
                files = [{"name": n.filename, "size": n.file_size} for n in z.infolist() if not n.is_dir()]
            print(f"      ✔ SHA1 通过   包名={real.get('Name')} v{real.get('Version')}")
            ok.append({**p, "identity": real, "files": files,
                       "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
        except Exception as ex:
            print(f"      ✗ {str(ex)[:160]}")
            failed.append({"package": p["package"], "error": str(ex)[:200]})
        sys.stdout.flush()

    (OUT / "_report.json").write_text(
        json.dumps({"source": src["Name"], "downloaded": ok, "failed": failed},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'='*70}\n成功 {len(ok)}   失败 {len(failed)}")
    for f in failed:
        print(f"  ✗ {f['package']}: {f['error'][:110]}")
    print(f"输出: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
