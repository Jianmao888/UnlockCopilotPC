import dnfile
p = r"C:\Windows\System32\WinMetadata\Windows.Management.winmd"
pe = dnfile.dnPE(p)
md = pe.net.mdtables
def S(x):
    try: return str(x)
    except Exception: return repr(x)

print("=== 所有 TypeDef 含 AI 的 ===")
for r in md.TypeDef.rows:
    tn, ns = S(r.TypeName), S(r.TypeNamespace)
    if "AI" in tn or "AI" in ns:
        print(f"  {ns}.{tn}")

print()
print("=== AIComponent 相关类型的成员 ===")
for r in md.TypeDef.rows:
    tn, ns = S(r.TypeName), S(r.TypeNamespace)
    if "AIComponent" not in tn: continue
    print(f"\n  --- {ns}.{tn} ---")
    if r.FieldList:
        for f in r.FieldList:
            print("      field: " + S(f.row.Name))
    if r.MethodList:
        for m in r.MethodList:
            nm = S(m.row.Name)
            sig = ""
            try:
                if m.row.Signature is not None:
                    pass
            except Exception: pass
            print("      method: " + nm)

print()
print("=== 所有 Property ===")
for r in md.Property.rows:
    print("   " + S(r.Name))
