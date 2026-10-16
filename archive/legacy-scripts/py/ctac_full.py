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
        k32.ReadFile(h, buf, len(buf), ctypes.byref(n), None); return buf.raw[:n.value]
    finally:
        try: k32.CloseHandle(h)
        except Exception: pass
f = r"C:\Windows\Logs\WindowsUpdate\WindowsUpdate.20261013.123129.290.1.etl"
t = rd(f).decode("utf-16-le", "ignore")
lines = re.findall(r"[\x20-\x7E]{15,}", t)
print("-- 所有 PN= 声明 --")
pns = set()
for l in lines:
    for m in re.finditer(r"PN=([A-Za-z0-9_.{}-]+)", l):
        pns.add(m.group(1))
for p in sorted(pns):
    print(("   * " if "Workload" in p else "     ") + p)
print()
print("-- 与 Workload 相关的其他行 --")
for l in lines:
    if "Workload" in l and "PN=" not in l:
        print("   " + l[:200])
print()
print("-- 与更新数量/结果相关的行 --")
for l in lines:
    if re.search(r"Updates found|NumberOfNewUpdates|NumberOfUpdatesEvaluated|SyncResult|Found \d+ updates", l):
        print("   " + l[:200])
