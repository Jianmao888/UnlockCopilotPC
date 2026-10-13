import re
p = r"C:\Users\jianm\Code\DeepseekHarness\extracted\oneocr.dll"
d = open(p, "rb").read()

# 导入函数名在 PE 里以 ASCII 出现
apis = ["GetTempPath", "GetTempFileName", "CreateFileW", "CreateFileA", "DeleteFileW",
        "WriteFile", "ReadFile", "MoveFile", "SetFileAttributes", "GetTempPath2",
        "BCryptDecrypt", "BCryptGenerateSymmetricKey", "BCryptImportKey",
        "BCryptOpenAlgorithmProvider", "BCryptDeriveKey", "CreateFile2", "SHCreateDirectory"]
print("=== oneocr.dll 导入/引用中的文件与加密 API ===")
for a in apis:
    n = len(re.findall(re.escape(a).encode() + rb"\x00", d))
    m = len(re.findall(re.escape(a).encode(), d))
    print(f"  {a:32} 精确(带\\0) {n:3}   任意出现 {m:3}")

print("\n=== 查找 'Failed to delete generated ONNX file' 附近的字符串 ===")
for m in re.finditer(rb"[\x20-\x7E]{4,}", d):
    s = m.group(0)
    if b"generated ONNX" in s or b"Missing ONNX" in s or b"creating inference session" in s:
        lo = max(0, m.start()-260)
        hi = min(len(d), m.end()+260)
        ctx = d[lo:hi]
        strs = [x.decode("ascii","ignore") for x in re.findall(rb"[\x20-\x7E]{4,}", ctx)]
        print("\n  --- 命中:", s.decode("ascii","ignore"))
        for x in strs:
            print("      " + x[:140])

print("\n=== 含 'onnx' 且像路径/文件名的字符串（去重）===")
hits = set()
for m in re.finditer(rb"[\x20-\x7E]{4,}", d):
    s = m.group(0).decode("ascii","ignore")
    low = s.lower()
    if ("onnx" in low or "onemodel" in low) and ("." in s) and ("\\" in s or "/" in s or s.endswith((".onnx",".onemodel"))):
        hits.add(s)
for x in sorted(hits)[:25]:
    print("   " + x[:160])
