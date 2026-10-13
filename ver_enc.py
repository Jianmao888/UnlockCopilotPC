import sqlite3
c = sqlite3.connect(r"C:\Users\jianm\Code\DeepseekHarness\srd-wu.srd")
print("=== 真实 Package 行的 Version 编码 ===")
for r in c.execute("SELECT _PackageID, PackageFullName, Version, Architecture, Flags, Flags2 FROM Package LIMIT 8"):
    pid, pfn, ver, arch, f, f2 = r
    print(f"  {pfn}")
    print(f"      Version={ver}  0x{ver:016X}   arch={arch}  Flags={f} Flags2={f2}")
    if ver:
        ma = (ver >> 48) & 0xFFFF; mi = (ver >> 32) & 0xFFFF
        bu = (ver >> 16) & 0xFFFF; re = ver & 0xFFFF
        print(f"      -> {ma}.{mi}.{bu}.{re}")
print()
print("=== PackageIdentity 示例 ===")
for r in c.execute("SELECT _PackageIdentityID, PackageFullName FROM PackageIdentity WHERE PackageFullName LIKE '%WindowsWorkload%' LIMIT 5"):
    print("   ", r)
print()
print("=== 我们的包在 Package/PackageIdentity 里的 ID ===")
for r in c.execute("SELECT _PackageID, PackageFullName, Version FROM Package WHERE PackageFullName LIKE '%365%' LIMIT 8"):
    print("   ", r)
c.close()
