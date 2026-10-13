import re, os
p = r"C:\Windows\System32\AIComponentMgmt.dll"
d = open(p,"rb").read()
print(f"大小: {len(d)/1e6:.2f} MB\n")
pats = ["ProductEnumerator","UupProduct","StateRepository","PkgExtension","AIComponent",
        "Enumerate","Installed","PackageFamily","Workload","Registry","RegOpen","RegQuery",
        "Software\\\\Microsoft","PkgFamily","GetInstalled"]
print("=== 关键字符串 ===")
for k in pats:
    hits = sorted(set(m.decode("ascii","ignore") for m in
                      re.findall(rb"[\x20-\x7E]{4,}", d)
                      if k.lower().encode() in m.lower()))
    if hits:
        print(f"\n-- {k} ({len(hits)}) --")
        for h in hits[:14]: print("   " + h[:150])
