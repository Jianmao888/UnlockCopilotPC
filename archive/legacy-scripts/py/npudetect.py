import os, re, glob
cands = glob.glob(r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\**\npudetect.dll", recursive=True)
cands += glob.glob(r"C:\Windows\System32\**\npudetect.dll", recursive=True)
for p in cands[:3]:
    d = open(p,"rb").read()
    print("="*76); print(p, f"({len(d)/1e6:.2f} MB)"); print("="*76)
    # 导出名通常是 ASCII
    exps = set()
    for m in re.finditer(rb"[\x20-\x7E]{4,}", d):
        s = m.group(0).decode("ascii","ignore")
        low = s.lower()
        if (low.startswith("npudetect") or "nputype" in low or "detect" in low) and len(s) < 80:
            exps.add(s)
    print("  -- 疑似导出/函数名 --")
    for x in sorted(exps)[:30]:
        print("     " + x[:130])
    print("\n  -- 检测相关字符串（硬件/驱动/注册表）--")
    hits = set()
    for m in re.finditer(rb"[\x20-\x7E]{5,}", d):
        s = m.group(0).decode("ascii","ignore")
        low = s.lower()
        if any(k in low for k in ("pci", "ven_", "dev_", "setupapi", "pnp", "deviceid",
                                  "registry", "hklm", "software\\", "driver", "npu",
                                  "intel", "qualcomm", "amd", "mediatek", "lunarlake",
                                  "meteorlake", "arrowlake", "strix", "hawk", "ryzen")):
            hits.add(s)
    for x in sorted(hits)[:35]:
        print("     " + x[:130])
