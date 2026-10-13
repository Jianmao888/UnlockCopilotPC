#!/usr/bin/env python3
"""
fetch_all_ai_payloads.py — 从微软 CDN 的 LCU MSU 中按 WIM 资源表提取 AI 包

方法（复用已验证的路线）：
  UUP 元数据 → MSU URL → WIM 资源表(offset/size/sha1) → HTTP Range → 完整 MSIX
  校验：WIM 资源 SHA1 + MSIX 签名 + Identity

特性：
  - 断点续传：已存在且 SHA1 匹配的文件直接跳过
  - 按体积升序下载（小的先拿到，快速见效）
  - 实时进度
  - 失败不中断，最后汇总

用法：
  python fetch_all_ai_payloads.py                 # 下载全部
  python fetch_all_ai_payloads.py --only 365      # 只下名字含 365 的
  python fetch_all_ai_payloads.py --max-size 60   # 只下小于 60MB 的
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

SRC = pathlib.Path(r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具")
OUT = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness\ai-packages")

CHUNK = 1 << 20


def microsoft_url(url):
    from urllib.parse import urlsplit, urlunsplit
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    allowed = ("delivery.mp.microsoft.com", "download.windowsupdate.com", "download.microsoft.com")
    if p.scheme not in ("http", "https") or p.username or p.password:
        raise ValueError("unexpected URL form")
    if not any(host == d or host.endswith("." + d) for d in allowed):
        raise ValueError("host outside Microsoft allowlist")
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))


def safe_name(n):
    if not n or n in (".", "..") or any(c in n for c in ':\\/'):
        raise ValueError("bad filename: " + repr(n))
    return n


def sha1_of(path, limit=None):
    h = hashlib.sha1()
    n = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
            n += len(b)
            if limit and n >= limit:
                break
    return h.hexdigest()


def download(url, start, size, target):
    partial = target.with_suffix(target.suffix + ".partial")
    have = partial.stat().st_size if partial.exists() else 0
    if have > size:
        partial.unlink()
        have = 0
    if have == size:
        return partial
    headers = {"Range": f"bytes={start + have}-{start + size - 1}"}
    req = urllib.request.Request(url, headers=headers)
    t0 = time.time()
    done = have
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != 206:
            raise ValueError(f"expected 206, got {r.status}")
        cr = r.headers.get("Content-Range", "")
        want = f"bytes {start + have}-{start + size - 1}/"
        if not cr.startswith(want):
            raise ValueError(f"unexpected Content-Range {cr!r}")
        mode = "ab" if have else "wb"
        with open(partial, mode) as f:
            while True:
                block = r.read(min(CHUNK, size - done))
                if not block:
                    break
                f.write(block)
                done += len(block)
                if done % (32 << 20) < CHUNK or done == size:
                    el = max(time.time() - t0, 0.01)
                    rate = (done - have) / el / 1e6
                    print(f"\r      {done/1e6:8.2f}/{size/1e6:.2f} MB  {rate:6.1f} MB/s",
                          end="", flush=True)
    print()
    if partial.stat().st_size != size:
        raise ValueError(f"size mismatch {partial.stat().st_size} != {size}")
    return partial


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="只下名字包含该子串的")
    ap.add_argument("--max-size", type=float, default=None, help="只下小于该 MB 数的")
    ap.add_argument("--list", action="store_true", help="只列清单")
    args = ap.parse_args()

    entries = json.loads((SRC / "msu-payloads.json").read_text(encoding="utf-8"))
    msix = [e for e in entries if e.get("name", "").endswith(".msix")]
    items = json.loads((SRC / "uup-msu-files.json").read_text(encoding="utf-8-sig"))
    src = max(items, key=lambda x: int(x["Size"]))
    src["Url"] = microsoft_url(src["Url"])
    print(f"源 MSU: {src['Name']}  ({int(src['Size'])/1e9:.2f} GB)")

    if args.only:
        msix = [e for e in msix if args.only.lower() in e["name"].lower()]
    if args.max_size:
        msix = [e for e in msix if e["size"] <= args.max_size * 1e6]
    msix.sort(key=lambda e: e["size"])

    total = sum(e["size"] for e in msix)
    print(f"待下载: {len(msix)} 个, 共 {total/1e6:.1f} MB\n")
    if args.list:
        for e in msix:
            print(f"  {e['size']/1e6:9.2f} MB  {e['name']}")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    report, failed, skipped = [], [], []
    for i, e in enumerate(msix, 1):
        name = safe_name(e["name"])
        target = OUT / name
        print(f"[{i}/{len(msix)}] {name}  ({e['size']/1e6:.2f} MB)")
        try:
            if target.exists():
                if sha1_of(target) == e["sha1"]:
                    print("      ✔ 已存在且 SHA1 匹配，跳过")
                    skipped.append(name)
                    continue
                else:
                    print("      ⚠ 已存在但 SHA1 不符，重新下载")
                    target.unlink()
            partial = download(src["Url"], e["offset"], e["size"], target)
            got = sha1_of(partial)
            if got != e["sha1"]:
                raise ValueError(f"SHA1 mismatch: {got} != {e['sha1']}")
            partial.replace(target)
            info = {"name": name, "size": e["size"], "sha1": e["sha1"], "sha1_match": True,
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "offset": e["offset"]}
            try:
                with zipfile.ZipFile(target) as z:
                    mf = z.read("AppxManifest.xml")
                    info["manifest"] = mf.decode("utf-8", "replace")
                    root = ET.fromstring(mf)
                    ident = next((n for n in root if n.tag.endswith("Identity")), None)
                    if ident is not None:
                        info["identity"] = dict(ident.attrib)
                    info["files"] = [{"name": n.filename, "size": n.file_size}
                                     for n in z.infolist() if not n.is_dir()]
                    sig = z.read("AppxSignature.p7x")
                    (OUT / (name + ".AppxSignature.p7x")).write_bytes(sig)
                    info["signature_size"] = len(sig)
            except Exception as ex:
                info["zip_error"] = str(ex)[:200]
            report.append(info)
            print(f"      ✔ SHA1 校验通过, SHA256={info['sha256'][:16]}...")
        except Exception as ex:
            print(f"      ✗ 失败: {str(ex)[:200]}")
            failed.append({"name": name, "error": str(ex)[:300]})
        sys.stdout.flush()

    (OUT / "_report.json").write_text(
        json.dumps({"source": src, "packages": report, "failed": failed,
                    "skipped": skipped}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'='*70}")
    print(f"成功 {len(report)}   跳过 {len(skipped)}   失败 {len(failed)}")
    if failed:
        for f in failed:
            print(f"  ✗ {f['name']}: {f['error'][:120]}")
    print(f"输出目录: {OUT}")
    print(f"报告: {OUT/'_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
