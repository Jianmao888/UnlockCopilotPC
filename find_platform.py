import os, re, glob
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
dlls = glob.glob(os.path.join(base, "**", "*.dll"), recursive=True)
print(f"AIFabric 包内 DLL: {len(dlls)} 个\n")
for d in dlls:
    sz = os.path.getsize(d)
    data = open(d,"rb").read()
    hits = set()
    for m in re.finditer(rb"[\x20-\x7E]{5,}", data):
        s = m.group(0).decode("ascii","ignore")
        low = s.lower()
        if "workloads" in low and ".json" in low:
            hits.add(s)
        elif low in ("lnl","ptl","stx","qnn","j32","365"):
            hits.add("PLATFORM_TAG:"+s)
    if hits:
        print(f"--- {os.path.basename(d)} ({sz/1e6:.2f} MB) ---")
        for x in sorted(hits)[:20]:
            print("    " + x[:140])

print("\n=== 找平台检测相关字符串 ===")
for d in dlls:
    data = open(d,"rb").read()
    hits = set()
    for m in re.finditer(rb"[\x20-\x7E]{5,}", data):
        s = m.group(0).decode("ascii","ignore")
        low = s.lower()
        if any(k in low for k in ("npu", "platform", "silicon", "cpuvendor", "processor",
                                  "lunarlake", "arrowlake", "meteorlake", "panther", "strix",
                                  "snapdragon", "islnl", "getplatform")):
            hits.add(s)
    if hits:
        print(f"\n--- {os.path.basename(d)} ---")
        for x in sorted(hits)[:22]:
            print("    " + x[:140])
