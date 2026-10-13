import json, os, glob
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
root = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验"
def load(n): return json.load(open(os.path.join(base,n), encoding="utf-8-sig"))

have = set()
for f in glob.glob(os.path.join(root,"**","*.msix"), recursive=True):
    n = os.path.basename(f)
    # 从包名推 FamilyName：<Name>_<Version>_<arch>.msix
    parts = n[:-5].rsplit("_", 2)
    if len(parts) == 3:
        have.add(parts[0] + "_8wekyb3d8bbwe")
print(f"我们已有的包 ({len(have)}):")
for h in sorted(have): print("   " + h)

for jf in ("workloads.lnl.json","workloads.365.json","workloads.json"):
    d = load(jf)
    need = set(p.get("FamilyName","") for p in d.get("Packages",[]))
    # 只看与我们要研究的功能相关的 workload
    focus = {"Windows.Workload.ContentExtraction.Lnl","Windows.Workload.ContentExtraction.365",
             "Windows.Workload.ContentExtraction","Windows.Workload.Analysis.Lnl","Windows.Workload.Analysis.365"}
    rel = set()
    for w in d.get("Workloads", []):
        if w.get("Id") in focus:
            for p in w.get("Packages", []):
                fn = p.get("FamilyName","")
                if fn: rel.add(fn)
    missing = sorted(x for x in rel if x not in have)
    print(f"\n=== {jf} ===")
    print(f"  该平台全部 Packages: {len(need)}")
    print(f"  ContentExtraction/Analysis 相关必需包: {len(rel)}")
    print(f"  其中我们已有: {len(rel) - len(missing)}")
    print(f"  ❌ 缺失: {len(missing)}")
    for m in missing[:25]:
        print(f"       {m}")
