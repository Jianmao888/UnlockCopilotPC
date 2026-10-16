import zipfile, glob, os, math, collections, io
root = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验"

targets = []
for f in glob.glob(os.path.join(root, "**", "*.msix"), recursive=True):
    with zipfile.ZipFile(f) as z:
        for i in z.infolist():
            if i.filename.lower().endswith(('.onnxe', '.onemodel')):
                targets.append((os.path.basename(f), i.filename, i.file_size))

def entropy(b):
    if not b: return 0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v/n) * math.log2(v/n) for v in c.values())

print(f"{'包':<52} {'文件':<34} {'MB':>7} {'熵':>6}  魔数")
print("-"*130)
for pkg, name, size in targets:
    full = glob.glob(os.path.join(root, "**", pkg), recursive=True)[0]
    with zipfile.ZipFile(full) as z:
        data = z.read(name)
    head = data[:32]
    e = entropy(data[:262144])
    magic = head[:16].hex()
    ascii_ = "".join(chr(c) if 32 <= c < 127 else "." for c in head[:16])
    print(f"{pkg[:50]:<52} {name[:32]:<34} {size/1e6:7.2f} {e:6.3f}  {ascii_}")
