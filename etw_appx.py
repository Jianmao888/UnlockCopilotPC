"""etw_appx.py - dump full AppXDeployment-Server events and WU search calls from the ETW XML."""
import re
import xml.etree.ElementTree as ET

P = r"C:\Users\jianm\Code\DeepseekHarness\etw-ensure.xml"

tree = ET.parse(P)
root = tree.getroot()

ns = ""
if root.tag.startswith("{"):
    ns = root.tag.split("}")[0] + "}"


def txt(el):
    return "".join(el.itertext()).strip()


events = []
for ev in root.iter(ns + "Event"):
    prov = ""
    sysel = ev.find(ns + "System")
    if sysel is not None:
        p = sysel.find(ns + "Provider")
        if p is not None:
            prov = p.get("Name") or p.get("EventSourceName") or ""
        eid = sysel.find(ns + "EventID")
        eid = txt(eid) if eid is not None else "?"
        tid = sysel.find(ns + "TimeCreated")
        ts = tid.get("SystemTime") if tid is not None else ""
        pid = sysel.find(ns + "Execution")
        pid = pid.get("ProcessID") if pid is not None else ""
    else:
        eid = "?"; ts = ""; pid = ""
    data = {}
    dlist = ev.find(ns + "EventData")
    if dlist is not None:
        for d in dlist:
            n = d.get("Name") or "?"
            data[n] = txt(d)
    if not data:
        ud = ev.find(ns + "UserData")
        if ud is not None:
            for c in ud.iter():
                tag = c.tag.split("}")[-1]
                if c.text and c.text.strip():
                    data.setdefault(tag, c.text.strip())
    events.append({"prov": prov, "eid": eid, "ts": ts, "pid": pid, "data": data})

print("total events:", len(events))
print()

# ---- 1. AppXDeployment-Server 全部事件 ----
print("=" * 78)
print("AppXDeployment-Server 全部事件")
print("=" * 78)
for e in events:
    if "AppXDeployment-Server" not in e["prov"]:
        continue
    print(f"\n--- id={e['eid']}  pid={e['pid']}  {e['ts']} ---")
    for k, v in e["data"].items():
        v2 = v.replace("\r", " ").replace("\n", " ")
        print(f"    {k}: {v2[:400]}")

# ---- 2. WindowsUpdateClient 全部事件 ----
print()
print("=" * 78)
print("WindowsUpdateClient 全部事件（含 UserData）")
print("=" * 78)
for e in events:
    if "WindowsUpdateClient" not in e["prov"]:
        continue
    print(f"\n--- id={e['eid']}  pid={e['pid']}  {e['ts']} ---")
    for k, v in e["data"].items():
        v2 = v.replace("\r", " ").replace("\n", " ")
        print(f"    {k}: {v2[:400]}")

# ---- 3. 全文搜关键字符串 ----
print()
print("=" * 78)
print("全文关键词命中")
print("=" * 78)
raw = open(P, encoding="utf-8", errors="replace").read()
for kw in ("Windows.Workload", "ContentExtraction", "UupProduct", "Product=",
           "fe3cr", "fe2cr", "IsInstalled", "DeploymentAction", "Workload"):
    idxs = [m.start() for m in re.finditer(re.escape(kw), raw)]
    if not idxs:
        continue
    print(f"\n  '{kw}'  x{len(idxs)}")
    for i in idxs[:6]:
        seg = raw[max(0, i - 120): i + 200]
        seg = re.sub(r"\s+", " ", seg)
        print(f"      ...{seg}...")
