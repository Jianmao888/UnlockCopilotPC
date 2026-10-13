import pefile
DLL = r"C:\Windows\System32\InstallService.dll"
pe = pefile.PE(DLL, fast_load=True)
IB = pe.OPTIONAL_HEADER.ImageBase
data = open(DLL, "rb").read()
secs = [(IB+s.VirtualAddress, IB+s.VirtualAddress+s.Misc_VirtualSize, s.PointerToRawData, s.SizeOfRawData) for s in pe.sections]
def rd(va, n):
    for sva, eva, raw, rawsz in secs:
        if sva <= va < eva:
            off = raw + (va - sva)
            return data[off:off+n]
    return b""
# dump 0x1802f9f00 .. 0x1802fa700
start, end = 0x1802f9ef0, 0x1802fa700
buf = rd(start, end-start)
for base in range(0, len(buf), 16):
    va = start + base
    chunk = buf[base:base+16]
    hexs = " ".join(f"{b:02x}" for b in chunk)
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    print(f"{va:012x}  {hexs:<47}  {asc}")
