import json, os, re
t = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具"
d = json.load(open(os.path.join(t,"msu-payloads.json"), encoding="utf-8"))
print(f"MSU 载荷总数: {len(d)}\n")
print("=== 非 WindowsWorkload.* 的载荷 ===")
for e in d:
    n = e.get("name","")
    if not n.startswith("WindowsWorkload."):
        print(f"  {e.get('size',0)/1e6:9.2f} MB  {n}")
print()
print("=== 含 AI/Fabric/CoreAI 的载荷 ===")
for e in d:
    n = e.get("name","")
    if re.search(r"AI|Fabric|CoreAI", n, re.I):
        print(f"  {e.get('size',0)/1e6:9.2f} MB  {n}")
print()
# 打印一个完整条目看字段
print("=== 一个条目的字段 ===")
nn = [e for e in d if e.get("name","").startswith("WindowsWorkload.Manager")][:1]
print(json.dumps(nn[0] if nn else d[0], ensure_ascii=False, indent=2)[:600])
