import json
import pathlib
import re
import shutil

W = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness\.dsh-tmp\onepkg")
DST = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness\ai-products\_rum-new")
DST.mkdir(parents=True, exist_ok=True)

saved = 0
seen = set()
for root in (W / "x", W):
    for f in root.rglob("*.json"):
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if '"ProductIdentifier"' not in t or "Windows.Workload" not in t:
            continue
        m = re.search(r'"ProductIdentifier"\s*:\s*"([^"]+)"', t)
        v = re.search(r'"ProductVersion"\s*:\s*"([^"]+)"', t)
        if not m:
            continue
        pid = m.group(1)
        ver = v.group(1) if v else "0"
        if (pid, ver) in seen:
            continue
        seen.add((pid, ver))
        name = "%s.%s.rum.json" % (pid, ver)
        shutil.copy2(f, DST / name)
        try:
            meta = json.loads(t)
            ups = meta.get("UpdateProduct", [])
            ents = len(ups[0].get("UpdateEntityCollection", [])) if ups else 0
        except Exception:
            ents = -1
        print("  saved %-56s %6d B  entities=%d" % (name, f.stat().st_size, ents))
        saved += 1

print("total new-generation RUMs saved:", saved)
print("dir:", DST)

# also list what payload (package, version) pairs each product wants, locally satisfied or not
print()
local = {}
for tree in (pathlib.Path(r"C:\Users\jianm\Downloads"), pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")):
    for p in tree.rglob("WindowsWorkload.*.msix"):
        parts = p.name.split("_")
        if len(parts) >= 2:
            local.setdefault((parts[0], parts[1]), p)

for f in sorted(DST.glob("*.rum.json")):
    meta = json.loads(f.read_text(encoding="utf-8", errors="replace"))
    for up in meta.get("UpdateProduct", []):
        need, have = [], 0
        for e in up.get("UpdateEntityCollection", []):
            for pl in e.get("EntityPayload", {}).get("Canonical", []) or []:
                pn = pl["PayloadName"]
                if not pn.endswith(".msix"):
                    continue
                pkg = e["EntityIdentifier"]["EntityName"].split("_")[0]
                ver = pn.split("_")[1]
                need.append((pkg, ver))
                if (pkg, ver) in local:
                    have += 1
        print("  %-46s need=%-3d local-exact=%-3d  %s" % (
            up.get("ProductIdentifier"), len(need), have,
            "READY" if have == len(need) else "missing=%d" % (len(need) - have)))
