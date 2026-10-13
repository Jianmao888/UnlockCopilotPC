import zipfile, glob, os, re
root = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验"
out = r"C:\Users\jianm\Code\DeepseekHarness\extracted"
os.makedirs(out, exist_ok=True)

want = {}
for f in glob.glob(os.path.join(root, "**", "*.msix"), recursive=True):
    with zipfile.ZipFile(f) as z:
        for i in z.infolist():
            n = os.path.basename(i.filename)
            if n in ("oneocr.dll", "TextRecognitionSession.dll", "ScreenRegionDetectionSession.dll",
                     "srdapi.dll", "Microsoft.Windows.AI.MachineLearning.dll"):
                want.setdefault(n, (f, i.filename))

for n,(f,member) in want.items():
    with zipfile.ZipFile(f) as z:
        data = z.read(member)
    p = os.path.join(out, n)
    open(p,"wb").write(data)
    print(f"提取 {n}  {len(data)/1e6:.2f} MB")

# 对 oneocr.dll 做字符串扫描
p = os.path.join(out, "oneocr.dll")
if os.path.exists(p):
    d = open(p,"rb").read()
    print(f"\n=== oneocr.dll 关键字符串 ===")
    pats = [rb"[\x20-\x7E]{6,}"]
    strs = set()
    for m in re.finditer(rb"[\x20-\x7E]{6,}", d):
        s = m.group(0)
        if any(k in s.lower() for k in (b"onemodel", b"onnxe", b"onnx", b"crypt", b"key", b"decrypt",
                                        b"model", b"openvino", b"qnn", b"vitis", b"directml",
                                        b"provider", b"session", b"license", b"signatur")):
            strs.add(s)
    byk = {}
    for s in sorted(strs):
        t = s.decode("ascii","ignore")
        for k in ("onemodel","onnxe","onnx","crypt","openvino","qnn","vitis","directml","provider","licens"):
            if k in t.lower():
                byk.setdefault(k, []).append(t)
    for k, v in byk.items():
        print(f"\n-- 含 '{k}' ({len(v)}) --")
        for x in v[:14]:
            print("   " + x[:150])
