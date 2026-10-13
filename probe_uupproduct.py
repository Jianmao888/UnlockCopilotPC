#!/usr/bin/env python3
"""
probe_uupproduct.py — 探测 Windows.Internal.StateRepository.UupProduct 的接口

它是 StateRepository 里管理 UUP 产品记录的 WinRT 类。
如果它有"添加/注册"方法，我们就能自己创建产品记录，让 AIComponentManager 看到组件。
"""
import ctypes
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

IID_FACTORY = bytes.fromhex("3500000000000000c000000000000046")

CLASSES = [
    "Windows.Internal.StateRepository.UupProduct",
    "Windows.Internal.StateRepository.UupProductPackage",
    "Windows.AI.Management.Internal.AIComponentManager",
]


def mkstr(s):
    h = ctypes.c_void_p()
    WindowsCreateString(s, len(s), ctypes.byref(h))
    return h


def sl(ptr, n):
    vt = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0]
    return ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))[n]


def cname(ptr):
    try:
        fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                ctypes.POINTER(ctypes.c_void_p))(sl(ptr, 4))
        h = ctypes.c_void_p()
        if fn(ctypes.c_void_p(ptr), ctypes.byref(h)) < 0 or not h.value:
            return "?"
        ln = ctypes.c_uint(0)
        s = WindowsGetStringRawBuffer(h, ctypes.byref(ln))
        WindowsDeleteString(h)
        return s
    except Exception:
        return "?"


def main():
    RoInitialize(1)
    for cls in CLASSES:
        print("=" * 74)
        print(cls)
        print("=" * 74)
        h = mkstr(cls)
        iid = ctypes.create_string_buffer(IID_FACTORY, 16)
        fac = ctypes.c_void_p()
        hr = RoGetActivationFactory(h, ctypes.cast(iid, ctypes.c_void_p), ctypes.byref(fac))
        WindowsDeleteString(h)
        print(f"  RoGetActivationFactory -> 0x{hr & 0xffffffff:08x}",
              "OK" if hr == 0 else "FAIL")
        if hr < 0:
            print()
            continue
        print(f"  factory = 0x{fac.value:016x}   runtimeClass = {cname(fac.value)}")
        print("  vtable slots 6..24:")
        for s in range(6, 25):
            try:
                a = sl(fac.value, s)
                print(f"     slot[{s:2}] = 0x{a:016x}")
            except Exception as e:
                print(f"     slot[{s:2}] 读取失败 {e}")
        print()


if __name__ == "__main__":
    sys.exit(main())
