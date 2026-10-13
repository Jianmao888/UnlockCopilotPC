import re, html, os, io
p = r"C:\Users\jianm\Code\DeepseekHarness\oem\add-oempreload.html"
raw = open(p, encoding="utf-8", errors="replace").read()
print(f"HTML 大小: {len(raw)}")

# 提取 <code> 块
blocks = re.findall(r"<code[^>]*>(.*?)</code>", raw, re.S)
print(f"code 块: {len(blocks)} 个")
best = max(blocks, key=len) if blocks else ""
txt = html.unescape(re.sub(r"<[^>]+>", "", best))
print(f"最长 code 块: {len(txt)} 字符")
if txt:
    out = r"C:\Users\jianm\Code\DeepseekHarness\oem\add-OemPreload.ps1"
    open(out, "w", encoding="utf-8").write(txt)
    print(f"已保存: {out}")
    print("\n--- 前 60 行 ---")
    for i, l in enumerate(txt.splitlines()[:60], 1):
        print(f"  {i:3} {l}")
