import json, os, glob
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
v = json.load(open(os.path.join(base,"workloads.365.json"), encoding="utf-8-sig"))

# 我们有的 MSIX 家族（从下载目录 + 工作区）
have = set()
for root in (r"C:\Users\jianm\Downloads\Windows-AI-包", r"C:\Users\jianm\Code\DeepseekHarness"):
    for f in glob.glob(os.path.join(root, "**", "*.msix"), recursive=True):
        n = os.path.basename(f)
        m = n.split("_")
        if len(m) >= 3:
            have.add(m[0] + "_8wekyb3d8bbwe")
print(f"手上有 MSIX 的家族: {len(have)}\n")

for w in v["Workloads"]:
    wid = w["Id"]
    pkgs = [p["FamilyName"] for p in w.get("Packages", [])]
    missing = [p for p in pkgs if p not in have]
    status = "OK" if not missing else f"缺 {len(missing)}"
    print(f"=== {wid}  ({len(pkgs)} 包)  {status} ===")
    for p in pkgs:
        mark = "  ok " if p in have else "  MISS"
        print(f"   {mark} {p}")
    if missing:
        print(f"   缺: {missing}")
    print()
