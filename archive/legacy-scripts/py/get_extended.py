#!/usr/bin/env python3
"""
get_extended.py — 对 SyncUpdates 返回的更新调 GetExtendedUpdateInfo2 取详情

目的：确认服务端在"声明了 Windows.Workload.* 产品"后返回的 34 个更新里，
      到底有没有那个模型包。

用法: python get_extended.py [响应文件]
默认读取 dr2-prod-P1-text.xml
"""
import html
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import wu_probe as wp

ENDPOINT = "https://fe3cr.delivery.mp.microsoft.com/ClientWebService/client.asmx"
SECURED = ENDPOINT + "/secured"


def get_ids(xmlfile):
    raw = open(xmlfile, encoding="utf-8").read()
    t = html.unescape(raw)
    pairs = re.findall(
        r'<UpdateIdentity[^>]*UpdateID="([^"]+)"[^>]*RevisionNumber="([^"]*)"', t)
    seen = []
    for uid, rev in pairs:
        if (uid, rev) not in seen:
            seen.append((uid, rev))
    return seen


def extended_info(ids):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    idxml = "".join(
        f'<UpdateIdentity UpdateID="{u}" RevisionNumber="{r or 1}" />' for u, r in ids)
    body = f"""
            <updateIDs>{idxml}</updateIDs>
            <infoTypes>
                <XmlUpdateFragmentType>Extended</XmlUpdateFragmentType>
                <XmlUpdateFragmentType>LocalizedProperties</XmlUpdateFragmentType>
                <XmlUpdateFragmentType>FileUrl</XmlUpdateFragmentType>
            </infoTypes>
            <deviceAttributes>{wp.device_attrs(ver="10.0.26300.9550")}</deviceAttributes>
    """
    return wp.soap_post(SECURED, "GetExtendedUpdateInfo2",
                        "3d5c2a41-9e3f-4e2a-9c1d-6b8a7f0e1d22",
                        SECURED, wp.fmt(now), wp.fmt(now + timedelta(minutes=5)),
                        "Retail", body)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "dr2-prod-P1-text.xml"
    ids = get_ids(src)
    print(f"从 {src} 取到 {len(ids)} 个 UpdateIdentity")

    # 先取 cookie（要用 fe3cr 端点）
    wp.CLIENT_WS = ENDPOINT
    try:
        cookie = wp.get_cookie("en-US", "1.81")
        print(f"GetCookie OK ({len(cookie)})")
    except Exception as e:
        print(f"GetCookie 失败: {str(e)[:200]}")
        return 1

    try:
        xml = extended_info(ids)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"HTTP {e.code}: {body[:800]}")
        return 1
    except Exception as e:
        print(f"失败: {str(e)[:400]}")
        return 1

    print(f"响应 {len(xml)} 字符\n")
    open("extended-out.xml", "w", encoding="utf-8").write(xml)

    t = html.unescape(xml)
    print("=== 标题 / 描述 ===")
    for tag in ("Title", "Description", "SupportUrl", "MoreInfoUrl"):
        vals = []
        for m in re.finditer(rf"<{tag}>([^<]*)</{tag}>", t):
            v = m.group(1).strip()
            if v and v not in vals:
                vals.append(v)
        if vals:
            print(f"\n-- {tag} ({len(vals)}) --")
            for v in vals[:50]:
                print("   " + v[:160])

    print("\n=== 文件名 / 下载 URL ===")
    files = re.findall(r'<File[^>]*FileName="([^"]+)"', t)
    urls = re.findall(r"<Url>([^<]+)</Url>", t)
    print(f"  File 元素 {len(files)} 个, Url {len(urls)} 个")
    for f in sorted(set(files))[:40]:
        print("   " + f[:160])
    for u in sorted(set(urls))[:10]:
        print("   URL " + u[:160])

    print("\n=== 关键字搜索 ===")
    for kw in ("Workload", "ContentExtraction", "Analysis", "Onnx", "Semantic",
               "TextRecognition", "AIFabric", "SessionManager", "Model"):
        hits = sorted(set(re.findall(rf"[\w\.\- ]{{0,50}}{kw}[\w\.\- ]{{0,50}}", t, re.I)))
        if hits:
            print(f"  [{kw}] {len(hits)}:")
            for x in hits[:10]:
                print("      " + x.strip()[:140])
    return 0


if __name__ == "__main__":
    sys.exit(main())
