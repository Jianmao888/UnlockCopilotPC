import ssl, urllib.request, urllib.error, random
from datetime import datetime, timedelta, timezone
import wu_probe as wp

CTX = ssl._create_unverified_context()

def raw_post(url, body):
    req = urllib.request.Request(url, data=body.encode("utf-8"),
        headers={"Content-Type": "application/soap+xml; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=90) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8","replace")

cookie = wp.get_cookie("en-US")
print("cookie OK\n")

# 构造一个带 <Products><Product Id=.../></Products> 的请求，抓完整 fault
prod_xml = '<Products><Product Id="Windows.Workload.ContentExtraction.amd64" /></Products>'
try:
    wp.sync_updates(cookie, products_xml=prod_xml)
    print("意外成功")
except urllib.error.HTTPError as e:
    full = e.read().decode("utf-8","replace")
    print("=== 完整 SOAP Fault (HTTP %d) ===" % e.code)
    print(full)
