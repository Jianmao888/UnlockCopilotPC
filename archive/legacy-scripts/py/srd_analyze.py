#!/usr/bin/env python3
"""
srd_analyze.py — 只读分析 StateRepository（SQLite）里与 AI 组件 / 产品相关的注册

目标是回答：
  1. StateRepository 里有没有 AI 组件（WindowsWorkload / AIComponent）的注册表？
  2. 「产品（Product）」类的记录在哪里？CTAC 清单是否来自这里？
"""
import os
import re
import sqlite3
import sys

DST = r"C:\Users\jianm\Code\DeepseekHarness\srd-copy"
KEYWORDS = ["Workload", "AIComponent", "ContentExtraction", "TextRecognition",
            "SemanticText", "PSOnnxRuntime", "AIFabric", "AICapability"]


def open_db(name):
    p = os.path.join(DST, name)
    if not os.path.exists(p):
        return None
    # 只读打开（副本已含 wal，SQLite 会自动合并）
    try:
        return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    except Exception as e:
        print(f"  打开 {name} 失败: {e}")
        return None


def analyze(name):
    print("=" * 78)
    print(name, f"({os.path.getsize(os.path.join(DST, name))/1e6:.1f} MB)")
    print("=" * 78)
    con = open_db(name)
    if not con:
        return
    cur = con.cursor()

    cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")
    objs = cur.fetchall()
    print(f"  表/视图: {len(objs)} 个")
    names = [n for n, t in objs]
    print("  " + ", ".join(names[:60]))
    if len(names) > 60:
        print(f"  ... 还有 {len(names)-60} 个")

    # 1) 表名里带关键字的
    print("\n  -- 表名含 AI/Workload/Product 的 --")
    hit = [n for n in names if re.search(r"AI|Workload|Product|Capabilit|Model", n, re.I)]
    if hit:
        for n in hit:
            try:
                c = cur.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
                print(f"     {n}  ({c} 行)")
            except Exception as e:
                print(f"     {n}  (读取失败: {e})")
    else:
        print("     (无)")

    # 2) 全表扫描找关键字（只扫文本列，限制表数与行数）
    print("\n  -- 全表扫描关键字 --")
    found = {}
    for n in names:
        try:
            cols = [r[1] for r in cur.execute(f'PRAGMA table_info("{n}")').fetchall()]
        except Exception:
            continue
        textcols = [c for c in cols]
        if not textcols:
            continue
        try:
            cnt = cur.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
        except Exception:
            continue
        if cnt == 0 or cnt > 400000:
            continue
        sel = ", ".join(f'"{c}"' for c in textcols)
        try:
            rows = cur.execute(f'SELECT {sel} FROM "{n}" LIMIT 20000').fetchall()
        except Exception:
            continue
        for row in rows:
            for v in row:
                if isinstance(v, (bytes, bytearray)):
                    try:
                        v = v.decode("utf-8", "ignore")
                    except Exception:
                        continue
                if not isinstance(v, str):
                    continue
                for k in KEYWORDS:
                    if k.lower() in v.lower():
                        found.setdefault((n, k), 0)
                        found[(n, k)] += 1
    if found:
        for (n, k), c in sorted(found.items()):
            print(f"     [{n}] 关键字 '{k}' 命中 {c} 次")
    else:
        print("     (无命中)")

    con.close()


def main():
    for f in ("StateRepository-Machine.srd", "StateRepository-Deployment.srd"):
        if os.path.exists(os.path.join(DST, f)):
            analyze(f)
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
