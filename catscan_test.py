import ssl, urllib.request, urllib.error, random, re
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET
import wu_probe as wp

CTX = ssl._create_unverified_context()
WS = "https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx"

def catscan(cookie, cats):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    created, expires = wp.fmt(now), wp.fmt(now + timedelta(minutes=5))
    if cats:
        inner = "".join(
            f"<CategoryRelationship><IndexOfAndGroup>1</IndexOfAndGroup>"
            f"<CategoryId>{c}</CategoryId></CategoryRelationship>" for c in cats)
    else:
        inner = ""
    body = f"<requestedCategories>{inner}</requestedCategories>" if cats else "<requestedCategories/>"
    env = wp.envelope("StartCategoryScan", "aa11bb22-cc33-dd44-ee55-ff6677889900",
                      WS, created, expires, "Retail", body)
    req = urllib.request.Request(WS, data=env.encode("utf-8"),
        headers={"Content-Type": "application/soap+xml; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=90) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8","replace")

cookie = wp.get_cookie("en-US")
print("cookie OK\n")

for label, cats in [
    ("空请求", []),
    ("已知分类 099246c5", ["099246c5-cba0-42c5-84ad-931b1d1861af"]),
    ("已知分类 bcc64481", ["bcc64481-0fdb-4242-9ed7-48027a7cae9c"]),
    ("两个已知分类", ["099246c5-cba0-42c5-84ad-931b1d1861af","bcc64481-0fdb-4242-9ed7-48027a7cae9c"]),
]:
    st, xml = catscan(cookie, cats)
    print(f"===== {label} -> HTTP {st}, {len(xml)} chars =====")
    guids = sorted(set(re.findall(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", xml)))
    if guids:
        print(f"  返回 {len(guids)} 个 GUID:")
        for g in guids[:60]:
            print(f"    {g.lower()}")
    else:
        print("  无 GUID。响应片段:")
        print("   " + xml[:700].replace("\n"," "))
    open(f"catscan-{len(cats)}.xml","w",encoding="utf-8").write(xml)
    print()
