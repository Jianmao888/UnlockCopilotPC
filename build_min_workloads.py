"""build_min_workloads.py - build minimal workloads.json from workloads.365.json

Keeps only the three 365 workloads whose package closure we fully possess.
Pure ASCII. Run elevated (needs write access to SystemApps).
"""
import json
import os
import sys

BASE = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
SRC = os.path.join(BASE, "workloads.365.json")
DST = os.path.join(BASE, "workloads.json")

KEEP = {
    "Windows.Workload.Analysis.365",
    "Windows.Workload.ContentExtraction.365",
    "Windows.Workload.ImageSearch.365",
}

v = json.load(open(SRC, encoding="utf-8-sig"))

wl = [w for w in v["Workloads"] if w.get("Id") in KEEP]
ai = [a for a in v.get("ApiInfos", []) if a.get("Workload") in KEEP]

fams = set()
for w in wl:
    for p in w.get("Packages", []):
        fams.add(p["FamilyName"])
for a in ai:
    sp = a.get("SessionPackage")
    if sp:
        fams.add(sp)

vermap = {}
for p in v.get("Packages", []):
    vermap.setdefault(p["FamilyName"], p.get("Version"))

pkgs = []
for f in sorted(fams):
    e = {"FamilyName": f}
    if vermap.get(f):
        e["Version"] = vermap[f]
    pkgs.append(e)

out = {"Packages": pkgs, "Workloads": wl, "ApiInfos": ai}
with open(DST, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)

print("wrote " + DST)
print("  Packages=%d Workloads=%d ApiInfos=%d" % (len(pkgs), len(wl), len(ai)))
for w in wl:
    print("    workload: " + w["Id"])
for a in ai:
    print("    api: " + str(a.get("ApiClassName")))
