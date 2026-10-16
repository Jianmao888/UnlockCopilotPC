import glob, json, os, re
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
files = sorted(glob.glob(os.path.join(base, "workloads*.json")))
print("找到的 workloads JSON:", len(files))
for f in files:
    print("  " + os.path.basename(f))

print()
print("=" * 78)
for f in files:
    name = os.path.basename(f)
    try:
        d = json.load(open(f, encoding="utf-8-sig"))
    except Exception as e:
        print(f"--- {name}: 解析失败 {e}"); continue
    txt = json.dumps(d, ensure_ascii=False)
    fams = sorted(set(re.findall(r'WindowsWorkload\.[A-Za-z0-9._]+', txt)))
    print(f"--- {name}  ({len(fams)} 个家族引用) ---")
    for x in fams:
        print("    " + x)
    print()
