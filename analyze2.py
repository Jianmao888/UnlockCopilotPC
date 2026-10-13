import html, re
from collections import Counter

raw = open("dr2-prod-P1-text.xml", encoding="utf-8").read()
t = html.unescape(raw)

# 每个 UpdateInfo 的 Xml 片段
infos = re.findall(r"<UpdateInfo>(.*?)</UpdateInfo>", t, re.S)
print(f"UpdateInfo 总数: {len(infos)}\n")

types = Counter()
leaves = Counter()
rows = []
for inf in infos:
    xmlfrag = re.search(r"<Xml>(.*?)</Xml>", inf, re.S)
    frag = html.unescape(xmlfrag.group(1)) if xmlfrag else ""
    uid = re.search(r'UpdateID="([^"]+)"', frag)
    utype = re.search(r'UpdateType="([^"]+)"', frag)
    is_leaf = re.search(r"<IsLeaf>(true|false)</IsLeaf>", inf)
    handler = re.search(r"<HandlerSpecificAction>(\d+)</HandlerSpecificAction>", inf)
    action = re.search(r"<Action>([^<]+)</Action>", inf)
    tname = utype.group(1) if utype else "?"
    types[tname] += 1
    leaf = is_leaf.group(1) if is_leaf else "?"
    leaves[(tname, leaf, action.group(1) if action else "?")] += 1
    rows.append((uid.group(1) if uid else "?", tname, leaf, handler.group(1) if handler else "?",
                 action.group(1) if action else "?"))

print("=== UpdateType 分布 ===")
for k, v in types.most_common():
    print(f"   {k:22} {v}")

print("\n=== (类型, 是否叶子, 动作) 分布 ===")
for k, v in leaves.most_common():
    print(f"   {str(k):50} {v}")

print("\n=== 前 20 条明细 ===")
for r in rows[:20]:
    print(f"   {r[0]:40} type={r[1]:16} leaf={r[2]:5} handler={r[3]:3} action={r[4]}")

print("\n=== 各 Xml 片段里出现的 Properties/其他元素 ===")
props = Counter(re.findall(r"<Properties UpdateType=\"([^\"]+)\"", t))
print("   " + str(dict(props)))
others = Counter(re.findall(r"<([A-Za-z]+)[ />]", t))
print("\n=== 全部 XML 片段里的元素名（前 30）===")
print("   " + ", ".join(list(others.keys())[:30]))
