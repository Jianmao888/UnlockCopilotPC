#!/usr/bin/env python3
"""
xref_products.py — 在 InstallService.dll 中定位构造 <Products> 的代码

思路：
  1. 解析 PE，找到 "SyncProductsParameters" / "Products" / "ProductsParameters"
     这些字符串的虚拟地址
  2. 线性反汇编 .text，找出引用这些地址的指令（x64 RIP 相对寻址）
  3. 打印引用点周围的代码，从中推断 <Products> 的子元素结构

只读，不修改任何文件。
"""
import sys
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

DLL = r"C:\Windows\System32\InstallService.dll"
TARGETS = ["SyncProductsParameters", "ProductsParameters", "Products",
           "SyncCurrentVersionOnly", "DeviceAttributes", "CallerAttributes"]

pe = pefile.PE(DLL, fast_load=True)
image_base = pe.OPTIONAL_HEADER.ImageBase
print(f"ImageBase = 0x{image_base:x}")
print(f"架构      = {'x64' if pe.FILE_HEADER.Machine == 0x8664 else hex(pe.FILE_HEADER.Machine)}")

# ---- 建立 VA <-> 文件偏移 映射 ----
sections = []
for s in pe.sections:
    name = s.Name.rstrip(b"\x00").decode("ascii", "replace")
    va = image_base + s.VirtualAddress
    sections.append((name, va, va + s.Misc_VirtualSize, s.PointerToRawData, s.SizeOfRawData))
    print(f"  段 {name:8} VA=0x{va:012x} 大小=0x{s.Misc_VirtualSize:x}")

def va_to_off(va):
    for _n, sva, eva, raw, rawsz in sections:
        if sva <= va < eva:
            off = raw + (va - sva)
            return off if off < raw + rawsz else None
    return None

# ---- 找字符串 ----
data = open(DLL, "rb").read()
str_vas = {}
for t in TARGETS:
    needle = t.encode("ascii")
    idx = 0
    while True:
        i = data.find(needle, idx)
        if i < 0:
            break
        # 必须是被 NUL 包围的完整字符串
        before_ok = i == 0 or data[i-1] == 0
        after = i + len(needle)
        after_ok = after >= len(data) or data[after] == 0
        if before_ok and after_ok:
            for _n, sva, eva, raw, rawsz in sections:
                if raw <= i < raw + rawsz:
                    va = sva + (i - raw)
                    str_vas.setdefault(t, []).append(va)
        idx = i + 1

print("\n=== 字符串地址 ===")
for t in TARGETS:
    vas = str_vas.get(t, [])
    print(f"  {t:26} -> {', '.join('0x%x' % v for v in vas) if vas else '(未找到)'}")

# ---- 反汇编 .text，找引用 ----
text = None
for s in pe.sections:
    if s.Name.rstrip(b"\x00") == b".text":
        text = s
        break
if text is None:
    print("找不到 .text 段")
    sys.exit(1)

tva = image_base + text.VirtualAddress
tdata = data[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData]
print(f"\n.text: VA=0x{tva:x}, {len(tdata)} 字节，开始反汇编...")

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

x86_to_vas = {}   # target string -> set of string VAs
for t, vas in str_vas.items():
    x86_to_vas[t] = set(vas)

hits = []
for insn in md.disasm(tdata, tva):
    for op in insn.operands:
        # x86 op type 3 = X86_OP_MEM
        if op.type == 3 and op.mem.base == 0x29 + 0:  # placeholder
            pass
    # 更简单：直接看反汇编文本里有没有地址
    txt = f"{insn.mnemonic} {insn.op_str}"
    for t, vas in x86_to_vas.items():
        for v in vas:
            if f"0x{v:x}" in txt:
                hits.append((insn.address, t, v, txt))
                break

print(f"\n=== 引用命中 {len(hits)} 处 ===")
for addr, t, v, txt in hits:
    off = va_to_off(addr)
    print(f"  0x{addr:x}  -> {t}  (str 0x{v:x})")
    print(f"      {txt}")

# ---- 打印命中点附近的代码 ----
if hits:
    print("\n" + "=" * 78)
    print("命中点上下文反汇编（每条 30 条指令窗口）")
    print("=" * 78)
    hit_addrs = sorted(set(h[0] for h in hits))
    for ha in hit_addrs[:6]:
        start = max(tva, ha - 96)
        foff_start = start - tva
        print(f"\n----- 0x{ha:x} 附近 -----")
        count = 0
        for insn in md.disasm(tdata[foff_start:foff_start + 700], start):
            mark = " >>>" if insn.address == ha else "    "
            print(f"{mark} 0x{insn.address:x}:  {insn.mnemonic:8} {insn.op_str}")
            count += 1
            if count > 55:
                break
