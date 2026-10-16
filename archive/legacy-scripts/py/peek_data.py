import zipfile, glob, os
root = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验"
pats = ["*ScrRegDetection.Data.1_1.2608*.msix",
        "*SemanticText.Data.1_1.2511*.msix",
        "*TextRecognition.Data.OPT.1*.msix",
        "*Data.ContentExtraction.Lnl.1_1.2608*.msix"]
for pat in pats:
    fs = glob.glob(os.path.join(root, "**", pat), recursive=True)
    if not fs: continue
    f = fs[0]
    print("="*76)
    print(os.path.basename(f))
    print("="*76)
    with zipfile.ZipFile(f) as z:
        items = [(i.filename, i.file_size) for i in z.infolist() if not i.is_dir()]
        items.sort(key=lambda x: -x[1])
        print(f"  条目 {len(items)}   解压总计 {sum(s for _,s in items)/1e6:.1f} MB")
        for n, s in items[:18]:
            print(f"    {s/1e6:10.3f} MB  {n}")
        # 后缀统计
        from collections import Counter
        ext = Counter(os.path.splitext(n)[1].lower() for n,_ in items)
        print(f"  后缀分布: {dict(ext)}")
