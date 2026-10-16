import re, os
for f in (r"C:\Users\jianm\Code\DeepseekHarness\oneocr-extract\oneocr.dll",
          r"C:\Users\jianm\Code\DeepseekHarness\oneocr-extract\TextRecognitionSession.dll"):
    d = open(f,"rb").read()
    print(f"--- {os.path.basename(f)} ({len(d)/1e6:.1f} MB) ---")
    hits=set()
    for m in re.finditer(rb"[\x20-\x7E]{6,}", d):
        s = m.group(0).decode("ascii","ignore")
        low = s.lower()
        if any(k in low for k in ("magic_number","crypto.cpp","decrypt","encryptionkey",
                                  "modelkey","ocrkey","aes","symmetric","uncompress",
                                  "keylen","key_len","0x1", "signature")):
            hits.add(s)
    for x in sorted(hits)[:40]:
        print("   " + x[:160])
    print()
