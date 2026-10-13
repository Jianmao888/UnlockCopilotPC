import glob, os, re
targets = []
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
for pat in ("*.dll","*.exe","*.json","*.winmd"):
    targets += glob.glob(os.path.join(base, pat))
    targets += glob.glob(os.path.join(base, "**", pat), recursive=True)

seen = set()
for f in sorted(set(targets)):
    if os.path.isdir(f): continue
    sz = os.path.getsize(f)
    if sz < 8000: continue
    try: d = open(f,"rb").read()
    except Exception: continue
    hits = set()
    for m in re.finditer(rb"[\x20-\x7E]{5,}", d):
        s = m.group(0).decode("ascii","ignore")
        low = s.lower()
        if any(k in low for k in ("win365","cloudpc","cloud pc","cloudpcmetadata",
                                  "deploymenttype","iscloudpc","cloudpcconfig",
                                  "npugeneration","nputype","brokernputype",
                                  "w365","cloudhost","sessionhost")):
            hits.add(s)
    if hits:
        print(f"--- {os.path.relpath(f, base)}  ({sz/1e6:.2f} MB) ---")
        for x in sorted(hits)[:22]:
            print("    " + x[:150])
        print()
