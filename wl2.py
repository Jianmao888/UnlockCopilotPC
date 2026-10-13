import json, os
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
def load(n):
    return json.load(open(os.path.join(base, n), encoding="utf-8-sig"))

for name in ("workloads.lnl.json",):
    d = load(name)
    print("="*78); print(name); print("="*78)
    pk = d.get("Packages", [])
    print(f"  Packages ({len(pk)}):")
    for p in pk:
        fn = p.get("FamilyName","")
        if any(k in fn for k in ("TextRecognition","ScrRegDetection","SemanticText","WinML","Onnx","PSOnnx","SessionManager","Manager")):
            print(f"    * {fn}   v{p.get('Version')}")
    print(f"\n  Workloads ({len(d.get('Workloads',[]))}):")
    for w in d.get("Workloads", [])[:12]:
        if isinstance(w, dict):
            print("    " + json.dumps(w, ensure_ascii=False)[:220])
    print(f"\n  ApiInfos ({len(d.get('ApiInfos',[]))}):")
    for a in d.get("ApiInfos", [])[:8]:
        print("    " + json.dumps(a, ensure_ascii=False)[:260])

print()
print("=== 各平台 JSON 的 Packages 数量 与 是否含 Lnl/Stx/Ptl/Qnn ===")
for f in sorted(os.listdir(base)):
    if not f.startswith("workloads") or not f.endswith(".json"): continue
    try:
        d = load(f)
    except Exception as e:
        print(f"  {f}: 解析失败"); continue
    pk = d.get("Packages", [])
    fams = [p.get("FamilyName","") for p in pk]
    marks = []
    for tag in ("Lnl","Stx","Ptl","Qnn","365","J32"):
        if any(tag in x for x in fams): marks.append(tag)
    print(f"  {f:22} Packages={len(pk):3}  Workloads={len(d.get('Workloads',[])):2}  ApiInfos={len(d.get('ApiInfos',[])):2}  平台标记={marks}")
