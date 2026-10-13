import ssl, urllib.request, urllib.error, random, re
from datetime import datetime, timedelta, timezone
import wu_probe as wp

CTX = ssl._create_unverified_context()
WS = "https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx"

def call(action, body, ticket="Retail", proto=None, minutes=5):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    created, expires = wp.fmt(now), wp.fmt(now + timedelta(minutes=minutes))
    env = wp.envelope(action, "aa11bb22-cc33-dd44-ee55-ff6677889900",
                      WS, created, expires, ticket, body)
    req = urllib.request.Request(WS, data=env.encode("utf-8"),
        headers={"Content-Type": "application/soap+xml; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=90) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8","replace")

# 1) GetCookie with protocolVersion 1.81
now = datetime.now(timezone.utc).replace(tzinfo=None)
st, xml = call("GetCookie",
    f"<oldCookie></oldCookie><lastChange>{wp.fmt7(now - timedelta(days=730))}</lastChange>"
    f"<currentTime>{wp.fmt(now)}</currentTime><protocolVersion>1.81</protocolVersion>",
    ticket="<User />", minutes=27*60*24)
print(f"[GetCookie 1.81] HTTP {st}, {len(xml)} chars")
m = re.search(r"<EncryptedData[^>]*>(.*?)</EncryptedData>", xml, re.S)
cookie = m.group(1) if m else None
print("  cookie:", "OK" if cookie else "失败")
open("gc181.xml","w",encoding="utf-8").write(xml)

# 2) GetConfig
st, cfg = call("GetConfig", "<protocolVersion>1.81</protocolVersion>")
print(f"\n[GetConfig] HTTP {st}, {len(cfg)} chars")
pv = re.search(r"ProtocolVersion[^>]*>([^<]+)<", cfg)
print("  服务端 ProtocolVersion =", pv.group(1) if pv else "(未找到)")
open("getconfig.xml","w",encoding="utf-8").write(cfg)
print("  响应键:", ", ".join(sorted(set(re.findall(r"<(?:[a-z0-9]+:)?([A-Za-z][A-Za-z0-9]*)[ >/]", cfg)))[:30]))

# 3) StartCategoryScan
if cookie:
    st, sc = call("StartCategoryScan", "<requestedCategories/>", ticket="Retail")
    print(f"\n[StartCategoryScan 空] HTTP {st}, {len(sc)} chars")
    guids = sorted(set(re.findall(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", sc)))
    guids = [g for g in guids if g.lower() != "aa11bb22-cc33-dd44-ee55-ff6677889900"]
    print(f"  分类 GUID: {len(guids)}")
    for g in guids[:60]: print("   ", g.lower())
    open("catscan-empty.xml","w",encoding="utf-8").write(sc)
    if not guids:
        print("  原始:", sc[:900])
