import json, os, re
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
f = os.path.join(base, "workloads.json")
d = json.load(open(f, encoding="utf-8-sig"))
print(f"=== workloads.json (generic) 顶层键 ===")
if isinstance(d, dict):
    for k in d: print("   " + k)
    txt = json.dumps(d, ensure_ascii=False, indent=2)
else:
    txt = json.dumps(d, ensure_ascii=False, indent=2)
print()
print(f"总长 {len(txt)} 字符")
fams = sorted(set(re.findall(r'WindowsWorkload\.[A-Za-z0-9._]+', txt)))
print(f"\n=== 引用的家族 ({len(fams)}) ===")
for x in fams: print("   " + x)
print()
print("=== 前 3000 字符原文 ===")
print(txt[:3000])
