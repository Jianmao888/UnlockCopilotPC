import pefile, struct
DLL = r"C:\Windows\System32\InstallService.dll"
pe = pefile.PE(DLL, fast_load=True)
IB = pe.OPTIONAL_HEADER.ImageBase
data = open(DLL, "rb").read()
secs = [(IB+s.VirtualAddress, IB+s.VirtualAddress+s.Misc_VirtualSize, s.PointerToRawData, s.SizeOfRawData) for s in pe.sections]
def rd(va,n):
    for sva,eva,raw,rawsz in secs:
        if sva<=va<eva:
            o=raw+(va-sva); return data[o:o+n]
    return b""
def str_at(va):
    b = rd(va, 200)
    z = b.find(b"\x00")
    return b[:z].decode("ascii","replace") if z>0 else ""

print("=== 区域 0x1802a68c0 - 0x1802a6950（引用共享指针的表）===")
buf = rd(0x1802a68c0, 0x1802a6960-0x1802a68c0)
for base in range(0, len(buf), 16):
    va = 0x1802a68c0 + base
    c = buf[base:base+16]
    print(f"{va:012x}  " + " ".join(f"{x:02x}" for x in c) + "  " + "".join(chr(x) if 32<=x<127 else "." for x in c))

print()
print("=== 把该区域解析为 8 字节指针 ===")
for base in range(0, len(buf)-7, 8):
    va = 0x1802a68c0 + base
    v = struct.unpack("<Q", buf[base:base+8])[0]
    if IB <= v < IB+0x400000:
        s = str_at(v)
        print(f"  @0x{va:x} -> 0x{v:x}  {repr(s) if s else ''}")
