import json, os
t = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具"
for name in ("msu-payloads.json", "oct-msu-payloads.json"):
    d = json.load(open(os.path.join(t,name), encoding="utf-8-sig"))
    msix = []
    def walk(o):
        if isinstance(o, dict):
            for k,v in o.items():
                if k in ("name","fileName","FileName","path") and isinstance(v,str) and v.lower().endswith(".msix"):
                    msix.append((v, o))
                walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
        elif isinstance(o, str):
            if o.lower().endswith(".msix"): msix.append((o, None))
    walk(d)
    seen = {}
    for n, meta in msix:
        if n not in seen: seen[n] = meta
    print("="*80)
    print(f"{name}  —— MSIX 载荷 {len(seen)} 个")
    print("="*80)
    for i,(n,m) in enumerate(sorted(seen.items()),1):
        extra = ""
        if m:
            for key in ("offset","size","sha1","part"):
                if key in m: extra += f" {key}={str(m[key])[:14]}"
        print(f"  {i:3}. {n}{extra}")
    print()
