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
def s_at(va, n=120):
    b=rd(va,n); z=b.find(b"\x00"); return b[:z].decode("ascii","replace") if z>0 else ""

for va,label in [(0x1802a8fc8,"共享类型描述符"),(0x1802a6888,"0x1802a6888"),(0x1802a8708,"0x1802a8708")]:
    print(f"===== {label} @ 0x{va:x} =====")
    b = rd(va, 96)
    for i in range(0, len(b), 16):
        c=b[i:i+16]
        print(f"  +{i:02x}  " + " ".join(f"{x:02x}" for x in c) + "  " + "".join(chr(x) if 32<=x<127 else "." for x in c))
    # 解析为指针
    for i in range(0, len(b)-7, 8):
        v = struct.unpack("<Q", b[i:i+8])[0]
        if IB <= v < IB+0x400000:
            print(f"     ptr +{i:02x} -> 0x{v:x}  {repr(s_at(v))}")
    print()

# 找到 Products 条目的完整解析
print("===== Products 描述符条目 @ 0x1802a72b0 =====")
b = rd(0x1802a72b0, 32)
p_name, p_type, gid, code = struct.unpack("<QIIQ", b) if False else (struct.unpack("<Q",b[0:8])[0], struct.unpack("<Q",b[8:16])[0], struct.unpack("<I",b[16:20])[0], struct.unpack("<I",b[24:28])[0])
print(f"  name ptr = 0x{p_name:x}  -> {repr(s_at(p_name))}")
print(f"  type ptr = 0x{p_type:x}")
print(f"  field[16] = {gid} (0x{gid:x})")
print(f"  field[24] = {code} (0x{code:x})")
print()
print("===== 与其它条目对比 =====")
for off,name in [(0x1802a71f0,'ArrayOfGuid'),(0x1802a7210,'guid'),(0x1802a7230,'SyncProductsParameters'),
                 (0x1802a7250,'SyncCurrentVersionOnly'),(0x1802a7270,'DeviceAttributes'),
                 (0x1802a7290,'CallerAttributes'),(0x1802a72b0,'Products'),(0x1802a72d0,'SyncUpdateParameters')]:
    b = rd(off,32)
    a1=struct.unpack("<I",b[16:20])[0]; a2=struct.unpack("<I",b[20:24])[0]
    a3=struct.unpack("<I",b[24:28])[0]; a4=struct.unpack("<I",b[28:32])[0]
    print(f"  {name:24} +10={a1:>4} (0x{a1:02x})  +14={a2:>4}  +18={a3:>4} (0x{a3:02x})  +1c={a4:>4}")
