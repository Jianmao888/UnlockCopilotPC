import json, os, re
t = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具"
p = os.path.join(t, "msu-wim-resources.json")
d = json.load(open(p, encoding="utf-8-sig"))
print("顶层类型:", type(d).__name__)
if isinstance(d, dict):
    print("顶层键:", list(d.keys())[:10])
    for k in list(d.keys())[:3]:
        v = d[k]
        print(f"\n  '{k}' 类型={type(v).__name__}", end="")
        if isinstance(v, list): print(f" 长度={len(v)}")
        elif isinstance(v, dict): print(f" 键={list(v.keys())[:10]}")
        else: print(f" 值={str(v)[:200]}")
elif isinstance(d, list):
    print("长度:", len(d))
    print("\n前 3 项:")
    for x in d[:3]:
        print("  " + json.dumps(x, ensure_ascii=False)[:400])
