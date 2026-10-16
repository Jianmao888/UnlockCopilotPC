#!/usr/bin/env python3
"""verify_copies.py — 逐文件比对源目录与整理后的副本（大小 + SHA256）"""
import hashlib
import pathlib
import sys

HERE = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
DEST = pathlib.Path(r"C:\Users\jianm\Downloads\Windows-AI-包")

SRC_DIRS = [HERE / "ai-packages", HERE / "ai-packages-legacy"]


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


src = {}
for d in SRC_DIRS:
    for f in d.glob("*.msix"):
        src[f.name] = f

dst = {}
for f in DEST.rglob("*.msix"):
    dst[f.name] = f

print(f"源: {len(src)} 个    整理后: {len(dst)} 个\n")

missing = sorted(set(src) - set(dst))
extra = sorted(set(dst) - set(src))
if missing:
    print("❌ 缺失:")
    for n in missing:
        print(f"   {n}  ({src[n].stat().st_size/1e6:.2f} MB)")
if extra:
    print("⚠ 多出:")
    for n in extra:
        print(f"   {n}")
if not missing and not extra:
    print("✔ 文件集合一致")

print("\n逐文件校验（大小 + SHA256）:")
bad = 0
total = 0
for name, s in sorted(src.items()):
    if name not in dst:
        continue
    d = dst[name]
    sz_ok = s.stat().st_size == d.stat().st_size
    h1 = sha256_of(s)
    h2 = sha256_of(d)
    h_ok = h1 == h2
    total += s.stat().st_size
    if not (sz_ok and h_ok):
        bad += 1
        print(f"  ✗ {name}")
        print(f"      源 {s.stat().st_size} / 副本 {d.stat().st_size}   hash {'== ' if h_ok else '!='}")
print(f"\n校验完成: {len(src)-len(missing)} 个文件, 不一致 {bad} 个")
print(f"源总计: {total/1e6:.1f} MB")

# 源目录自身统计
for d in SRC_DIRS:
    fs = list(d.glob("*.msix"))
    print(f"  {d.name}: {len(fs)} 个 / {sum(f.stat().st_size for f in fs)/1e6:.1f} MB")
