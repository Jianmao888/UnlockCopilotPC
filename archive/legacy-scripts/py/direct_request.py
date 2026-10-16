#!/usr/bin/env python3
"""
direct_request.py — 直接向 workload 服务(fe3cr)请求 Windows.Workload.* 产品

背景：
  ETL 里客户端发出的形态是
    ProductAttributes(Caller): PN=Windows.Workload.ContentExtraction.amd64&V=0.0.0.0
    ProductAttributes(CTAC):   PN=A&V=..;PN=B&V=..
  说明产品属性以 "PN=<name>&V=<version>" 的分号串形式传递。

本脚本针对 fe3cr.delivery.mp.microsoft.com（8B24B027 服务）试多种承载位置与格式，
对比哪个能让服务端返回更新。

用法: python direct_request.py [variant]
  不带参数 = 跑全部变体
"""
import ssl
import sys
import urllib.error
from datetime import datetime, timedelta, timezone

import wu_probe as wp

ENDPOINT = "https://fe3cr.delivery.mp.microsoft.com/ClientWebService/client.asmx"

PRODUCT = "Windows.Workload.ContentExtraction.amd64"
PRODUCT2 = "Windows.Workload.Analysis.amd64"

# 我们的 SOAP 封装要求 wsse:Security/Timestamp 元素名带命名空间前缀，
# 这里的变体都注入到 <ProductsParameters> 内。
VARIANTS = {
    # 1. Products 元素里放 PN=..&V=.. 文本
    "A-products-text": f"<Products>PN={PRODUCT}&amp;V=0.0.0.0</Products>",
    # 2. Products/Product Id 形式
    "B-products-id": f'<Products><Product Id="{PRODUCT}" Version="0.0.0.0" /></Products>',
    # 3. ProductAttributes 元素（分号串）
    "C-productattrs": f"<ProductAttributes>PN={PRODUCT}&amp;V=0.0.0.0</ProductAttributes>",
    # 4. CallerAttributes 里追加 PN
    "D-caller-pn": None,   # 需要改 CallerAttributes，单独处理
    # 5. Products 里放 PackageFamilyName 形式
    "E-products-pfn": f"<Products><Product Id=\"{PRODUCT}\" Version=\"0.0.0.0\" /><Product Id=\"{PRODUCT2}\" Version=\"0.0.0.0\" /></Products>",
    # 6. 空 Products + FilterAppCategoryIds 用真实 GUID
    "F-products-empty": "<Products/>",
    # 7. Products 里用 ms-uup 形式
    "G-products-uup": f"<Products>PN={PRODUCT}&amp;V=0.0.0.0&amp;IsEmergencyProduct=0</Products>",
}


def run_variant(name, products_xml, caller_attrs=None):
    print("=" * 76)
    print(f"变体 {name}")
    print("  注入 XML: " + (products_xml or "(改 CallerAttributes)"))
    print("=" * 76)
    wp.CLIENT_WS = ENDPOINT
    try:
        cookie = wp.get_cookie("en-US", "1.81")
    except Exception as e:
        print(f"  GetCookie 失败: {str(e)[:200]}")
        return None

    # 对 D 变体走特殊路径
    if caller_attrs is not None:
        xml = sync_with_caller(cookie, caller_attrs)
    else:
        try:
            xml = wp.sync_updates(cookie, products_xml=products_xml)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.read().decode('utf-8','replace')[:400]}")
            return None
        except Exception as e:
            print(f"  失败: {str(e)[:300]}")
            return None

    wp.summarize(xml, name)
    return xml


def sync_with_caller(cookie, caller_attrs):
    """自定义 CallerAttributes 的 SyncUpdates。"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    created = wp.fmt(now)
    expires = wp.fmt(now + timedelta(minutes=5))
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
                    <CallerAttributes>{caller_attrs}</CallerAttributes>
                    <Products/>
                </ProductsParameters>
            </parameters>
    """
    return wp.soap_post(ENDPOINT, "SyncUpdates", "175df68c-4b91-41ee-b70b-f2208c65438e",
                        ENDPOINT, created, expires, "Retail", body)


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"目标端点: {ENDPOINT}\n")

    results = {}
    for name, pxml in VARIANTS.items():
        if want and want != name:
            continue
        if name == "D-caller-pn":
            xml = run_variant(name, None,
                              caller_attrs=f"Interactive=1;IsSeeker=0;PN={PRODUCT}&V=0.0.0.0;")
        else:
            xml = run_variant(name, pxml)
        results[name] = xml
        print()

    print("#" * 76)
    print("# 汇总")
    print("#" * 76)
    for name, xml in results.items():
        if xml is None:
            print(f"  {name:20} -> 失败")
            continue
        n_ids = xml.count("<UpdateIdentity")
        n_files = xml.count("<File ")
        hit = "Workload" in xml
        print(f"  {name:20} -> {len(xml):7} 字符  UpdateIdentity={n_ids:3}  File={n_files:3}  含Workload={hit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
