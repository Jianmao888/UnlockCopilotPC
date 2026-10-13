import json, os
t = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具"
d = json.load(open(os.path.join(t,"msu-payloads.json"), encoding="utf-8"))
msix = [e for e in d if e.get("name","").endswith(".msix")]
tot = sum(e["size"] for e in msix)
print(f"  载荷数: {len(msix)}   总计: {tot/1e9:.3f} GB")
print(f"\n  按体积排序:")
for e in sorted(msix, key=lambda x:-x["size"])[:20]:
    print(f"    {e['size']/1e6:9.2f} MB  {e['name']}")
print(f"\n  体积 < 5MB 的（可全下）: {sum(1 for e in msix if e['size']<5e6)} 个, 共 {sum(e['size'] for e in msix if e['size']<5e6)/1e6:.1f} MB")
