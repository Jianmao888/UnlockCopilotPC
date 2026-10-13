import json, os
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
KEYS = ["WinMLShared","EP.Intel.OpenVINO","EP.AMD.VitisAI","PSTokenizerShared.5.2",
        "SettingsModel","ImageSearch","ImageTextSearch","Manager.1","SessionManager.1",
        "PSOnnxRuntime.3.7","PSTokenizerShared.3.7","QueryBlockList"]
for f in sorted(os.listdir(base)):
    if not (f.startswith("workloads") and f.endswith(".json")): continue
    d = json.load(open(os.path.join(base,f), encoding="utf-8-sig"))
    fams = [p.get("FamilyName","") for p in d.get("Packages",[])]
    print(f"--- {f} ({len(fams)} 包) ---")
    for k in KEYS:
        hits = sorted(set(x for x in fams if k in x))
        if hits:
            print(f"    {k:26} -> {hits[0]}")
    print()
