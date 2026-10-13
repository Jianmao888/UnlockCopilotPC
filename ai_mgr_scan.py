#!/usr/bin/env python3
"""
ai_mgr_scan.py — 获取 AIComponentManager 实例，扫描它的方法槽

路径：
  RoGetActivationFactory(AIComponentManager) -> factory
  factory.slot[6]()                          -> AIComponentManager 实例
  实例.slot[6..N]                            -> 真正的操作方法

每个槽位在独立子进程里试，崩溃被隔离。
用法：
  python ai_mgr_scan.py scan [lo] [hi]
  python ai_mgr_scan.py try <slot>
  python ai_mgr_scan.py info
"""
import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

combase = ctypes.WinDLL("combase.dll")


def _b(n, r, a):
    f = getattr(combase, n); f.restype = r; f.argtypes = a; return f


RoGetActivationFactory = _b("RoGetActivationFactory", ctypes.c_long,
                            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)])
WindowsCreateString = _b("WindowsCreateString", ctypes.c_long,
                         [wintypes.LPCWSTR, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p)])
WindowsDeleteString = _b("WindowsDeleteString", ctypes.c_long, [ctypes.c_void_p])
WindowsGetStringRawBuffer = _b("WindowsGetStringRawBuffer", ctypes.c_wchar_p,
                               [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)])
RoInitialize = _b("RoInitialize", ctypes.c_long, [ctypes.c_int])

CLASS = "Windows.AI.Management.Internal.AIComponentManager"
IID_FACTORY = bytes.fromhex("3500000000000000c000000000000046")


def slot_of(ptr, n):
    vt = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0]
    return ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))[n]


def get_instance(slot_no=6):
    RoInitialize(1)
    h = ctypes.c_void_p()
    WindowsCreateString(CLASS, len(CLASS), ctypes.byref(h))
    iid = ctypes.create_string_buffer(IID_FACTORY, 16)
    fac = ctypes.c_void_p()
    hr = RoGetActivationFactory(h, ctypes.cast(iid, ctypes.c_void_p), ctypes.byref(fac))
    WindowsDeleteString(h)
    if hr < 0:
        raise RuntimeError(f"激活失败 0x{hr & 0xffffffff:08x}")
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(slot_of(fac.value, 6))
    o = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(fac.value), ctypes.byref(o))
    if hr < 0 or not o.value:
        raise RuntimeError(f"slot[6] 失败 0x{hr & 0xffffffff:08x}")
    return o.value


def cname(ptr):
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(slot_of(ptr, 4))
    h = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(h))
    if hr < 0 or not h.value:
        return "?"
    ln = ctypes.c_uint(0)
    s = WindowsGetStringRawBuffer(h, ctypes.byref(ln))
    WindowsDeleteString(h)
    return s


def cmd_info():
    inst = get_instance()
    print(f"实例 = 0x{inst:016x}  类名 = {cname(inst)}")
    print("vtable:")
    for i in range(26):
        print(f"  [{i:2}] = 0x{slot_of(inst, i):016x}")


def cmd_try(s):
    inst = get_instance()
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(slot_of(inst, s))
    o = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(inst), ctypes.byref(o))
    tag = ""
    if hr == 0 and o.value:
        try: tag = " -> obj class " + cname(o.value)
        except Exception: tag = " -> obj"
    elif hr == 0:
        tag = " -> S_OK (null out)"
    print(f"slot[{s}] -> HRESULT 0x{hr & 0xffffffff:08x} out=0x{(o.value or 0):016x}{tag}")


def cmd_scan(lo, hi):
    for s in range(lo, hi + 1):
        try:
            r = subprocess.run([sys.executable, os.path.abspath(__file__), "try", str(s)],
                               capture_output=True, text=True, timeout=60)
            out = (r.stdout or "").strip().splitlines()
            msg = out[-1] if out else ""
            if r.returncode != 0:
                msg = f"slot[{s}] 崩溃/退出 {r.returncode}"
            print("  " + msg)
        except subprocess.TimeoutExpired:
            print(f"  slot[{s}] 超时（可能是阻塞方法）")


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "info"
    if a == "info":
        cmd_info()
    elif a == "try":
        cmd_try(int(sys.argv[2]))
    elif a == "scan":
        lo = int(sys.argv[2]) if len(sys.argv) > 2 else 6
        hi = int(sys.argv[3]) if len(sys.argv) > 3 else 24
        cmd_scan(lo, hi)
