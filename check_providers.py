import zipfile, glob, os
root = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验"
for pat in ("5a4c95f6*", "*365.1*"):
    for f in glob.glob(os.path.join(root, "**", pat + ".msix"), recursive=True):
        print("="*76); print(os.path.basename(f)); print("="*76)
        with zipfile.ZipFile(f) as z:
            items = sorted(((i.filename, i.file_size) for i in z.infolist() if not i.is_dir()), key=lambda x:-x[1])
            for n,s in items[:20]:
                print(f"   {s/1e6:9.3f} MB  {n}")
            # 找 provider 插件
            prov = [n for n,_ in items if any(k in n.lower() for k in ("plugin","provider","npu","openvino","qnn","vitis","directml","onnxruntime"))]
            if prov:
                print("   -- 执行提供程序/插件 --")
                for n in prov: print("      " + n)
        print()

# 检查 Lnl runtime dll 里的 provider 字符串
print("="*76)
print("PSOnnxRuntime (5a4c95f6...) 内的 provider 字符串")
print("="*76)
fs = glob.glob(os.path.join(root, "**", "5a4c95f6*.msix"), recursive=True)
if fs:
    import re
    with zipfile.ZipFile(fs[0]) as z:
        for i in z.infolist():
            if i.filename.lower().endswith(".dll") and i.file_size > 1_000_000:
                data = z.read(i.filename)
                hits = set()
                for m in re.finditer(rb"[\x20-\x7E]{5,}", data):
                    s = m.group(0).decode("ascii","ignore")
                    if any(k in s for k in ("ExecutionProvider","NPU","OpenVINO","QNN","Vitis","DML","DirectML","CPU")):
                        hits.add(s)
                print(f"\n  --- {i.filename} ({i.file_size/1e6:.2f} MB) ---")
                for x in sorted(hits)[:25]:
                    print("      " + x[:130])
