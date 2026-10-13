import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
DLL = r"C:\Windows\System32\InstallService.dll"
pe = pefile.PE(DLL, fast_load=True)
IB = pe.OPTIONAL_HEADER.ImageBase
data = open(DLL, "rb").read()
text = [s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text"][0]
tva = IB + text.VirtualAddress
tdata = data[text.PointerToRawData:text.PointerToRawData+text.SizeOfRawData]

# 描述符表条目地址（Products=0x1802a72b0, SyncProductsParameters=0x1802a7230, 表基址附近）
targets = {
  "desc:Products":            0x1802a72b0,
  "desc:SyncProductsParams":  0x1802a7230,
  "desc:SyncCurrentVerOnly":  0x1802a7250,
  "desc:DeviceAttributes":    0x1802a7270,
  "desc:CallerAttributes":    0x1802a7290,
  "table_base_guess":         0x1802a71f0,
  "shared_ptr_0x1802a8fc8":   0x1802a8fc8,
}
md = Cs(CS_ARCH_X86, CS_MODE_64)
hits = []
for insn in md.disasm(tdata, tva):
    txt = f"{insn.mnemonic} {insn.op_str}"
    for name, va in targets.items():
        if f"0x{va:x}" in txt:
            hits.append((insn.address, name, txt))
print(f"=== 命中 {len(hits)} 处 ===")
for a, n, t in hits[:40]:
    print(f"  0x{a:x}  [{n}]  {t}")

# 也搜 .rdata/.data 里指向这些条目的指针
import struct
secs = [(IB+s.VirtualAddress, IB+s.VirtualAddress+s.Misc_VirtualSize, s.PointerToRawData, s.SizeOfRawData) for s in pe.sections]
def off2va(off):
    for sva,eva,raw,rawsz in secs:
        if raw<=off<raw+rawsz: return sva+(off-raw)
    return None
print()
print("=== .rdata/.data 中指向表条目的指针 ===")
for name, va in targets.items():
    pat = struct.pack("<Q", va)
    found=[]
    i=0
    while True:
        i = data.find(pat,i)
        if i<0: break
        f=off2va(i)
        if f: found.append(f)
        i+=1
    if found: print(f"  {name}: {', '.join('0x%x'%f for f in found[:6])}")
