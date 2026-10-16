import sqlite3, os
p = r"C:\Users\jianm\Code\DeepseekHarness\srd-copy3.srd"
print(f"副本大小: {os.path.getsize(p):,} 字节")
con = sqlite3.connect(p)
cur = con.cursor()
tabs = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print(f"表数: {len(tabs)}")
upi = [t for t in tabs if 'uup' in t.lower() or 'product' in t.lower()]
print(f"UUP/Product 相关表: {upi}")
for t in upi:
    try:
        n = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"   {t}: {n} 行")
        if n:
            cols = [d[1] for d in cur.execute(f'PRAGMA table_info("{t}")')]
            print(f"      列: {cols}")
            for row in cur.execute(f'SELECT * FROM "{t}" LIMIT 5'):
                print(f"      {row}")
    except Exception as e:
        print(f"   {t}: {e}")
print()
print("=== 搜所有表里有没有 .365. / WindowsWorkload 字符串 ===")
found = 0
for t in tabs:
    try:
        cols = [d[1] for d in cur.execute(f'PRAGMA table_info("{t}")')]
        for c in cols:
            try:
                r = cur.execute(f'SELECT COUNT(*) FROM "{t}" WHERE CAST("{c}" AS TEXT) LIKE ?', ('%WindowsWorkload%',)).fetchone()[0]
                if r:
                    print(f"   {t}.{c}: {r} 行")
                    found += 1
            except Exception: pass
    except Exception: pass
if not found: print("   （没找到）")
con.close()
