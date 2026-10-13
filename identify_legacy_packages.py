#!/usr/bin/env python3
"""
identify_legacy_packages.py — 廉价识别旧 MSU 里 GUID 命名包的真正身份

难点：KB5066835 里 56 个包的文件名是 GUID，真正身份在包内 AppxManifest.xml。
      下载整个包（最大 447MB）成本太高。

做法：zip 的中央目录在文件末尾。实现一个 HTTP Range 支撑的文件对象，
      交给标准库 zipfile —— 它只会读 EOCD / 中央目录 / 目标条目的字节。
      读 AppxManifest.xml 通常只需几十 KB。

用法: python identify_legacy_packages.py [--max N]
"""
import argparse
import io
import json
import os
import pathlib
import sys
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

SRC = pathlib.Path(r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具")


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


class HttpRangeFile(io.RawIOBase):
    """最小只读文件对象：seek/read 全部转成 HTTP Range 请求。"""

    def __init__(self, url, base, size):
        self.url = url
        self.base = base        # 该 payload 在 MSU 中的起始偏移
        self.size = size
        self.pos = 0
        self.fetched = 0

    def seekable(self): return True
    def readable(self): return True

    def seek(self, off, whence=0):
        if whence == 0: self.pos = off
        elif whence == 1: self.pos += off
        elif whence == 2: self.pos = self.size + off
        self.pos = max(0, min(self.pos, self.size))
        return self.pos

    def tell(self): return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        start = self.base + self.pos
        end = start + n - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        self.fetched += len(data)
        self.pos += len(data)
        return data

    def readall(self):
        return self.read(-1)


def probe(url, base, size):
    f = HttpRangeFile(url, base, size)
    with zipfile.ZipFile(f) as z:
        mf = z.read("AppxManifest.xml")
        root = ET.fromstring(mf)
        ident = next((n for n in root if n.tag.endswith("Identity")), None)
        info = dict(ident.attrib) if ident is not None else {}
        names = [i.filename for i in z.infolist()]
        sig_present = "AppxSignature.p7x" in names
    return info, names, sig_present, f.fetched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=None, help="最多探测多少个")
    args = ap.parse_args()

    entries = json.loads((SRC / "oct-msu-payloads.json").read_text(encoding="utf-8"))
    msix = [e for e in entries if e.get("name", "").endswith(".msix")]
    msix.sort(key=lambda e: e["size"])
    if args.max:
        msix = msix[:args.max]

    items = json.loads((SRC / "uup-oct-msu-files.json").read_text(encoding="utf-8-sig"))
    src = max(items, key=lambda x: int(x["Size"]))
    url = microsoft_url(src["Url"])
    print(f"源 MSU: {src['Name']}  载荷 {len(msix)} 个\n")

    results, failed = [], []
    total_fetched = 0
    for i, e in enumerate(msix, 1):
        tag = e["name"].split("_")[0]
        try:
            info, names, sig, fetched = probe(url, e["offset"], e["size"])
            total_fetched += fetched
            pkg = info.get("Name", "?")
            results.append({"file": e["name"], "package": pkg,
                            "version": info.get("Version"),
                            "arch": info.get("ProcessorArchitecture"),
                            "size": e["size"], "fetched": fetched,
                            "sha1": e["sha1"], "signature": sig,
                            "dlls": [n for n in names if n.lower().endswith(".dll")]})
            print(f"[{i:2}/{len(msix)}] {tag[:36]:38} -> {pkg}  v{info.get('Version')}  "
                  f"({e['size']/1e6:.1f}MB, 只取 {fetched/1024:.1f}KB)")
        except Exception as ex:
            failed.append({"file": e["name"], "error": str(ex)[:200]})
            print(f"[{i:2}/{len(msix)}] {tag[:36]:38} -> ✗ {str(ex)[:90]}")
        sys.stdout.flush()

    out = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness\legacy-identified.json")
    out.write_text(json.dumps({"source": src["Name"], "packages": results,
                               "failed": failed}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n成功识别 {len(results)} / {len(msix)}   失败 {len(failed)}")
    print(f"共取字节 {total_fetched/1e6:.2f} MB（若全下载需 {sum(e['size'] for e in msix)/1e9:.2f} GB）")
    print(f"结果: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
