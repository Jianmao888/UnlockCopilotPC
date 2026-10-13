import pefile, struct
DLL = r"C:\Windows\System32\InstallService.dll"
pe = pefile.PE(DLL, fast_load=True)
IB = pe.OPTIONAL_HEADER.ImageBase
data = open(DLL, "rb").read()
secs = [(s.Name.rstrip(b"\x00").decode(), IB+s.VirtualAddress, IB+s.VirtualAddress+s.Misc_VirtualSize, s.PointerToRawData, s.SizeOfRawData) for s in pe.sections]
def off_to_va(off):
    for n, sva, eva, raw, rawsz in secs:
        if raw <= off < raw+rawsz:
            return sva + (off-raw), n
    return None, None

targets = {
  "SyncProductsParameters": 0x1802f9f80,
  "SyncCurrentVersionOnly": 0x1802f9f98,
  "DeviceAttributes":       0x1802f9fb0,
  "CallerAttributes":       0x1802f9fc8,
  "Products":               0x1802f9fe0,
  "ProductsParameters":     0x1802fa4b0,
}
print("=== 搜索指向这些字符串的 8 字节指针 ===")
for name, va in targets.items():
    pat = struct.pack("<Q", va)
    idx = 0
    found = []
    while True:
        i = data.find(pat, idx)
        if i < 0: break
        fva, sname = off_to_va(i)
        if fva: found.append((fva, sname))
        idx = i+1
    print(f"\n  {name}  (str VA 0x{va:x}) -> {len(found)} 个指针")
    for fva, sname in found[:8]:
        print(f"     ptr @ 0x{fva:x}  [{sname}]")
        # 打印该指针前后各 64 字节，看结构
        start = (fva - 0x180000000)  # not used
        # 找文件偏移
        for n, sva, eva, raw, rawsz in secs:
            if sva <= fva < eva:
                o = raw + (fva - sva)
                lo = max(raw, o-64); hi = min(raw+rawsz, o+80)
                chunk = data[lo:hi]
                for b in range(0, len(chunk), 16):
                    cv = sva + (lo - raw) + b
                    c = chunk[b:b+16]
                    print(f"        {cv:012x}  " + " ".join(f"{x:02x}" for x in c) + "  " + "".join(chr(x) if 32<=x<127 else "." for x in c))
                break
