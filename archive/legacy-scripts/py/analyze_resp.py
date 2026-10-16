import re, html
from xml.etree import ElementTree as ET

xml = open("dr2-prod-P1-text.xml", encoding="utf-8").read()
# 响应里 XML 片段是转义的，先反转义
t = html.unescape(xml)
try:
    root = ET.fromstring(t)
except Exception as e:
    print("解析失败:", e); root = None

# 收集所有 UpdateIdentity 与其上下文
print("=== 34 个 UpdateIdentity 及其携带的信息 ===")
ids = re.findall(r'<UpdateIdentity[^>]*UpdateID="([^"]+)"[^>]*RevisionNumber="([^"]*)"', t)
print(f"共 {len(ids)} 个\n")
for uid, rev in ids:
    print(f"  {uid}  rev={rev}")

print("\n=== 所有 Title / Description / 产品名 ===")
for tag in ("Title", "Description", "ProductName", "Product", "CategoryName", "MsrcSeverity"):
    vals = set(re.findall(rf"<{tag}>([^<]+)</{tag}>", t))
    if vals:
        print(f"\n-- {tag} ({len(vals)}) --")
        for v in sorted(vals)[:40]:
            print("   " + v[:150])

print("\n=== 关键字搜索 ===")
for kw in ("Workload", "orkload", "ContentExtraction", "Analysis", "AI", "Model", "Onnx", "NPU", "Copilot"):
    hits = re.findall(rf"[\w\.\-/]{{0,60}}{kw}[\w\.\-/]{{0,60}}", t)
    u = sorted(set(hits))
    if u:
        print(f"  [{kw}] {len(u)} 种:")
        for x in u[:12]: print("      " + x[:130])
