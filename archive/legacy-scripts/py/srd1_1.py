import sqlite3, binascii
c = sqlite3.connect(r"C:\Users\jianm\Code\DeepseekHarness\srd-wu.srd")
print("=== PkgExtension 表结构 ===")
print(" ", c.execute("SELECT sql FROM sqlite_master WHERE name='PkgExtension'").fetchone()[0])
print()
print("=== 所有 PkgExtension 行 ===")
cols = [d[1] for d in c.execute("PRAGMA table_info(PkgExtension)")]
print("  列:", cols)
for r in c.execute("SELECT * FROM PkgExtension"):
    row = dict(zip(cols, r))
    print()
    for k in cols:
        v = row[k]
        if isinstance(v, (bytes, bytearray)):
            print("   %-22s BLOB %d bytes: %s" % (k, len(v), binascii.hexlify(v[:64]).decode()))
        else:
            print("   %-22s %r" % (k, v))
c.close()
