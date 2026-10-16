import pathlib
HERE = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
DEST = pathlib.Path(r"C:\Users\jianm\Downloads\Windows-AI-包")
for label, d, pat in (("源 ai-packages", HERE/"ai-packages", "*.msix"),
                      ("源 ai-packages-legacy", HERE/"ai-packages-legacy", "*.msix"),
                      ("目标 Windows-AI-包", DEST, "*.msix")):
    fs = list(d.rglob(pat) if d == DEST else d.glob(pat))
    print(f"  {label:26} {len(fs):3} 个 / {sum(f.stat().st_size for f in fs)/1e6:9.1f} MB")
print()
print("=== 目标里最大的 6 个 ===")
fs = sorted(DEST.rglob("*.msix"), key=lambda f: -f.stat().st_size)
for f in fs[:6]:
    print(f"  {f.stat().st_size/1e6:9.2f} MB  {f.name}")
print()
print("=== 旧代 6-模型数据包 实际内容 ===")
d6 = DEST/"01-旧代3.7-KB5066835"/"6-模型数据包"
for f in sorted(d6.glob("*.msix"), key=lambda x:-x.stat().st_size):
    print(f"  {f.stat().st_size/1e6:9.2f} MB  {f.name}")
print(f"  小计: {sum(f.stat().st_size for f in d6.glob('*.msix'))/1e6:.1f} MB")
