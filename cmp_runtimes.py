import zipfile, glob, os, re
BASE = r"C:\Users\jianm\Downloads\Windows-AI-包"
def find(pat):
    r = glob.glob(os.path.join(BASE, "**", pat), recursive=True)
    return r[0] if r else None

print("=== 对比 Lnl vs 365 的运行时包内容 ===")
for pat, label in (("*PSOnnxRuntime.Lnl.3.7*.msix","Lnl 运行时"),
                   ("*PSOnnxRuntime.365.3.7*.msix","365 运行时"),
                   ("*WinMLShared.5.2*.msix","新代 WinML 运行时")):
    f = find(pat)
    if not f:
        print(f"  {label}: 未找到"); continue
    print(f"\n--- {label} ({os.path.basename(f)}) ---")
    with zipfile.ZipFile(f) as z:
        items = sorted(((i.filename, i.file_size) for i in z.infolist() if not i.is_dir()),
                       key=lambda x:-x[1])
        for n,s in items[:14]:
            print(f"    {s/1e6:9.3f} MB  {n}")
        # 找 EP 相关
        ep = [n for n,_ in items if re.search(r"openvino|qnn|vitis|npu|directml|provider", n, re.I)]
        print(f"    EP/NPU 相关: {ep}")

print("\n=== 对比 TextRecognition 会话包（Lnl vs 365）===")
for pat in ("*TextRecognition.Lnl.1_1.2608*.msix","*TextRecognition.365.1_1.2608*.msix",
            "*TextRecognition.365.1_1.2508*.msix"):
    f = find(pat)
    if not f: continue
    print(f"\n--- {os.path.basename(f)} ({os.path.getsize(f)/1e6:.2f} MB) ---")
    with zipfile.ZipFile(f) as z:
        items = sorted(((i.filename, i.file_size) for i in z.infolist() if not i.is_dir()),
                       key=lambda x:-x[1])
        for n,s in items[:10]:
            print(f"    {s/1e6:9.3f} MB  {n}")
