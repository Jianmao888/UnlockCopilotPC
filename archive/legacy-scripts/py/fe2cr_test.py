import ssl, urllib.request, urllib.error, random, re
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

CTX = ssl._create_unverified_context()
URL = "https://fe2cr.update.microsoft.com/v6/ClientWebService/client.asmx"
ACT = "http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService/"

def fmt(dt):  return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond//1000:03d}Z"
def fmt7(dt): return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond:07d}Z"

def env11(action, body, ticket="<User />", mid="b9b43757-2247-4d7b-ae8f-a71ba8a22386", exp_min=27):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    created, expires = fmt(now), fmt(now + timedelta(days=exp_min))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:x="http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService"
  xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
  xmlns:wuws="http://schemas.microsoft.com/msus/2014/10/WindowsUpdateAuthorization">
  <soap:Header>
    <wuws:WindowsUpdateTicketsToken wsu:id="ClientMSA">
      <TicketType Name="MSA" Version="1.0" Policy="MBI_SSL">{ticket}</TicketType>
    </wuws:WindowsUpdateTicketsToken>
  </soap:Header>
  <soap:Body><x:{action}>{body}</x:{action}></soap:Body>
</soap:Envelope>"""

def post(action, body, ticket="<User />", exp_min=27):
    data = env11(action, body, ticket, exp_min=exp_min).encode("utf-8")
    req = urllib.request.Request(URL, data=data, method="POST", headers={
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{ACT}{action}"',
    })
    with urllib.request.urlopen(req, context=CTX, timeout=90) as r:
        return r.read().decode("utf-8", "replace")

now = datetime.now(timezone.utc).replace(tzinfo=None)
try:
    xml = post("GetCookie", f"<x:oldCookie/><x:lastChange>{fmt7(now - timedelta(days=730))}</x:lastChange>"
                           f"<x:currentTime>{fmt(now)}</x:currentTime><x:protocolVersion>1.40</x:protocolVersion>")
    print("GetCookie OK, len =", len(xml))
    root = ET.fromstring(xml)
    cookie = None
    for el in root.iter():
        if el.tag.endswith("EncryptedData") and el.text:
            cookie = el.text; break
    print("cookie 提取:", "成功" if cookie else "失败")
    open("fe2cr-getcookie.xml","w",encoding="utf-8").write(xml)
except urllib.error.HTTPError as e:
    print("GetCookie HTTP", e.code, e.read().decode("utf-8","replace")[:1200])
except Exception as e:
    print("GetCookie 失败:", str(e)[:300])
