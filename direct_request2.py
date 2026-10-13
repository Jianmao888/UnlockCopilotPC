#!/usr/bin/env python3
"""
direct_request2.py — 对比基线与产品请求，检查响应差异

用法: python direct_request2.py
输出: baseline.xml / prod_text.xml / prod_two.xml / caller_pn.xml
"""
import re
import ssl
import sys
import urllib.error
from datetime import datetime, timedelta, timezone

import wu_probe as wp

ENDPOINT = "https://fe3cr.delivery.mp.microsoft.com/ClientWebService/client.asmx"
P1 = "Windows.Workload.ContentExtraction.amd64"
P2 = "Windows.Workload.Analysis.amd64"


def post(body_action, cookie, extra_products, caller=None):
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
                    <CallerAttributes>{caller or "Interactive=1;IsSeeker=0;"}</CallerAttributes>
                    {extra_products}
                </ProductsParameters>
            </parameters>
    """
    return wp.soap_post(ENDPOINT, "SyncUpdates", "175df68c-4b91-41ee-b70b-f2208c65438e",
                        ENDPOINT, wp.fmt(now), wp.fmt(now + timedelta(minutes=5)), "Retail", body)


def analyze(name, xml):
    if xml is None:
        print(f"  {name:16} -> 失败")
        return None
    ids = re.findall(r'UpdateIdentity UpdateID="([^"]+)"', xml)
    files = re.findall(r'<File[^>]*FileName="([^"]+)"', xml)
    wl = [x for x in (ids + files) if "orkload" in x or "ontentExtraction" in x or "Analysis" in x]
    print(f"  {name:16} -> {len(xml):7} 字符  UpdateID={len(ids):3}  File={len(files):3}  workload相关={len(wl)}")
    for w in wl[:10]:
        print(f"        ★ {w}")
    return xml


def main():
    wp.CLIENT_WS = ENDPOINT
    cookie = wp.get_cookie("en-US", "1.81")
    print(f"cookie OK ({len(cookie)})\n")

    cases = [
        ("baseline",         "<Products/>"),
        ("prod-P1-text",     f"<Products>PN={P1}&amp;V=0.0.0.0</Products>"),
        ("prod-both-text",   f"<Products>PN={P1}&amp;V=0.0.0.0;PN={P2}&amp;V=0.0.0.0</Products>"),
        ("prod-P1-P2-elem",  f"<Products><string>PN={P1}&amp;V=0.0.0.0</string>"
                             f"<string>PN={P2}&amp;V=0.0.0.0</string></Products>"),
    ]
    saved = {}
    for name, px in cases:
        try:
            xml = post("SyncUpdates", cookie, px)
        except urllib.error.HTTPError as e:
            print(f"  {name:16} -> HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
            xml = None
        except Exception as e:
            print(f"  {name:16} -> 异常: {str(e)[:200]}")
            xml = None
        analyze(name, xml)
        if xml:
            open(f"dr2-{name}.xml", "w", encoding="utf-8").write(xml)
            saved[name] = xml
        print()

    # caller attributes 变体
    print("--- CallerAttributes 里带 PN ---")
    try:
        xml = post("SyncUpdates", cookie, "<Products/>",
                   caller=f"Interactive=1;IsSeeker=0;PN={P1}&V=0.0.0.0;")
        analyze("caller-PN", xml)
        if xml: open("dr2-caller-PN.xml", "w", encoding="utf-8").write(xml)
    except urllib.error.HTTPError as e:
        print(f"  caller-PN        -> HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")
    except Exception as e:
        print(f"  caller-PN        -> 异常: {str(e)[:200]}")

    print("\n=== 差异对比（与 baseline 相比新增/减少的 UpdateID）===")
    base = saved.get("baseline")
    if base:
        bi = set(re.findall(r'UpdateIdentity UpdateID="([^"]+)"', base))
        for name, xml in saved.items():
            if name == "baseline":
                continue
            xi = set(re.findall(r'UpdateIdentity UpdateID="([^"]+)"', xml))
            print(f"  {name:16}  新增 {len(xi-bi):3}  消失 {len(bi-xi):3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
