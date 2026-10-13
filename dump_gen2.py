import json, os
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
d = json.load(open(os.path.join(base,"workloads.json"), encoding="utf-8-sig"))
print("Packages:", len(d["Packages"]))
print("Workloads:", len(d["Workloads"]))
print("ApiInfos:", len(d["ApiInfos"]))

print("\n=== Workloads 结构（第 1 项） ===")
print(json.dumps(d["Workloads"][0], ensure_ascii=False, indent=2)[:1800])

print("\n=== Workloads 全部名称 ===")
for w in d["Workloads"]:
    keys = list(w.keys())
    nm = w.get("Name") or w.get("Id") or w.get("Workload") or keys
    print(f"   {nm}   keys={keys}")

print("\n=== ApiInfos 结构（第 1 项） ===")
print(json.dumps(d["ApiInfos"][0], ensure_ascii=False, indent=2)[:1500])

print("\n=== ApiInfos 全部 ===")
for a in d["ApiInfos"]:
    print("   " + str(a.get("ApiClassName") or a.get("Name") or list(a.keys())))
