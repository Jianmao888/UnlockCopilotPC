import json, os
t = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具"
for name in ("msu-payloads.json","oct-msu-payloads.json"):
    p = os.path.join(t, name)
    d = json.load(open(p, encoding="utf-8-sig"))
    print("="*78); print(name, f"({os.path.getsize(p)/1024:.1f} KB)"); print("="*78)
    print("  顶层:", type(d).__name__, end="")
    if isinstance(d, dict): print(" 键:", list(d.keys())[:12])
    elif isinstance(d, list): print(f" 长度 {len(d)}")
    # 收集所有像文件名的字符串
    names = set()
    def walk(o):
        if isinstance(o, str):
            if o.lower().endswith((".msix",".cab",".esd",".msu",".appx")) or "workload" in o.lower():
                names.add(o)
        elif isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(d)
    print(f"\n  含 msix/workload 的字符串 ({len(names)}):")
    for n in sorted(names)[:60]:
        print("    " + n)
    print()
