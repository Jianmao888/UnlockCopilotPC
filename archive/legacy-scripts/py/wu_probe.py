#!/usr/bin/env python3
"""
wu_probe.py — 可配置的 Windows Update SyncUpdates 探针

用途：向 Microsoft 的 WU ClientWebService 发送 SyncUpdates 请求，
      观察在给定"设备属性"和"产品/分类过滤"下，服务端返回哪些更新。

背景：WindowsWorkload.* 模型包通过 UUP 产品
      ms-uup://Product/com.microsoft.windows.workload.* 下发。
      本探针用于找出对应的 WuCategoryId 或产品标识。

用法：
  python wu_probe.py --baseline                 # 不带任何过滤，看服务端默认给什么
  python wu_probe.py --category <ID>            # 用 FilterAppCategoryIds 过滤
  python u_probe.py --product <ID>              # 用 Products 过滤
  python wu_probe.py --category X --raw out.xml # 保存原始响应

不修改系统。只是 HTTP 请求。
"""

import argparse
import random
import ssl
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

_SSL_CTX = ssl._create_unverified_context()

CLIENT_WS = "https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx"
FE3_SECURED = "https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx/secured"

# 来自真实 WU 流量的已安装更新 ID 列表
INSTALLED_NON_LEAF = [
    1, 2, 3, 11, 19, 544, 549, 2359974, 2359977, 5169044, 8788830,
    23110993, 23110994, 54341900, 54343656, 59830006, 59830007, 59830008,
    60484010, 62450018, 62450019, 62450020, 66027979, 66053150, 97657898,
    98822896, 98959022, 98959023, 98959024, 98959025, 98959026, 104433538,
    104900364, 105489019, 117765322, 129905029, 130040031, 132387090,
    132393049, 133399034, 138537048, 140377312, 143747671, 158941041,
    158941042, 158941043, 158941044, 159123858, 159130928, 164836897,
    164847386, 164848327, 164852241, 164852246, 164852252, 164852253,
]
OTHER_CACHED = [
    10, 17, 2359977, 5143990, 5169043, 5169047, 8806526, 9125350, 9154769,
    10809856, 23110995, 23110996, 23110999, 23111000, 23111001, 23111002,
    23111003, 23111004, 24513870, 28880263, 30077688, 30486944, 30526991,
    30528442, 30530496, 30530501, 30530504, 30530962, 30535326, 30536242,
    30539913, 30545142, 30545145, 30545488, 30546212, 30547779, 30548797,
    30548860, 30549262, 30551160, 30551161, 30551164, 30553016, 30553744,
    30554014, 30559008, 30559011, 30560006, 30560011, 30561006, 30563261,
]


def fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def fmt7(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond:07d}Z"


def envelope(action, message_id, to_url, created, expires, ticket, body):
    return f"""<s:Envelope xmlns:a="http://www.w3.org/2005/08/addressing" xmlns:s="http://www.w3.org/2003/05/soap-envelope">
    <s:Header>
        <a:Action s:mustUnderstand="1">http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService/{action}</a:Action>
        <a:MessageID>urn:uuid:{message_id}</a:MessageID>
        <a:To s:mustUnderstand="1">{to_url}</a:To>
        <o:Security s:mustUnderstand="1" xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <Timestamp xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
                <Created>{created}</Created>
                <Expires>{expires}</Expires>
            </Timestamp>
            <wuws:WindowsUpdateTicketsToken wsu:id="ClientMSA"
                xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
                xmlns:wuws="http://schemas.microsoft.com/msus/2014/10/WindowsUpdateAuthorization">
                <TicketType Name="MSA" Version="1.0" Policy="MBI_SSL">
                    {ticket}
                </TicketType>
            </wuws:WindowsUpdateTicketsToken>
        </o:Security>
    </s:Header>
    <s:Body>
        <{action} xmlns="http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService">
            {body}
        </{action}>
    </s:Body>
</s:Envelope>"""


def soap_post(url, action, message_id, to_url, created, expires, ticket, body):
    env = envelope(action, message_id, to_url, created, expires, ticket, body)
    req = urllib.request.Request(
        url, data=env.encode("utf-8"),
        headers={"Content-Type": "application/soap+xml; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=90) as resp:
        return resp.read().decode("utf-8", errors="replace")


def int_list(ids, tag):
    return f"<{tag}>" + "".join(f"<int>{i}</int>" for i in ids) + f"</{tag}>"


def device_attrs(locale="en-US", sku=48, ver="10.0.26100.1", extra=""):
    return (
        "BranchReadinessLevel=CB;CurrentBranch=rs_prerelease;OEMModel=Virtual Machine;"
        "FlightRing=WIS;AttrDataVer=21;SystemManufacturer=Microsoft Corporation;"
        f"InstallLanguage={locale};OSUILocale={locale};InstallationType=Client;"
        "FlightingBranchName=external;FirmwareVersion=Hyper-V UEFI Release v2.5;"
        f"SystemProductName=Virtual Machine;OSSkuId={sku};FlightContent=Branch;"
        "App=WU;OEMName_Uncleaned=Microsoft Corporation;"
        f"AppVer={ver};OSArchitecture=AMD64;SystemSKU=None;"
        "UpdateManagementGroup=2;IsFlightingEnabled=1;IsDeviceRetailDemo=0;"
        f"TelemetryLevel=3;OSVersion={ver};DeviceFamily=Windows.Desktop;" + extra
    )


def get_cookie(locale, protocol_version="1.40"):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    created = fmt(now)
    expires = fmt(now + timedelta(days=27, seconds=random.randint(-21600, 21600)))
    body = f"""
        <oldCookie></oldCookie>
        <lastChange>{fmt7(now - timedelta(days=730))}</lastChange>
        <currentTime>{fmt(now + timedelta(milliseconds=7))}</currentTime>
        <protocolVersion>{protocol_version}</protocolVersion>
    """
    xml = soap_post(CLIENT_WS, "GetCookie", "b9b43757-2247-4d7b-ae8f-a71ba8a22386",
                    CLIENT_WS, created, expires, "<User />", body)
    root = ET.fromstring(xml)
    for el in root.iter():
        if el.tag.endswith("EncryptedData") and el.text:
            return el.text
    raise RuntimeError("未能取得 cookie:\n" + xml[:2000])


def sync_updates(cookie, category_ids=None, products=None, products_xml=None,
                 also_regular=False, dev_extra="", os_ver="10.0.26100.1"):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    created = fmt(now)
    expires = fmt(now + timedelta(minutes=5))
    now_ms = now + timedelta(milliseconds=7)

    if category_ids:
        cats = "".join(
            f"<CategoryIdentifier><Id>{c}</Id></CategoryIdentifier>" for c in category_ids)
        filter_xml = f"<FilterAppCategoryIds>{cats}</FilterAppCategoryIds>"
        treat = "<TreatAppCategoryIdsAsInstalled>true</TreatAppCategoryIdsAsInstalled>"
    else:
        filter_xml = ""
        treat = ""

    if products_xml is not None:
        prod_xml = products_xml
    elif products:
        prod_xml = "<Products>" + "".join(
            f'<Product Id="{p}" />' for p in products) + "</Products>"
    else:
        prod_xml = "<Products/>"

    body = f"""
            <cookie>
                <Expiration>2045-03-11T02:02:48Z</Expiration>
                <EncryptedData>{cookie}</EncryptedData>
            </cookie>
            <parameters>
                <ExpressQuery>false</ExpressQuery>
                {int_list(INSTALLED_NON_LEAF, "InstalledNonLeafUpdateIDs")}
                {int_list(OTHER_CACHED, "OtherCachedUpdateIDs")}
                <SkipSoftwareSync>false</SkipSoftwareSync>
                <NeedTwoGroupOutOfScopeUpdates>true</NeedTwoGroupOutOfScopeUpdates>
                {filter_xml}
                {treat}
                <AlsoPerformRegularSync>{"true" if also_regular else "false"}</AlsoPerformRegularSync>
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
                    <DeviceAttributes>{device_attrs(ver=os_ver, extra=dev_extra)}</DeviceAttributes>
                    <CallerAttributes>Interactive=1;IsSeeker=0;</CallerAttributes>
                    {prod_xml}
                </ProductsParameters>
            </parameters>
    """
    xml = soap_post(CLIENT_WS, "SyncUpdates", "175df68c-4b91-41ee-b70b-f2208c65438e",
                    CLIENT_WS, created, expires, "Retail", body)
    return xml


def summarize(xml, label):
    """打印响应摘要。"""
    text = xml.replace("&lt;", "<").replace("&gt;", ">")
    try:
        root = ET.fromstring(text)
    except Exception as e:
        print(f"  [{label}] XML 解析失败: {e}")
        print("  原始响应前 800 字符:")
        print("   " + xml[:800].replace("\n", "\n   "))
        return
    # SOAP Fault?
    for el in root.iter():
        if el.tag.endswith("Fault"):
            print(f"  [{label}] SOAP Fault:")
            for c in el.iter():
                if c.text and c.text.strip():
                    print(f"     {c.tag.split('}')[-1]}: {c.text.strip()[:200]}")
            return
        if el.tag.endswith("Result") and el.text is not None and el.text.strip():
            print(f"  [{label}] Result = {el.text.strip()[:200]}")

    names = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("UpdateIdentity",):
            uid = el.get("UpdateID", "")
            rev = el.get("RevisionNumber", "")
            if uid:
                names.append((uid, rev))
        if tag == "File":
            fn = el.get("FileName", "")
            iid = el.get("InstallerSpecificIdentifier", "")
            if fn or iid:
                names.append(("FILE", fn or iid))
    print(f"  [{label}] 响应 {len(xml)} 字符, 命中 {len(names)} 个身份/文件")
    for n in names[:60]:
        print(f"     {n[0]}  {n[1]}")
    if len(names) > 60:
        print(f"     ... 还有 {len(names)-60} 个")
    if not names:
        print("     (无 UpdateIdentity / File 元素)")
        # 打印结构便于诊断
        seen = []
        for el in root.iter():
            t = el.tag.split("}")[-1]
            if t not in seen:
                seen.append(t)
        print("     响应中的元素名: " + ", ".join(seen[:40]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", action="append", default=None, help="FilterAppCategoryIds 的值，可重复")
    ap.add_argument("--product", action="append", default=None, help="Products 的 Id，可重复")
    ap.add_argument("--products-xml", default=None, help="直接注入 <Products> 元素 XML")
    ap.add_argument("--baseline", action="store_true", help="不带任何过滤")
    ap.add_argument("--also-regular", action="store_true", help="同时执行常规同步")
    ap.add_argument("--dev-extra", default="", help="追加到 DeviceAttributes 的额外属性")
    ap.add_argument("--os-version", default="10.0.26100.1")
    ap.add_argument("--protocol-version", default="1.40")
    ap.add_argument("--raw", default=None, help="保存原始响应到此文件")
    args = ap.parse_args()

    if not (args.category or args.product or args.products_xml or args.baseline):
        args.baseline = True

    label = ("baseline" if args.baseline
             else f"cat={args.category}" if args.category
             else "products-xml" if args.products_xml
             else f"prod={args.product}")
    print(f"==> 探针: {label}  (os={args.os_version}, also_regular={args.also_regular})")

    try:
        cookie = get_cookie("en-US", args.protocol_version)
        print(f"    GetCookie 成功 (protocolVersion={args.protocol_version}), cookie 长度 {len(cookie)}")
    except Exception as e:
        print(f"    GetCookie 失败: {e}")
        return 1

    try:
        xml = sync_updates(
            cookie,
            category_ids=args.category,
            products=args.product,
            products_xml=args.products_xml,
            also_regular=args.also_regular,
            dev_extra=args.dev_extra,
            os_ver=args.os_version,
        )
    except urllib.error.HTTPError as e:
        print(f"    SyncUpdates HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:600]}")
        return 1
    except Exception as e:
        print(f"    SyncUpdates 失败: {e}")
        return 1

    summarize(xml, label)
    if args.raw:
        with open(args.raw, "w", encoding="utf-8") as f:
            f.write(xml)
        print(f"    原始响应已保存: {args.raw}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
