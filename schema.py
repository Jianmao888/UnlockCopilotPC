import sqlite3
p = r"C:\Users\jianm\Code\DeepseekHarness\srd-wu.srd"
c = sqlite3.connect(p)
print("=== UupProduct 结构 ===")
print("  SQL:", c.execute("SELECT sql FROM sqlite_master WHERE name='UupProduct'").fetchone()[0])
for d in c.execute("PRAGMA table_info(UupProduct)"): print("   ", d)
print()
print("=== UupProductPackage 结构 ===")
print("  SQL:", c.execute("SELECT sql FROM sqlite_master WHERE name='UupProductPackage'").fetchone()[0])
for d in c.execute("PRAGMA table_info(UupProductPackage)"): print("   ", d)
print()
print("=== 索引 ===")
for r in c.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND (tbl_name='UupProduct' OR tbl_name='UupProductPackage')"):
    print("   ", r)
print()
print("=== 参考：Package 表结构（前 20 列） ===")
for d in list(c.execute("PRAGMA table_info(Package)"))[:20]: print("   ", d)
print()
print("=== 参考：Package 表里我们包的 PackageId ===")
try:
    for r in c.execute("SELECT PackageId, PackageFullName FROM Package WHERE PackageFullName LIKE '%WindowsWorkload%' LIMIT 6"):
        print("   ", r)
except Exception as e:
    print("   ", e)
c.close()
