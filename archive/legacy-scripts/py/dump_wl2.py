import re, os
p = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\Microsoft.Windows.Workloads.dll"
d = open(p,"rb").read()
seen=set(); out=[]
for m in re.finditer(rb"[\x20-\x7E]{6,}", d):
    s = m.group(0).decode("ascii","ignore")
    # 只要像"词"的：有元音、字母占比高
    if not re.match(r'^[A-Za-z][A-Za-z0-9_\-\.\\/ :\*\?]{5,}$', s): continue
    letters = sum(c.isalpha() for c in s)
    if letters < len(s)*0.6: continue
    if len(re.findall(r'[aeiouAEIOU]', s)) < 2: continue
    if s in seen: continue
    seen.add(s); out.append(s)
print(f"有意义字符串 {len(out)} 条:\n")
for s in out:
    print("   " + s[:190])
