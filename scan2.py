import re, os
p = r"C:\Users\jianm\Code\DeepseekHarness\extracted\oneocr.dll"
d = open(p, "rb").read()

print("=== oneocr.dll 里与「模型文件读写 / 临时文件 / 密钥」相关的字符串 ===")
def scan(buf, label, kws):
    hits = []
    for m in re.finditer(rb"[\x20-\x7E]{5,}", buf):
        s = m.group(0).decode("ascii", "ignore")
        low = s.lower()
        if any(k in low for k in kws):
            hits.append(s)
    seen = set(); out = []
    for h in hits:
        if h not in seen:
            seen.add(h); out.append(h)
    print(f"\n-- {label} ({len(out)}) --")
    for x in out[:40]:
        print("   " + x[:170])

scan(d, "临时文件/路径/写出", ["tmp", "temp", "gettemppath", "createfile", "writefile",
                            ".onnx", "generated", "delete generated"])
scan(d, "密钥/解密/证书", ["bcrypt", "key", "aes", "chacha", "hmac", "certificate",
                        "signature", "entropy", "pbkdf", "sha256"])
scan(d, "模型加载入口", ["onemodel", "modelparser", "parsemodel", "loadmodel", "inference session"])

print("\n\n=== .onnxe 的处理（在会话 DLL 里找）===")
for n in ("TextRecognitionSession.dll", "ScreenRegionDetectionSession.dll", "srdapi.dll"):
    fp = os.path.join(r"C:\Users\jianm\Code\DeepseekHarness\extracted", n)
    if not os.path.exists(fp): continue
    dd = open(fp, "rb").read()
    hits = set()
    for m in re.finditer(rb"[\x20-\x7E]{5,}", dd):
        s = m.group(0).decode("ascii", "ignore")
        if any(k in s.lower() for k in ("onnxe", "onemodel", "onnx", "crypt", "decrypt", "bcrypt")):
            hits.add(s)
    print(f"\n-- {n} ({len(hits)}) --")
    for x in sorted(hits)[:20]:
        print("   " + x[:160])
