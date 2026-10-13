import ctypes, glob, os, re, datetime
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
start=datetime.datetime.strptime(open(r"C:\Users\jianm\Code\DeepseekHarness\exp3-starttime.txt").read().strip(),"%Y%m%d.%H%M%S")
files=[f for f in glob.glob(r"C:\Windows\Logs\WindowsUpdate\*.etl") if datetime.datetime.fromtimestamp(os.path.getmtime(f))>start]
print(f"新 ETL: {len(files)} 个")
for f in files:
    d=rd(f)
    if not d: continue
    t=d.decode("utf-16-le","ignore")
    ls=re.findall(r"[\x20-\x7E]{20,}",t)
    prod=[l for l in ls if "Product=" in l and "Criteria" in l]
    tgt=[l for l in ls if "Product Targeting" in l]
    if prod or tgt:
        print(f"\n--- {os.path.basename(f)[:44]} ---")
        for l in prod[:6]: print("  [Criteria] "+l[:210])
        for l in tgt[:6]: print("  [Targeting] "+l[:210])
print("\n(若无输出，说明仍未发生 Product= 专属搜索)")
