#!/usr/bin/env python3
"""srd_dig.py — 深挖 UupProduct 表结构与 Deployment 库里的 Workload/SemanticText 记录"""
import os
import sqlite3
import sys

DST = r"C:\Users\jianm\Code\DeepseekHarness\srd-copy"


def con(name):
    return sqlite3.connect(f"file:{os.path.join(DST, name)}?mode=ro", uri=True)


def show_schema(c, table):
    print(f"\n--- schema: {table} ---")
    try:
        row = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()
        print("  " + (row[0] if row else "(不存在)"))
    except Exception as e:
        print("  失败:", e)


def dump_rows(c, table, limit=30, where=None, params=()):
    print(f"\n--- {table} 前 {limit} 行 ---")
    try:
        cols = [r[1] for r in c.execute(f'PRAGMA table_info("{table}")').fetchall()]
        print("  列: " + ", ".join(cols))
        q = f'SELECT * FROM "{table}"'
        if where:
            q += " WHERE " + where
        q += f" LIMIT {limit}"
        rows = c.execute(q, params).fetchall()
        if not rows:
            print("  (无数据)")
            return
        for r in rows:
            vals = []
            for v in r:
                if isinstance(v, (bytes, bytearray)):
                    v = v[:60].hex()
                s = str(v)
                vals.append(s[:70])
            print("   | ".join(vals))
    except Exception as e:
        print("  失败:", e)


def main():
    print("#" * 78)
    print("# Machine.srd —— UupProduct 相关")
    print("#" * 78)
    c = con("StateRepository-Machine.srd")
    show_schema(c, "UupProduct")
    show_schema(c, "UupProductPackage")
    dump_rows(c, "UupProduct", 10)
    dump_rows(c, "UupProductPackage", 10)
    # 所有含 Uup 的表
    print("\n--- 所有含 Uup 的表及行数 ---")
    for (n,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%Uup%'"):
        try:
            cnt = c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
            print(f"  {n}: {cnt} 行")
        except Exception as e:
            print(f"  {n}: {e}")
    c.close()

    print()
    print("#" * 78)
    print("# Deployment.srd —— File 表里的 Workload / SemanticText")
    print("#" * 78)
    d = con("StateRepository-Deployment.srd")
    show_schema(d, "File")
    cols = [r[1] for r in d.execute('PRAGMA table_info("File")').fetchall()]
    print("\n  列:", ", ".join(cols))
    # 找含 Workload / SemanticText 的行
    textcols = [x for x in cols]
    where = " OR ".join([f'CAST("{x}" AS TEXT) LIKE ?' for x in textcols])
    params = []
    for _ in textcols:
        params.append("%Workload%")
    print("\n--- 含 'Workload' 的行（前 25）---")
    try:
        q = f'SELECT * FROM "File" WHERE {where} LIMIT 25'
        for r in d.execute(q, params):
            vals = []
            for v in r:
                if isinstance(v, (bytes, bytearray)):
                    v = v.decode("utf-8", "ignore")
                vals.append(str(v)[:80])
            print("   | ".join(vals))
    except Exception as e:
        print("  失败:", e)

    params2 = ["%SemanticText%"] * len(textcols)
    print("\n--- 含 'SemanticText' 的行（前 15）---")
    try:
        for r in d.execute(f'SELECT * FROM "File" WHERE {where} LIMIT 15', params2):
            vals = []
            for v in r:
                if isinstance(v, (bytes, bytearray)):
                    v = v.decode("utf-8", "ignore")
                vals.append(str(v)[:80])
            print("   | ".join(vals))
    except Exception as e:
        print("  失败:", e)

    print("\n--- 按 ContentGroup 关联（看这些文件属于哪个包）---")
    show_schema(d, "ContentGroup")
    show_schema(d, "ContentGroupFile")
    d.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
