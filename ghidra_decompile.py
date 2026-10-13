"""ghidra_decompile.py - use PyGhidra as a library to decompile AIComponentMgmt.dll

Finds every function that references the AI-component product APIs, decompiles it,
and writes the C to ghidra-out/AIComponentMgmt-decompiled.txt
"""
import os
import sys

GH = r"C:\Users\jianm\Downloads\ghidra_12.1.4_PUBLIC_20260921\ghidra_12.1.4_PUBLIC"
TARGET = r"C:\Users\jianm\Code\DeepseekHarness\ghidra-out\AIComponentMgmt.dll"
PROJ = r"C:\Users\jianm\Code\DeepseekHarness\ghidra-proj"
OUT = r"C:\Users\jianm\Code\DeepseekHarness\ghidra-out\AIComponentMgmt-decompiled.txt"

os.environ.setdefault("GHIDRA_INSTALL_DIR", GH)

import pyghidra

print("[*] starting pyghidra ...")
pyghidra.start()

from ghidra.base.project import GhidraProject
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

INTEREST = [
    "PE_CreateProductEnumerator",
    "EnumerateInstalledProductByName",
    "uupProductId",
    "AppXAllUserStore",
    "UUPProducts",
    "Pinned",
    "StateRepository",
    "ProductID",
    "GetInstalledProduct",
    "AIComponentManager",
    "ProductEnumerator",
]


def interesting(s):
    if not s:
        return False
    l = s.lower()
    return any(k.lower() in l for k in INTEREST)


print("[*] creating project ...")
import shutil
shutil.rmtree(PROJ, ignore_errors=True)
os.makedirs(PROJ, exist_ok=True)

from java.io import File
proj = GhidraProject.createProject(PROJ, "AIPy", False)
print("[*] importing", TARGET)
prog2 = proj.importProgram(File(TARGET))
print("[*] loaded:", prog2.getName())

# ---- run auto analysis so function bodies exist ----
from ghidra.app.plugin.core.analysis import AutoAnalysisManager
from ghidra.util.task import ConsoleTaskMonitor as _CTM
mon0 = _CTM()
mgr = AutoAnalysisManager.getAnalysisManager(prog2)
print("[*] running auto-analysis (may take a while) ...")
mgr.initializeOptions()
mgr.startAnalysis(mon0)
print("[*] analysis done")
proj.saveAs(prog2, "/", "AIComponentMgmt.dll", True)

fm = prog2.getFunctionManager()
listing = prog2.getListing()
refm = prog2.getReferenceManager()
symtab = prog2.getSymbolTable()

# 1) interesting symbols
sym_hits = []
seen = set()
sit = symtab.getAllSymbols(True)
while sit.hasNext():
    s = sit.next()
    if interesting(s.getName()) and s.getName() not in seen:
        seen.add(s.getName())
        sym_hits.append((s.getName(), s.getAddress()))

# 2) interesting strings
str_hits = []
dit = listing.getDefinedData(True)
while dit.hasNext():
    d = dit.next()
    try:
        v = d.getValue()
    except Exception:
        continue
    if v is None:
        continue
    s = str(v)
    if interesting(s):
        str_hits.append((d.getAddress(), s))

# 3) functions referencing them
funcs = {}
for a in [x[1] for x in sym_hits] + [x[0] for x in str_hits]:
    ri = refm.getReferencesTo(a)
    while ri.hasNext():
        r = ri.next()
        f = fm.getFunctionContaining(r.getFromAddress())
        if f is not None:
            funcs[f.getEntryPoint().getOffset()] = f

with open(OUT, "w", encoding="utf-8") as fh:
    def w(s):
        fh.write(s + "\n")

    w("PROGRAM: " + prog2.getName())
    w("=" * 78)
    w("")
    w("--- interesting symbols (%d) ---" % len(sym_hits))
    for n, a in sym_hits:
        w("  SYM  %-45s @ %s" % (n, a))
    w("")
    w("--- interesting strings (%d) ---" % len(str_hits))
    for a, s in str_hits:
        w("  STR  %s  %s" % (a, s.replace("\n", " ")[:140]))
    w("")
    w("--- functions to decompile (%d) ---" % len(funcs))
    for off in sorted(funcs):
        w("  FUNC %s  %s" % (funcs[off].getEntryPoint(), funcs[off].getName()))

    dec = DecompInterface()
    dec.openProgram(prog2)
    mon = ConsoleTaskMonitor()

    w("")
    w("=" * 78)
    w("DECOMPILED BODIES")
    w("=" * 78)
    for off in sorted(funcs):
        f = funcs[off]
        w("")
        w("#" * 78)
        w("# FUNC %s  %s" % (f.getEntryPoint(), f.getName()))
        w("#" * 78)
        try:
            res = dec.decompileFunction(f, 90, mon)
            if res and res.decompileCompleted():
                w(res.getDecompiledFunction().getC())
            else:
                w("  [decompile failed]")
        except Exception as e:
            w("  [exception] %s" % e)

print("[*] wrote", OUT)
proj.close()
