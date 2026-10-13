import os, glob, re
# 1) productenumerator APISet 转发到哪个 DLL
cands = glob.glob(r"C:\Windows\System32\ext-ms-win-deployment-productenumerator-l1-1-*.dll")
cands += glob.glob(r"C:\Windows\System32\downlevel\ext-ms-win-deployment-productenumerator-l1-1-*.dll")
print("=== productenumerator APISet 文件 ===")
for f in cands: print(f"  {f}  ({os.path.getsize(f)} bytes)")

for f in cands:
    d = open(f,"rb").read()
    print(f"\n--- {os.path.basename(f)} 字符串 ---")
    seen=set()
    for m in re.finditer(rb"[\x20-\x7E]{6,}", d):
        s = m.group(0).decode("ascii","ignore")
        if s in seen: continue
        seen.add(s)
        if re.search(r'\.dll|Enumerate|Product|PE_', s, re.I):
            print("   " + s[:140])

# 2) AIComponentMgmt.dll 里 productenumerator 相关字符串
p = r"C:\Windows\System32\AIComponentMgmt.dll"
if os.path.exists(p):
    d = open(p,"rb").read()
    print(f"\n=== {os.path.basename(p)} ({len(d)/1e6:.3f} MB) 关键字符串 ===")
    seen=set()
    for m in re.finditer(rb"[\x20-\x7E]{5,}", d):
        s = m.group(0).decode("ascii","ignore")
        if s in seen: continue
        seen.add(s)
        if re.search(r'product|enumerat|uup|staterepo|activ|deploy|AIComponent|\.dll', s, re.I) and len(s)<130:
            print("   " + s)
