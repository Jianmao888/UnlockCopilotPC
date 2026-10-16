import json, os, re
t = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具"
d = json.load(open(os.path.join(t,"msu-payloads.json"), encoding="utf-8"))
print(f"MSU 载荷总数: {len(d)}\n")
print("=== 非 WindowsWorkload.* 的载荷（找 AIFabric / AI 相关）===")
for e in d:
    n = e.get("name","")
    if not n.startswith("WindowsWorkload."):
        print(f"  {e['size']/1e6:9.2f} MB  {n}")
print()
print("=== 名字里含 AI / Fabric / CoreAI / Workload 的所有载荷 ===")
for e in d:
    n = e.get("name","")
    if re.search(r"AI|Fabric|CoreAI|Workload", n, re.I) and not n.startswith("WindowsWorkload."):
        print(f"  {e['size']/1e6:9.2f} MB  {n}")
