import os, glob, re, datetime, sys

path = r"C:\Windows\Logs\WindowsUpdate\WindowsUpdate.20261013.112206.271.1.etl"
try:
    # 共享读
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    GENERIC_READ = 0x80000000
    FILE_SHARE_ALL = 0x1 | 0x2 | 0x4
    OPEN_EXISTING = 3
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    h = k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_ALL, None, OPEN_EXISTING, 0, None)
    if h == wintypes.HANDLE(-1).value:
        print("打开失败, err=", ctypes.get_last_error()); sys.exit(1)
    buf = ctypes.create_string_buffer(64*1024*1024)
    n = wintypes.DWORD(0)
    k32.ReadFile(h, buf, len(buf), ctypes.byref(n), None)
    data = buf.raw[:n.value]
    k32.CloseHandle(h)
except Exception as e:
    print("读取异常:", e); sys.exit(1)

print(f"读到 {len(data)} 字节")
for enc in ('utf-16-le', 'ascii'):
    t = data.decode(enc, 'ignore')
    hits = sorted(set(m for m in re.findall(r'[\x20-\x7E]{12,}', t)
                      if re.search(r'Workload|Product=|product specific|HardwareCompat|NotCompatible|License|Available|Criteria', m)))
    if hits:
        print(f"\n--- [{enc}] {len(hits)} 条命中 ---")
        for hh in hits[:40]:
            print("  " + hh[:200])
