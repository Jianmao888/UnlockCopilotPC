# Ghidra postScript: dump function info + decompilation for given RVAs, plus keyword strings.
# Usage: -postScript DumpInfo.py <outFile> <rvaHex> [<rvaHex> ...]
import os

from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

args = getScriptArgs()
outPath = args[0]
rvas = []
for a in args[1:]:
    try:
        rvas.append(int(a, 16))
    except Exception:
        pass

prog = currentProgram
base = prog.getImageBase().getOffset()
fm = prog.getFunctionManager()
st = prog.getSymbolTable()
listing = prog.getListing()

di = DecompInterface()
di.openProgram(prog)
monitor = ConsoleTaskMonitor()

fh = open(outPath, "w")
def w(s):
    fh.write(str(s) + "\n")
    fh.flush()

w("program   : %s" % prog.getName())
w("imagebase : 0x%X" % base)
w("rvas asked: %s" % ", ".join(hex(r) for r in rvas))
w("")

for rva in rvas:
    addr = toAddr(base + rva)
    w("=" * 78)
    w("RVA 0x%X  ->  %s" % (rva, addr))
    func = fm.getFunctionContaining(addr)
    if func is None:
        w("  (no function contains this address)")
        ins = listing.getInstructionAt(addr)
        if ins:
            w("  instruction: %s" % ins)
        continue
    w("  function : %s" % func.getName())
    w("  entry    : %s   (RVA 0x%X)" % (func.getEntryPoint(), func.getEntryPoint().getOffset() - base))
    w("  signature: %s" % func.getPrototypeString(False, False))
    w("  body     : %d bytes" % func.getBody().getNumAddresses())
    xrefs = func.getEntryPoint().getReferences()
    n = 0
    for r in xrefs:
        if r.getReferenceType().isCall() or r.getReferenceType().isJump():
            n += 1
    w("  callers  : %d" % n)
    res = di.decompileFunction(func, 45, monitor)
    if res and res.decompileCompleted():
        code = res.getDecompiledFunction().getC()
        lines = code.split("\n")
        w("  ---- decompiled (first 120 lines) ----")
        for line in lines[:120]:
            w("    " + line)
    else:
        w("  (decompilation failed)")
    w("")

# interesting strings
w("=" * 78)
w("strings of interest:")
keys = ["Workload", "workload", "Lnl", "LNL", "Stx", "365", "Session", "session",
        "Family", "family", "Resolve", "resource", "Resource", "Recall", "ClickToDo",
        "Copilot", "A9", "Hcf", "HCF", "hybrid", "Hybrid", "NPU", "npu"]
seen = 0
for d in prog.getListing().getDefinedData(True):
    try:
        v = d.getValue()
        if v is None:
            continue
        s = str(v)
    except Exception:
        continue
    if len(s) < 5 or len(s) > 200:
        continue
    if any(k in s for k in keys):
        w("  %s  %s" % (d.getAddress(), s))
        seen += 1
        if seen > 300:
            break
w("(strings listed: %d)" % seen)
fh.close()
print("DumpInfo wrote %s" % outPath)
