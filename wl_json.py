import json, os
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
for name in ("workloads.json", "workloads.lnl.json"):
    p = os.path.join(base, name)
    print("="*78); print(name, f"({os.path.getsize(p)} bytes)"); print("="*78)
    try:
        d = json.load(open(p, encoding="utf-8-sig"))
    except Exception as e:
        print("  解析失败:", e); continue
    print(f"  顶层类型: {type(d).__name__}")
    if isinstance(d, dict):
        ks = list(d.keys())
        print(f"  顶层键 ({len(ks)}): {ks[:20]}")
        # 打印第一个键的完整结构
        if ks:
            k0 = ks[0]
            print(f"\n  --- d['{k0}'] 样例 ---")
            print("  " + json.dumps(d[k0], ensure_ascii=False, indent=2)[:2200])
    print()
