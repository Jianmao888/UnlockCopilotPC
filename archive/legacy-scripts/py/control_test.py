#!/usr/bin/env python3
"""
control_test.py — 对照实验：产品名是否真的影响服务端返回？

如果 `<Products>PN=<乱写>&V=0.0.0.0</Products>` 与
   `<Products>PN=Windows.Workload.ContentExtraction.amd64&V=0.0.0.0</Products>`
返回完全相同的结果，说明服务端忽略产品名，只是"看到 Products 非空就返回默认集"。

用法: python control_test.py
"""
import html
import re
import sys
import urllib.error
from datetime import datetime, timedelta, timezone

import wu_probe as wp

ENDPOINT = "https://fe3cr.delivery.mp.microsoft.com/ClientWebService/client.asmx"

CASES = [
    ("empty",       "<Products/>"),
    ("garbage",     "<Products>PN=ZZZ.NotAReal.Product.amd64&amp;V=0.0.0.0</Products>"),
    ("garbage2",    "<Products>PN=Foo.Bar.Baz.x64&amp;V=1.2.3.4</Products>"),
    ("workload-P1", "<Products>PN=Windows.Workload.ContentExtraction.amd64&amp;V=0.0.0.0</Products>"),
    ("workload-P2", "<Products>PN=Windows.Workload.Analysis.amd64&amp;V=0.0.0.0</Products>"),
    ("coreai",      "<Products>PN=osclient.coreai.amd64&amp;V=10.0.26100.9549</Products>"),
    ("aifabric",    "<Products>PN=Microsoft.AIFabric.CBS.1.6&amp;V=1.6.951.100</Products>"),
]


def post(cookie, products_xml):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    body = f"""
            <cookie>
                <Expiration>2045-03-11T02:02:48Z</Expiration>
                <EncryptedData>{cookie}</EncryptedData>
            </cookie>
            <parameters>
                <ExpressQuery>false</ExpressQuery>
                {wp.int_list(wp.INSTALLED_NON_LEAF, "InstalledNonLeafUpdateIDs")}
                {wp.int_list(wp.OTHER_CACHED, "OtherCachedUpdateIDs")}
                <SkipSoftwareSync>false</SkipSoftwareSync>
                <NeedTwoGroupOutOfScopeUpdates>true</NeedTwoGroupOutOfScopeUpdates>
                <AlsoPerformRegularSync>false</AlsoPerformRegularSync>
                <ComputerSpec/>
                <ExtendedUpdateInfoParameters>
                    <XmlUpdateFragmentTypes>
                        <XmlUpdateFragmentType>Extended</XmlUpdateFragmentType>
                    </XmlUpdateFragmentTypes>
                    <Locales><string>en-US</string><string>en</string></Locales>
                </ExtendedUpdateInfoParameters>
                <ClientPreferredLanguages><string>en-US</string></ClientPreferredLanguages>
                <ProductsParameters>
                    <SyncCurrentVersionOnly>false</SyncCurrentVersionOnly>
                    <DeviceAttributes>{wp.device_attrs(ver="10.0.26300.9550")}</DeviceAttributes>
                    <CallerAttributes>Interactive=1;IsSeeker=0;</CallerAttributes>
                    {products_xml}
                </ProductsParameters>
            </parameters>
    """
    return wp.soap_post(ENDPOINT, "SyncUpdates", "175df68c-4b91-41ee-b70b-f2208c65438e",
                        ENDPOINT, wp.fmt(now), wp.fmt(now + timedelta(minutes=5)), "Retail", body)


def fingerprint(xml):
    t = html.unescape(xml)
    ids = set(re.findall(r'UpdateIdentity UpdateID="([^"]+)"', t, re.I))
    types = re.findall(r'UpdateType="([^"]+)"', t)
    return len(xml), ids, types


def main():
    wp.CLIENT_WS = ENDPOINT
    try:
        cookie = wp.get_cookie("en-US", "1.81")
    except Exception as e:
        print(f"GetCookie 失败: {str(e)[:200]}")
        return 1
    print(f"cookie OK ({len(cookie)})\n")

    results = {}
    for name, px in CASES:
        try:
            xml = post(cookie, px)
        except urllib.error.HTTPError as e:
            print(f"  {name:14} -> HTTP {e.code}")
            results[name] = None
            continue
        except Exception as e:
            print(f"  {name:14} -> 异常 {str(e)[:120]}")
            results[name] = None
            continue
        ln, ids, types = fingerprint(xml)
        from collections import Counter
        results[name] = (ln, ids, Counter(types))
        print(f"  {name:14} -> {ln:6} 字符  UpdateID={len(ids):3}  {dict(Counter(types))}")
        open(f"ctrl-{name}.xml", "w", encoding="utf-8").write(xml)

    print("\n=== 各请求的 UpdateID 集合是否相同？ ===")
    names = [n for n in results if results[n]]
    if names:
        base = results[names[0]][1]
        for n in names:
            same = "完全相同" if results[n][1] == base else f"不同 (差异 {len(results[n][1] ^ base)})"
            print(f"  {n:14} vs {names[0]:14} -> {same}")

    print("\n=== 有没有任何请求返回 IsLeaf=true 的真实包？ ===")
    for n in names:
        xml = open(f"ctrl-{n}.xml", encoding="utf-8").read()
        t = html.unescape(xml)
        leaf_true = len(re.findall(r"<IsLeaf>true</IsLeaf>", t))
        fnames = re.findall(r'FileName="([^"]+)"', t)
        print(f"  {n:14} IsLeaf=true: {leaf_true}   文件名: {len(fnames)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
