import sqlite3, os
p = r"C:\Users\jianm\Code\DeepseekHarness\srd-wu.srd"
c = sqlite3.connect(p)
print("  UupProduct rows        =", c.execute("SELECT COUNT(*) FROM UupProduct").fetchone()[0])
print("  UupProductPackage rows =", c.execute("SELECT COUNT(*) FROM UupProductPackage").fetchone()[0])
for r in c.execute("SELECT * FROM UupProduct LIMIT 10"):
    print("   ", r)
c.close()
