"""etw_analyze.py - analyze the ETW CSV captured during EnsureReadyAsync."""
import csv
import re
import sys
from collections import Counter, OrderedDict

P = r"C:\Users\jianm\Code\DeepseekHarness\etw-ensure.csv"

def cell(v):
    if isinstance(v, list):
        return " ".join(str(x) for x in v)
    return (v or "")


rows = []
with open(P, encoding="utf-8", errors="replace") as fh:
    rd = csv.DictReader(fh)
    for r in rd:
        rows.append({(k or "").strip(): cell(v).strip() for k, v in r.items()})

print("total rows:", len(rows))
print()

# 清理后的列名
keys = list(rows[0].keys()) if rows else []
print("columns:", keys[:14])
print()

# 统计 provider 分布
prov = Counter(r.get("Event Name", "?") for r in rows)
print("=== provider 分布 ===")
for k, v in prov.most_common(20):
    print(f"  {v:5}  {k}")
print()

# 只关心这些 provider
WANT = ("WindowsUpdate", "AppXDeployment", "StateRepository", "AppReadiness")
interesting = [r for r in rows if any(w.lower() in r.get("Event Name", "").lower() for w in WANT)]
print(f"=== 关注 provider 的事件: {len(interesting)} ===")
print()

# 按 provider 分组，列出 event id 分布
byp = OrderedDict()
for r in interesting:
    byp.setdefault(r.get("Event Name"), Counter())[r.get("Event ID")] += 1
for p, c in byp.items():
    print(f"  {p}")
    for eid, n in c.most_common(15):
        print(f"      id={eid:>6}  x{n}")
print()

# 把所有事件的非空额外列拼起来找关键词
KEYWORDS = ["fe2cr", "fe3cr", "tas01", "update.microsoft", "Windows.Workload",
            "UUPProduct", "uup", "Product", "Workload", "AIComponent",
            "Ensure", "Readiness", "AIFabric", "LocalService", "S-1-5-19",
            "status", "error", "0x8007", "fail"]
print("=== 关键词命中 ===")
seen = set()
for r in interesting:
    blob = " | ".join(f"{k}={v}" for k, v in r.items() if v and k not in ("Event Name",))
    for kw in KEYWORDS:
        if kw.lower() in blob.lower():
            key = (r.get("Event Name"), r.get("Event ID"), blob[:160])
            if key in seen:
                break
            seen.add(key)
            print(f"  [{r.get('Event Name')} id={r.get('Event ID')} pid={r.get('PID')}]")
            print(f"      {blob[:300]}")
            break
print()

# 打印所有 WindowsUpdate / StateRepository / AppReadiness 事件
for want in ("WindowsUpdate", "StateRepository", "AppReadiness"):
    sub = [r for r in rows if want.lower() in r.get("Event Name", "").lower()]
    print(f"=== {want}: {len(sub)} 事件 ===")
    for r in sub[:25]:
        blob = " | ".join(f"{k}={v}" for k, v in r.items()
                          if v and k not in ("Event Name","Type","Version","Channel","Level","Opcode","Task","Keyword","Processor Number","Instance ID","Parent Instance ID"))
        print(f"  id={r.get('Event ID'):>6} pid={r.get('PID')}  {blob[:260]}")
    print()
