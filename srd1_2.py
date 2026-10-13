import sqlite3, binascii, struct
c = sqlite3.connect(r"C:\Users\jianm\Code\DeepseekHarness\srd-wu.srd")
cols = [d[1] for d in c.execute("PRAGMA table_info(PkgExtension)")]
print("=== 含 workload / com.microsoft 的 PkgExtension ===")
rows = list(c.execute("SELECT * FROM PkgExtension WHERE Name LIKE '%workload%' OR Name LIKE '%com.microsoft%' OR DisplayName LIKE '%Workload%'"))
print(f"  匹配 {len(rows)} 行")
for r in rows:
    d = dict(zip(cols, r))
    print()
    print("  _PkgExtensionID=%s  Name=%r  Id=%r" % (d["_PkgExtensionID"], d["Name"], d["Id"]))
    print("     DisplayName=%r  Extension=%s" % (d["DisplayName"], d["Extension"]))
    b = d["_Dictionary"]
    if b:
        print("     _Dictionary %d bytes: %s" % (len(b), binascii.hexlify(b[:96]).decode()))
        # 试着当 UTF-16LE 解读
        try:
            s = b.decode("utf-16-le", "ignore")
            print("     as utf16le: %r" % s[:200])
        except Exception as e:
            print("     utf16 fail:", e)
    else:
        print("     _Dictionary = NULL")
print()
print("=== 全部不同 Name 值 ===")
for r in c.execute("SELECT DISTINCT Name FROM PkgExtension ORDER BY Name"):
    n = r[0]
    cnt = c.execute("SELECT COUNT(*) FROM PkgExtension WHERE Name=?", (n,)).fetchone()[0]
    print("   %-55s %d 行" % (n, cnt))
c.close()
