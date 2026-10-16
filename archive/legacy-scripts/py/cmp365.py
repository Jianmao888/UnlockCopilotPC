import json, os, re, glob
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
g = json.load(open(os.path.join(base,"workloads.json"), encoding="utf-8-sig"))
v = json.load(open(os.path.join(base,"workloads.365.json"), encoding="utf-8-sig"))

print("结构对比:")
for k in ("Packages","Workloads","ApiInfos"):
    print(f"   {k:12} generic={len(g.get(k,[])):4}   365={len(v.get(k,[])):4}")

# 我们实际有的家族（WindowsApps 目录）
have = set()
for d in glob.glob(r"C:\Program Files\WindowsApps\WindowsWorkload.*"):
    n = os.path.basename(d)
    parts = n.split("_")
    if len(parts) >= 3:
        have.add(parts[0] + "_" + parts[-1])
print(f"\n我们已安装的家族: {len(have)}")
for h in sorted(have): print("   " + h)

def fams(o):
    return set(re.findall(r'"(WindowsWorkload\.[A-Za-z0-9._]+_8wekyb3d8bbwe)"', json.dumps(o)))

fg = fams(g); fv = fams(v)
print(f"\ngeneric 引用 {len(fg)} 个家族, 我们有其中 {len(fg & have)} 个")
print(f"365     引用 {len(fv)} 个家族, 我们有其中 {len(fv & have)} 个")
print(f"\n365 需要但我们没有的 ({len(fv - have)}):")
for x in sorted(fv - have): print("   " + x)

print(f"\n365 的 Workloads: {[w.get('Id') for w in v.get('Workloads',[])]}")
print(f"\n365 ApiInfos 前 8 个 ApiClassName:")
for a in v.get("ApiInfos",[])[:8]:
    print("   " + str(a.get("ApiClassName")))
