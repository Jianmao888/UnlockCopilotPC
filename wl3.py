import json, os
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
def load(n): return json.load(open(os.path.join(base,n), encoding="utf-8-sig"))

we_have = {
 "WindowsWorkload.Data.ContentExtraction.Lnl.1",
 "WindowsWorkload.ScrRegDetection.Data.1","WindowsWorkload.ScrRegDetection.Lnl.1",
 "WindowsWorkload.SemanticText.Data.1","WindowsWorkload.SemanticText.Lnl.1",
 "WindowsWorkload.TextRecognition.Lnl.1","WindowsWorkload.TextRecognition.365.1",
 "WindowsWorkload.TextRecognition.Data.OPT.1","WindowsWorkload.WinMLShared.5.2",
}
print("=== 各平台 JSON 里，TextRecognizer / ScrRegDetection / SemanticText 指向哪个包 ===")
for f in ("workloads.json","workloads.lnl.json","workloads.365.json","workloads.stx.json","workloads.qnn.json"):
    d = load(f)
    print(f"\n--- {f} ---")
    for a in d.get("ApiInfos", []):
        cn = a.get("ApiClassName","")
        if cn.endswith(("TextRecognizer","ScreenRegionDetector","SemanticTextEmbeddingsCreator")):
            fam = a.get("SessionPackage","")
            mark = "  ✅我们已有" if fam.replace("_8wekyb3d8bbwe","") in we_have else ""
            print(f"   {cn.split('.')[-1]:32} -> {fam}{mark}")
    # 该 JSON 的 Workloads 列表
    print(f"   Workloads: {[w.get('Id') for w in d.get('Workloads',[])][:10]}")
