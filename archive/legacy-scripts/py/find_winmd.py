import glob, os, re
hits=[]
for root in (r"C:\Windows\System32", r"C:\Windows\SystemApps", r"C:\Program Files\WindowsApps"):
    for f in glob.glob(os.path.join(root,"**","*.winmd"), recursive=True):
        try: d=open(f,"rb").read()
        except Exception: continue
        if b"AIComponentManager" in d or b"AIComponent" in d:
            hits.append((f, len(d)))
for f,s in hits[:20]:
    print(f"  {s:>9} {f}")
print(f"  共 {len(hits)} 个 winmd 命中")
