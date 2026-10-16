import json, os, urllib.request, ssl
t = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具"
ctx = ssl._create_default_https_context()
for name in ("uup-msu-files.json","uup-oct-msu-files.json"):
    p = os.path.join(t,name)
    d = json.load(open(p, encoding="utf-8-sig"))
    big = max(d, key=lambda x: int(x["Size"]))
    print("="*76)
    print(f"{name}: {len(d)} 个 MSU, 取最大 = {big['Name']} ({int(big['Size'])/1e9:.2f} GB)")
    print(f"  URL: {big['Url'][:130]}")
    try:
        req = urllib.request.Request(big["Url"], headers={"Range":"bytes=0-2047"})
        with urllib.request.urlopen(req, timeout=45) as r:
            data = r.read()
            print(f"  ✅ 有效  HTTP {r.status}  收到 {len(data)} 字节")
            print(f"     Content-Range: {r.headers.get('Content-Range')}")
            # 检查是不是 CAB/MSU 魔数
            print(f"     前 8 字节: {data[:8].hex()}  ({data[:4]!r})")
    except Exception as e:
        print(f"  ❌ 失效: {str(e)[:220]}")
