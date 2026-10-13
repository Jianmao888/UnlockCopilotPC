"""etw_dump.py - raw-dump every Event block from the ETW XML, ignoring namespaces."""
import re
import html

P = r"C:\Users\jianm\Code\DeepseekHarness\etw-ensure.xml"
raw = open(P, encoding="utf-8", errors="replace").read()

# 逐个 <Event ...>...</Event>
blocks = re.findall(r"<Event\b.*?</Event>", raw, re.S)
print("Event blocks:", len(blocks))
print()

def field(block, name):
    m = re.search(r'<Data Name="' + re.escape(name) + r'"[^>]*>(.*?)</Data>', block, re.S)
    if not m:
        return None
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()

def prov(block):
    m = re.search(r'<Provider[^>]*Name="([^"]+)"', block)
    return m.group(1) if m else "?"

def eid(block):
    m = re.search(r"<EventID[^>]*>(\d+)</EventID>", block)
    return m.group(1) if m else "?"

WK = ("WindowsWorkload", "Windows.Workload")

print("=" * 78)
print("包含 WindowsWorkload / Windows.Workload 的事件（完整字段）")
print("=" * 78)
n = 0
for b in blocks:
    if not any(k in b for k in WK):
        continue
    n += 1
    print(f"\n--- [{n}] provider={prov(b)} id={eid(b)} ---")
    # 所有 Data 字段
    for m in re.finditer(r'<Data Name="([^"]+)"[^>]*>(.*?)</Data>', b, re.S):
        name = m.group(1)
        val = html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))
        val = re.sub(r"\s+", " ", val).strip()
        if val:
            print(f"    {name} = {val[:300]}")
    # Message
    mm = re.search(r"<Message>(.*?)</Message>", b, re.S)
    if mm:
        msg = html.unescape(re.sub(r"<[^>]+>", "", mm.group(1)))
        msg = re.sub(r"\s+", " ", msg).strip()
        print(f"    MSG = {msg[:300]}")

print()
print("=" * 78)
print("错误码统计（所有含 ErrorCode 的事件）")
print("=" * 78)
from collections import Counter
ec = Counter()
for b in blocks:
    v = field(b, "ErrorCode")
    if v:
        ec[v] += 1
for k, c in ec.most_common(20):
    print(f"  {c:4}  {k}")

print()
print("=" * 78)
print("所有 DeploymentOperation 值及其 Path")
print("=" * 78)
for b in blocks:
    op = field(b, "DeploymentOperation")
    p = field(b, "Path")
    pf = field(b, "PackageFullName")
    if op is not None and (p or pf):
        print(f"  op={op:>4}  path={p}   pfn={pf}")
