import sqlite3, os, glob
d = r"C:\Users\jianm\Code\DeepseekHarness\srd-copy2"
f = os.path.join(d, "StateRepository-Machine.srd")
if not os.path.exists(f):
    print("副本不存在"); raise SystemExit
con = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tabs = [r[0] for r in cur.fetchall()]
print(f"表数: {len(tabs)}")
print("含 Uup 的表:", [t for t in tabs if 'uup' in t.lower()])
for t in tabs:
    if 'uup' in t.lower():
        try:
            n = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            print(f"  {t}: {n} 行")
            if n:
                cols=[r[1] for r in cur.execute(f'PRAGMA table_info("{t}")')]
                print("    列:", cols)
                for r in cur.execute(f'SELECT * FROM "{t}" LIMIT 5'):
                    print("    ", str(r)[:250])
        except Exception as e:
            print(f"  {t}: {e}")

print()
print("=== PkgExtension 表里 workload 相关行 ===")
try:
    cols=[r[1] for r in cur.execute('PRAGMA table_info("PkgExtension")')]
    print("列:", cols)
    for r in cur.execute('SELECT * FROM "PkgExtension" LIMIT 20'):
        print("  ", str(r)[:260])
except Exception as e:
    print("err:", e)

print()
print("=== 全库搜 'ContentExtraction.LNL' 相关 ===")
hits=0
for t in tabs:
    try:
        cols=[r[1] for r in cur.execute(f'PRAGMA table_info("{t}")')]
    except Exception:
        continue
    if not cols: continue
    for i,row in enumerate(cur.execute(f'SELECT * FROM "{t}" LIMIT 30000')):
        s=str(row)
        if 'ContentExtraction.LNL' in s or 'Workload.ContentExtraction' in s:
            print(f"  [{t}] {s[:260]}")
            hits+=1
            if hits>10: break
    if hits>10: break
if not hits: print("  (无)")
con.close()
