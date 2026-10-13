import os
try:
    import dnfile
except ImportError:
    print("no dnfile"); raise SystemExit

p = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\Microsoft.Windows.Workloads.winmd"
pe = dnfile.dnPE(p)
print(f"=== {os.path.basename(p)} ===")
md = pe.net.mdtables
for tn in ("TypeDef","Enum","MethodDef","Property","Field","InterfaceImpl"):
    t = getattr(md, tn, None)
    if t is None: continue
    print(f"  {tn}: {len(t.rows)}")

print()
print("=== TypeDef ===")
for r in md.TypeDef.rows:
    ns = r.TypeNamespace or ""
    print(f"  {ns}.{r.TypeName}")

print()
print("=== Enum values (Win365 etc) ===")
for r in md.TypeDef.rows:
    if "NpuType" in (r.TypeName or ""):
        print(f"  --- {r.TypeNamespace}.{r.TypeName} ---")
        if r.FieldList:
            for f in r.FieldList:
                print(f"      field: {f.row.Name}")

print()
print("=== Properties ===")
for r in md.Property.rows:
    print(f"  {r.Name}")
