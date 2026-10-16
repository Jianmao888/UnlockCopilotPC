import ssl, urllib.request, urllib.error, random, re
from datetime import datetime, timedelta, timezone
import wu_probe as wp

CTX = ssl._create_unverified_context()
ENDPOINTS = [
    ("fe3cr.delivery (8B24B027 workload service)", "https://fe3cr.delivery.mp.microsoft.com/ClientWebService/client.asmx"),
    ("fe3.delivery  (我一直在测的)",               "https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx"),
    ("fe2cr.update  (9482F4B4 MU)",                "https://fe2cr.update.microsoft.com/v6/ClientWebService/client.asmx"),
]
KEYS = ["SyncUpdatesSupportsProductsSync", "SyncUpdatesSupportsTreatAppCategoryIdsAsInstalled",
        "ProtocolVersion", "SyncUpdatesSupportsCatalogSync", "SyncUpdatesSupportsAdditionalFragments"]

for name, url in ENDPOINTS:
    print("="*74); print(name); print("  " + url); print("="*74)
    wp.CLIENT_WS = url
    try:
        cookie = wp.get_cookie("en-US", "1.81")
    except Exception as e:
        print("  GetCookie 失败:", str(e)[:160]); print(); continue
    print(f"  GetCookie OK ({len(cookie)})")
    try:
        cfg = wp.soap_post(url, "GetConfig", "aa11bb22-cc33-dd44-ee55-ff6677889900",
                           url, wp.fmt(datetime.now(timezone.utc).replace(tzinfo=None)),
                           wp.fmt(datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)),
                           "Retail", "<protocolVersion>1.81</protocolVersion>")
    except Exception as e:
        print("  GetConfig 失败:", str(e)[:200]); print(); continue
    print(f"  GetConfig {len(cfg)} 字符")
    for k in KEYS:
        m = re.search(r"<Name>" + re.escape(k) + r"</Name>\s*<Value[^>]*>([^<]*)</Value>", cfg)
        if m:
            print(f"    {k:52} = {m.group(1)}")
    if "SyncUpdatesSupportsProductsSync" not in cfg:
        vals = re.findall(r"<Name>([^<]+)</Name>\s*<Value[^>]*>([^<]*)</Value>", cfg)
        print(f"    （该服务未返回 ProductsSync 配置，共 {len(vals)} 项属性）")
        for a,b in vals[:12]: print(f"      {a} = {b}")
    print()
