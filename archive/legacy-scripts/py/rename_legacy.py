#!/usr/bin/env python3
"""rename_legacy.py — 把旧代 GUID 命名的包改名为真实包名，并保留映射"""
import json
import pathlib
import re
import shutil
import sys

HERE = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
DEST = pathlib.Path(r"C:\Users\jianm\Downloads\Windows-AI-包")

ident = json.loads((HERE / "legacy-identified.json").read_text(encoding="utf-8"))
guid2pkg = {p["file"]: (p["package"], p.get("version")) for p in ident.get("packages", [])}

mapping = []
renamed = 0
for f in sorted(DEST.rglob("*.msix")):
    if not re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}", f.name):
        continue
    info = guid2pkg.get(f.name)
    if not info:
        print(f"  ? 无映射: {f.name}")
        continue
    pkg, ver = info
    # 原 GUID 名形如 <guid>_<version>_x64.msix
    m = re.match(r"^([0-9a-f-]{36})_([^_]+)_(\w+)\.msix$", f.name)
    guid = m.group(1) if m else f.name.split("_")[0]
    arch = m.group(3) if m else "x64"
    v = ver or (m.group(2) if m else "0")
    newname = f"{pkg}_{v}_{arch}__{guid[:8]}.msix"
    newpath = f.with_name(newname)
    if newpath.exists():
        print(f"  ! 目标已存在，跳过: {newname}")
        continue
    f.rename(newpath)
    # 同步改名同目录的 manifest / 签名
    for suffix in (".AppxManifest.xml", ".AppxSignature.p7x"):
        side = f.with_name(f.name + suffix)
        side2 = f.with_name(f.name + suffix)
        if side.exists():
            side.rename(f.with_name(newname + suffix))
    renamed += 1
    mapping.append({"原名": f.name, "新名": newname, "包名": pkg, "版本": v,
                    "原始GUID": guid, "所在目录": str(newpath.parent.relative_to(DEST))})
    print(f"  {f.name[:44]:46} -> {newname}")

ld = DEST / "00-清单"
ld.mkdir(exist_ok=True)
(ld / "旧代GUID名称映射.json").write_text(
    json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n改名 {renamed} 个；映射已写入 00-清单/旧代GUID名称映射.json")
