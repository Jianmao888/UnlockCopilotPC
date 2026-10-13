import sqlite3, binascii
c = sqlite3.connect(r"C:\Users\jianm\Code\DeepseekHarness\srd-wu.srd")
cols = [d[1] for d in c.execute("PRAGMA table_info(PkgExtension)")]
print("=== 只筛 Name LIKE '%workload%' ===")
rows = list(c.execute("SELECT * FROM PkgExtension WHERE Name LIKE '%workload%'"))
print(f"  {len(rows)} 行")
for r in rows:
    d = dict(zip(cols, r))
    b = d["_Dictionary"]
    print()
    print("  ID=%s  Name=%r  Id=%r  DisplayName=%r" % (d["_PkgExtensionID"], d["Name"], d["Id"], d["DisplayName"]))
    if b:
        print("     _Dictionary %d bytes" % len(b))
        print("     hex : %s" % binascii.hexlify(b[:160]).decode())
        print("     txt : %r" % b.decode("utf-16-le","ignore")[:220])
print()
print("=== 所有 distinct Name（完整） ===")
for r in c.execute("SELECT Name, COUNT(*) FROM PkgExtension GROUP BY Name ORDER BY Name"):
    print("   %-56s %d" % (r[0], r[1]))
c.close()
