import glob, os, re
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
for d in glob.glob(os.path.join(base,"**","*.dll"), recursive=True):
    sz = os.path.getsize(d)
    if sz < 30000: continue
    data = open(d,"rb").read()
    hits=set()
    for m in re.finditer(rb"[\x20-\x7E]{4,}", data):
        s = m.group(0).decode("ascii","ignore")
        low = s.lower()
        if any(k in low for k in ("365","cloudpc","cloud pc","cloudhost","clouddesktop",
                                  "w365","deploymenttype","iscloud","sessionhost")):
            hits.add(s)
    if hits:
        print(f"--- {os.path.basename(d)} ---")
        for x in sorted(hits)[:18]: print("    " + x[:140])
