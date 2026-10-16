import zipfile, glob, os, json
root = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验"
# 1) 看包里的平台标记文件
print("=== 包内的平台/数据标记文件 ===")
for f in glob.glob(os.path.join(root, "**", "*.msix"), recursive=True):
    with zipfile.ZipFile(f) as z:
        for i in z.infolist():
            n = os.path.basename(i.filename)
            if n.lower() in ("lnl.txt", "datapkg.txt", "datapkg.std.txt") or n.lower().endswith((".txt",)):
                try:
                    data = z.read(i.filename)
                except Exception:
                    continue
                print(f"\n--- {os.path.basename(f)} :: {i.filename} ({len(data)} bytes) ---")
                print(data[:1200].decode("utf-8", "replace"))
