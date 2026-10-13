"""ghidra_decompile2.py - decompile ALL functions of AIComponentMgmt.dll,
keep the ones whose pseudocode mentions the product/pinned/store APIs."""
import os
import shutil

GH = r"C:\Users\jianm\Downloads\ghidra_12.1.4_PUBLIC_20260921\ghidra_12.1.4_PUBLIC"
TARGET = r"C:\Users\jianm\Code\DeepseekHarness\ghidra-out\AIComponentMgmt.dll"
PROJ = r"C:\Users\jianm\Code\DeepseekHarness\ghidra-proj2"
OUT = r"C:\Users\jianm\Code\DeepseekHarness\ghidra-out\AIComponentMgmt-all.txt"

os.environ.setdefault("GHIDRA_INSTALL_DIR", GH)

import pyghidra
print("[*] starting pyghidra ...")
pyghidra.start()

from java.io import File
from ghidra.base.project import GhidraProject
from ghidra.app.decompiler import DecompInterface
from ghidra.app.plugin.core.analysis import AutoAnalysisManager
from ghidra.util.task import ConsoleTaskMonitor

KEYWORDS = [
    "IsPackagePinned", "PE_CreateProductEnumerator", "EnumerateInstalledProduct",
    "AppXAllUserStore", "UUPProducts", "Pinned", "StateRepository",
    "uupProductId", "ProductID", "ProductEnumerator",
]

shutil.rmtree(PROJ, ignore_errors=True)
os.makedirs(PROJ, exist_ok=True)

proj = GhidraProject.createProject(PROJ, "AIPy2", False)
print("[*] importing ...")
prog = proj.importProgram(File(TARGET))
mon = ConsoleTaskMonitor()
print("[*] auto-analysis ...")
mgr = AutoAnalysisManager.getAnalysisManager(prog)
mgr.initializeOptions()
mgr.startAnalysis(mon)
print("[*] analysis done")

fm = prog.getFunctionManager()
funcs = list(fm.getFunctions(True))
print("[*] total functions:", len(funcs))

dec = DecompInterface()
dec.openProgram(prog)

kept = 0
total = 0
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("PROGRAM: %s\nfunctions: %d\n\n" % (prog.getName(), len(funcs)))
    for f in funcs:
        total += 1
        try:
            res = dec.decompileFunction(f, 60, mon)
            if not (res and res.decompileCompleted()):
                continue
            c = res.getDecompiledFunction().getC()
        except Exception:
            continue
        if not any(k.lower() in c.lower() for k in KEYWORDS):
            continue
        kept += 1
        fh.write("\n" + "#" * 78 + "\n")
        fh.write("# FUNC %s  %s\n" % (f.getEntryPoint(), f.getName()))
        fh.write("#" * 78 + "\n")
        fh.write(c)
    fh.write("\n\n[kept %d of %d]\n" % (kept, total))

print("[*] kept %d of %d -> %s" % (kept, total, OUT))
proj.close()
