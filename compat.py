import re, os
p = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\Microsoft.Asg.SemanticIndex.AiFabric.Compatibility.dll"
d = open(p,"rb").read()
print(f"大小: {len(d)/1e6:.2f} MB\n")

# 找 JSON 块
txt = d.decode("utf-8", "ignore")
# 提取包含 "365" 的 JSON 片段
for m in re.finditer(r'\{\s*"(?:365|Lnl|Stx|Qnn|Ptl)"\s*:', txt):
    lo = max(0, m.start()-400)
    hi = min(len(txt), m.start()+1500)
    seg = txt[lo:hi]
    print("="*74)
    print(seg)
    print()
    break

print("="*74)
print("=== 所有平台键 ===")
keys = set(re.findall(r'"(365|Lnl|Stx|Qnn|Ptl|J32|Default|Generic)"\s*:', txt))
print("  ", sorted(keys))

print()
print("=== 该 DLL 的关键字符串 ===")
hits=set()
for m in re.finditer(rb"[\x20-\x7E]{6,}", d):
    s = m.group(0).decode("ascii","ignore")
    low = s.lower()
    if any(k in low for k in ("npudetect","platform","nputype","execution","onnxruntime",
                              "openvino","qnn","directml","compatib","silicon","model")):
        hits.add(s)
for x in sorted(hits)[:30]:
    print("   " + x[:150])
