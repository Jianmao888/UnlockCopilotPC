import ctypes, glob, os, re, datetime
from ctypes import wintypes
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
def rd(p):
    h = k32.CreateFileW(p, 0x80000000, 0x7, None, 3, 0x80, None)
    if h == wintypes.HANDLE(-1).value: return None
    try:
        buf = ctypes.create_string_buffer(80*1024*1024); n = wintypes.DWORD(0)
        k32.ReadFile(h, buf, len(buf), ctypes.byref(n), None)
        return buf.raw[:n.value]
    finally:
        try: k32.CloseHandle(h)
        except Exception: pass

start = datetime.datetime.strptime(open(r"C:\Users\jianm\Code\DeepseekHarness\exp2-starttime.txt").read().strip(), "%Y%m%d.%H%M%S")
files = [f for f in glob.glob(r"C:\Windows\Logs\WindowsUpdate\*.etl") if datetime.datetime.fromtimestamp(os.path.getmtime(f)) > start]
print(f"新 ETL: {len(files)} 个")
found_any = False
for f in files:
    d = rd(f)
    if not d: continue
    t = d.decode("utf-16-le", "ignore")
    for m in re.finditer(r"ProductAttributes\(CTAC\)([^\x00]{0,3000})", t):
        seg = m.group(1)
        found_any = True
        print(f"\n--- {os.path.basename(f)[:40]} 的 CTAC ---")
        for pn in re.findall(r"PN=([A-Za-z0-9_.{}-]+)", seg):
            mark = "   <<<<<< 命中了！" if "Workload" in pn else ""
            print(f"    PN={pn}{mark}")
        break
if not found_any:
    print("新 ETL 中未找到 CTAC 行（可能扫描未产生该日志）")
