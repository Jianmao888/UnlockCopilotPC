import os, dnfile
p = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\Microsoft.Windows.Workloads.winmd"
pe = dnfile.dnPE(p)
md = pe.net.mdtables

def S(x):
    try: return str(x)
    except Exception: return repr(x)

print("=== Enum: NpuType ===")
for r in md.TypeDef.rows:
    if S(r.TypeName) == "NpuType":
        if r.FieldList:
            for f in r.FieldList:
                print("   " + S(f.row.Name))

print()
print("=== TypeDef -> methods ===")
for r in md.TypeDef.rows:
    tn = S(r.TypeName)
    if tn not in ("WorkloadManager","IWorkloadManagerStatics","IWorkloadManagerStatics2",
                  "IWorkloadManagerStatics3","IWorkloadManagerStatics4",
                  "IWorkloadManager5","IWorkloadManager6","ApiInfo"): continue
    print(f"  --- {S(r.TypeNamespace)}.{tn} ---")
    if r.MethodList:
        for m in r.MethodList:
            print("      " + S(m.row.Name))

print()
print("=== Properties ===")
for r in md.Property.rows:
    print("   " + S(r.Name))
