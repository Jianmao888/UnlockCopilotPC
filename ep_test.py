import sys, wu_probe as wp

ENDPOINTS = [
    ("fe2cr", "https://fe2cr.update.microsoft.com/v6/ClientWebService/client.asmx"),
    ("fe3",   "https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx"),
]
PROD = "<Products>PN=Windows.Workload.ContentExtraction.amd64&amp;V=0.0.0.0</Products>"

for name, url in ENDPOINTS:
    print(f"===== 端点 {name}: {url} =====")
    wp.CLIENT_WS = url
    try:
        cookie = wp.get_cookie("en-US")
        print(f"  GetCookie OK ({len(cookie)})")
    except Exception as e:
        print(f"  GetCookie 失败: {str(e)[:200]}")
        continue
    for label, kw in (("products", {"products_xml": PROD}), ("baseline", {})):
        try:
            xml = wp.sync_updates(cookie, **kw)
            t = xml.replace("&lt;","<").replace("&gt;",">")
            has_wl = "Workload" in t
            print(f"  [{label}] {len(xml)} 字符, UpdateIdentity={t.count('UpdateIdentity')}, Workload={has_wl}")
            if has_wl:
                import re
                print("    >>>", sorted(set(re.findall(r"[A-Za-z0-9\.]*Workload[A-Za-z0-9\.]*", t)))[:20])
                open(f"ep-{name}-{label}.xml","w",encoding="utf-8").write(xml)
        except Exception as e:
            print(f"  [{label}] 失败: {str(e)[:160]}")
    print()
