import ctypes, re
from ctypes import wintypes
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
def rd(p):
    h=k32.CreateFileW(p,0x80000000,0x7,None,3,0x80,None)
    if h==wintypes.HANDLE(-1).value: return None
    try:
        b=ctypes.create_string_buffer(80*1024*1024); n=wintypes.DWORD(0)
        k32.ReadFile(h,b,len(b),ctypes.byref(n),None); return b.raw[:n.value]
    finally:
        try: k32.CloseHandle(h)
        except Exception: pass
f=r"C:\Windows\Logs\WindowsUpdate\WindowsUpdate.20261013.123129.290.1.etl"
t=rd(f).decode("utf-16-le","ignore")
print("  Criteria 中含 Product= 的行:")
hits=[l for l in re.findall(r"[\x20-\x7E]{20,}",t) if "Criteria" in l and "Product=" in l]
for l in hits[:10]: print("    "+l[:200])
if not hits: print("    (无)")
print("  Product Targeting 行:")
for l in re.findall(r"[\x20-\x7E]{20,}",t):
    if "Product Targeting" in l or "ProductAttributes(Caller)" in l:
        print("    "+l[:220])
