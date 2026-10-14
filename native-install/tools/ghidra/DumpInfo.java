// Ghidra GhidraScript: dump function + decompilation for given RVAs, plus interesting strings.
// Usage: -postScript DumpInfo.java <outFile> <rvaHex> [<rvaHex> ...]
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import java.io.FileWriter;
import java.io.PrintWriter;

public class DumpInfo extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) { println("need outFile and at least one RVA"); return; }
        PrintWriter w = new PrintWriter(new FileWriter(args[0]));
        try {
            long base = currentProgram.getImageBase().getOffset();
            w.println("program    : " + currentProgram.getName());
            w.println("imagebase  : 0x" + Long.toHexString(base));
            w.println("");

            DecompInterface di = new DecompInterface();
            di.openProgram(currentProgram);

            for (int i = 1; i < args.length; i++) {
                long rva = Long.parseLong(args[i].replace("0x", ""), 16);
                Address a = toAddr(base + rva);
                w.println("==================================================================");
                w.println("RVA 0x" + Long.toHexString(rva) + "  ->  " + a);
                Function f = getFunctionContaining(a);
                if (f == null) {
                    w.println("  (no function contains this address)");
                    if (getInstructionAt(a) != null) w.println("  insn: " + getInstructionAt(a));
                    continue;
                }
                w.println("  function : " + f.getName());
                w.println("  entry    : " + f.getEntryPoint());
                w.println("  body     : " + f.getBody().getNumAddresses() + " bytes");
                w.println("  signature: " + f.getPrototypeString(false, false));
                DecompileResults r = di.decompileFunction(f, 90, monitor);
                if (r != null && r.decompileCompleted()) {
                    String[] lines = r.getDecompiledFunction().getC().split("\n");
                    w.println("  ---- decompiled (first 160 lines) ----");
                    for (int k = 0; k < Math.min(lines.length, 160); k++) w.println("    " + lines[k]);
                } else {
                    w.println("  (decompilation failed)");
                }
                w.println("");
            }

            w.println("==================================================================");
            w.println("strings of interest:");
            String[] keys = {"Workload", "workload", "Lnl", "LNL", "Stx", "365", "Session", "session",
                             "Family", "family", "Resolve", "resource", "Resource", "Recall", "ClickToDo",
                             "Copilot", "A9", "Hcf", "HCF", "Hybrid", "hybrid", "NPU", "npu", "TextRecognition"};
            int n = 0;
            DataIterator it = currentProgram.getListing().getDefinedData(true);
            while (it.hasNext() && n < 400) {
                Data d = it.next();
                try {
                    Object v = d.getValue();
                    if (v == null) continue;
                    String s = v.toString();
                    if (s.length() < 5 || s.length() > 200) continue;
                    for (String k : keys) {
                        if (s.contains(k)) { w.println("  " + d.getAddress() + "  " + s); n++; break; }
                    }
                } catch (Exception e) { }
            }
            w.println("(strings listed: " + n + ")");
        } finally {
            w.close();
        }
        println("DumpInfo finished");
    }
}
