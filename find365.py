import os, re, glob
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
targets = []
for d in glob.glob(os.path.join(base,"**","*.dll"), recursive=True):
    sz = os.path.getsize(d)
    if sz < 20000: continue
    data = open(d,"rb").read()
    hits = set()
    for m in re.finditer(rb"[\x20-\x7E]{4,}", data):
        s = m.group(0).decode("ascii","ignore")
        low = s.lower()
        if any(k in low for k in ("workloads.", "w365", "cloudpc", "cloud pc", "windows365",
                                  "windows 365", "cloudhost", "cloudhp", "iscloud",
                                  "loadworkloads", "workloadjson", "workloadfile")):
            hits.add(s)
    if hits:
        print(f"--- {os.path.basename(d)} ({sz/1e6:.2f} MB) ---")
        for x in sorted(hits)[:25]:
            print("    " + x[:150])
        print()
