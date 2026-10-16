import zipfile, glob, os
root = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验"
for pat in ("*TextRecognition.Lnl.1_1.2608*.msix",
            "*ScrRegDetection.Lnl.1_1.2608*.msix",
            "*WinMLShared.5.2*.msix"):
    fs = glob.glob(os.path.join(root, "**", pat), recursive=True)
    if not fs: continue
    f = fs[0]
    print("="*76)
    print(os.path.basename(f))
    print("="*76)
    with zipfile.ZipFile(f) as z:
        items = [(i.filename, i.file_size) for i in z.infolist() if not i.is_dir()]
        items.sort(key=lambda x: -x[1])
        print(f"  条目数: {len(items)}   解压总大小: {sum(s for _,s in items)/1e6:.1f} MB")
        print("  最大的 22 个:")
        for n, s in items[:22]:
            print(f"    {s/1e6:9.3f} MB  {n}")
        # 模型类文件
        models = [n for n,_ in items if n.lower().endswith(
            ('.onnx','.onnxe','.ort','.bin','.model','.tflite','.dlc','.xml','.json'))]
        print(f"  模型/描述类文件 ({len(models)}):")
        for n in models[:15]: print("      " + n)
