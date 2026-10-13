import pathlib, hashlib, json, re
DEST = pathlib.Path(r"C:\Users\jianm\Downloads\Windows-AI-包")
def sha256_of(p):
    h = hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda: f.read(1<<20), b""): h.update(b)
    return h.hexdigest()
inv=[]
for f in sorted(DEST.rglob("*.msix")):
    rel = f.relative_to(DEST)
    gen = rel.parts[0]; cat = rel.parts[1] if len(rel.parts)>2 else ""
    pkg = f.name.rsplit("_",2)[0]
    inv.append({"代际":gen,"类别":cat,"包名":pkg,"文件":f.name,
                "字节":f.stat().st_size,"SHA256":sha256_of(f)})
ld = DEST/"00-清单"; ld.mkdir(exist_ok=True)
(ld/"包清单.json").write_text(json.dumps(inv,indent=2,ensure_ascii=False),encoding="utf-8")
(ld/"SHA256清单.json").write_text(json.dumps(
    [{"文件":r["文件"],"SHA256":r["SHA256"],"字节":r["字节"]} for r in inv],
    indent=2,ensure_ascii=False),encoding="utf-8")
print(f"清单已刷新: {len(inv)} 个包 / {sum(r['字节'] for r in inv)/1e6:.1f} MB")
