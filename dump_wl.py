import re, os
p = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\Microsoft.Windows.Workloads.dll"
d = open(p,"rb").read()
print(f"大小: {len(d)/1e6:.3f} MB\n")

# 导入的 DLL
print("=== 导入的 DLL ===")
for m in re.finditer(rb"[A-Za-z0-9_\-\.]+\.dll", d):
    pass
from collections import Counter
c = Counter(re.findall(rb"[A-Za-z0-9_\-\.]{4,40}\.dll", d))
for k,v in c.most_common(30):
    print(f"   {v:3}x  {k.decode('ascii','ignore')}")

print()
print("=== 全部可读字符串（去重，长度>=6）===")
seen = set()
out = []
for m in re.finditer(rb"[\x20-\x7E]{6,}", d):
    s = m.group(0).decode("ascii","ignore")
    if s not in seen:
        seen.add(s); out.append(s)
print(f"共 {len(out)} 条")
for s in out:
    print("   " + s[:190])
