"""dump_strings.py - read the wide/ascii strings at the addresses Ghidra showed."""
import struct

DLL = r"C:\Users\jianm\Code\DeepseekHarness\ghidra-out\AIComponentMgmt.dll"
d = open(DLL, "rb").read()

# PE sections -> map RVA to file offset
pe = struct.unpack_from("<I", d, 0x3C)[0]
nsec = struct.unpack_from("<H", d, pe + 6)[0]
optsz = struct.unpack_from("<H", d, pe + 20)[0]
opt = pe + 24
image_base = struct.unpack_from("<Q", d, opt + 24)[0]
secoff = opt + optsz
secs = []
for i in range(nsec):
    o = secoff + i * 40
    name = d[o:o+8].rstrip(b"\0").decode("ascii", "ignore")
    vsz, va, rsz, ra = struct.unpack_from("<IIII", d, o + 8)
    secs.append((name, va, vsz, ra, rsz))

print("image base: 0x%X" % image_base)
for s in secs:
    print("  %-10s VA=0x%08X VSZ=0x%X RAW=0x%X" % (s[0], s[1], s[2], s[3]))


def rva2off(rva):
    for name, va, vsz, ra, rsz in secs:
        if va <= rva < va + max(vsz, rsz):
            return ra + (rva - va)
    return None


def read_wide(va, maxlen=200):
    off = rva2off(va - image_base)
    if off is None:
        return "(no section for 0x%X)" % va
    out = []
    for i in range(maxlen * 2, 2):
        pass
    i = 0
    while i < maxlen * 2:
        ch = struct.unpack_from("<H", d, off + i)[0]
        if ch == 0:
            break
        if 9 <= ch <= 0x7E or ch > 0x2000:
            out.append(chr(ch) if ch < 0x10000 else "?")
        else:
            out.append("\\x%04x" % ch)
        i += 2
    return "".join(out)


TARGETS = [
    (0x180021714, "productName (fallback when param_1[4]==0)"),
    (0x180021a98, "CompareStringOrdinal target"),
    (0x180021ce8, "property 1 (-> param_1[10])"),
    (0x180021d10, "property 2 (-> plStack_258)"),
    (0x180021c78, "error string A"),
    (0x180021cb8, "prop A"),
    (0x180021cd0, "prop B"),
    (0x180021df8, "prop C"),
    (0x180021e08, "prop D"),
    (0x180023417, "FUN_180001668 arg"),
    (0x180020160, "vtable-ish 1"),
    (0x1800201f0, "vtable-ish 2"),
]

print()
print("=" * 78)
for va, label in TARGETS:
    print("0x%08X  %s" % (va, label))
    print("    wide: %r" % read_wide(va))
    off = rva2off(va - image_base)
    if off:
        raw = d[off:off+64]
        print("    raw : " + " ".join("%02x" % b for b in raw))
    print()
