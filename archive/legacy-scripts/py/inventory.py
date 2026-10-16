#!/usr/bin/env python3
"""inventory.py — 生成已获取 AI 包的完整清单与覆盖度报告"""
import glob
import hashlib
import json
import pathlib
import zipfile
import xml.etree.ElementTree as ET

HERE = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
DIRS = {
    "KB5124010 (新代 5.2/1.8)": HERE / "ai-packages",
    "KB5066835 (旧代 3.7)": HERE / "ai-packages-legacy",
}
REF = pathlib.Path(r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验")

rows = []
for label, d in DIRS.items():
    if not d.exists():
        continue
    for f in sorted(d.glob("*.msix")):
        real = None
        mf_path = d / (f.name + ".AppxManifest.xml")
        if mf_path.exists():
            try:
                root = ET.fromstring(mf_path.read_bytes())
                el = next((n for n in root if n.tag.endswith("Identity")), None)
                real = dict(el.attrib) if el is not None else None
            except Exception:
                pass
        if real is None:
            try:
                with zipfile.ZipFile(f) as z:
                    root = ET.fromstring(z.read("AppxManifest.xml"))
                    el = next((n for n in root if n.tag.endswith("Identity")), None)
                    real = dict(el.attrib) if el is not None else None
            except Exception:
                real = {}
        rows.append({
            "source": label,
            "file": f.name,
            "package": real.get("Name"),
            "version": real.get("Version"),
            "arch": real.get("ProcessorArchitecture"),
            "bytes": f.stat().st_size,
        })

rows.sort(key=lambda r: (r["source"], r["package"] or r["file"]))
total = sum(r["bytes"] for r in rows)

print(f"总共 {len(rows)} 个包, {total/1e6:.1f} MB\n")
for label in DIRS:
    sub = [r for r in rows if r["source"] == label]
    if not sub:
        continue
    print("=" * 90)
    print(f"{label}   {len(sub)} 个 / {sum(r['bytes'] for r in sub)/1e6:.1f} MB")
    print("=" * 90)
    for r in sub:
        print(f"  {r['bytes']/1e6:9.2f} MB  {str(r['package']):56} v{r['version']}")

out = HERE / "ai-packages-inventory.json"
out.write_text(json.dumps({"total_packages": len(rows), "total_bytes": total,
                           "packages": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n清单已写入: {out}")
