#!/usr/bin/env python3
"""
find_service_url.py — 从 WU ETL 日志里找出 ServiceId -> ServiceURL 的对应关系

WU 日志里有一类行：
  ScanQOS. ServerId = <GUID>, SyncType = ..., ServiceURL = <url>, ...
只要扫描所有 ETL，就能把联邦搜索用的各个服务端点列出来。

ETL 被 WU 服务占用，用 FILE_SHARE_READ|WRITE|DELETE 打开。
"""
import ctypes
import glob
import os
import re
import sys
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
k32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k32.CloseHandle.argtypes = [wintypes.HANDLE]

GENERIC_READ = 0x80000000
SHARE_ALL = 0x1 | 0x2 | 0x4
OPEN_EXISTING = 3


def read_shared(path, maxsize=80 * 1024 * 1024):
    h = k32.CreateFileW(path, GENERIC_READ, SHARE_ALL, None, OPEN_EXISTING, 0x80, None)
    if h == wintypes.HANDLE(-1).value:
        return None
    try:
        buf = ctypes.create_string_buffer(maxsize)
        n = wintypes.DWORD(0)
        k32.ReadFile(h, buf, maxsize, ctypes.byref(n), None)
        return buf.raw[:n.value]
    finally:
        k32.CloseHandle(h)


def main():
    base = r"C:\Windows\Logs\WindowsUpdate"
    files = sorted(glob.glob(os.path.join(base, "*.etl")))
    print(f"扫描 {len(files)} 个 ETL ...")
    services = {}     # sid -> set(url)
    interesting = []  # 含 workload 的行

    for f in files:
        data = read_shared(f)
        if not data:
            continue
        t = data.decode("utf-16-le", "ignore")

        # ServerId = X ... ServiceURL = Y
        for m in re.finditer(r"ServerId\s*=\s*([0-9A-Fa-f-]{36})[^\n]{0,400}?ServiceURL\s*=\s*(\S+)", t):
            sid = m.group(1).upper()
            url = m.group(2).rstrip(",;")
            services.setdefault(sid, set()).add(url)

        # 单独出现 ServiceURL 的行
        for m in re.finditer(r"ServiceURL\s*=\s*(\S+)", t):
            url = m.group(1).rstrip(",;")
            services.setdefault("(unknown)", set()).add(url)

        if "Workload" in t or "8B24B027" in t.upper():
            for line in re.findall(r"[\x20-\x7E]{20,}", t):
                if "Workload" in line or "8B24B027" in line.upper():
                    interesting.append((os.path.basename(f), line[:220]))

    print("\n=== ServiceId -> ServiceURL ===")
    for sid in sorted(services):
        for u in sorted(services[sid]):
            print(f"  {sid}  ->  {u}")

    print("\n=== 含 Workload / 8B24B027 的行（去重，最多 40 条）===")
    seen = set()
    n = 0
    for f, line in interesting:
        k = line[:120]
        if k in seen:
            continue
        seen.add(k)
        print(f"  [{f[:34]}] {line}")
        n += 1
        if n >= 40:
            break
    if not n:
        print("  (无)")


if __name__ == "__main__":
    sys.exit(main())
