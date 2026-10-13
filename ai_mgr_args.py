#!/usr/bin/env python3
"""
ai_mgr_args.py — 用 HSTRING 参数探测 AIComponentManager 的 slot 7..11

slot[6] = GetInstalledComponents() -> IVector（实测 0 项）
slot[7..11] 用无参形式会崩 -> 说明它们接收参数。
本脚本用 HSTRING 参数逐个试，找出 "按名字查询/安装组件" 的方法。

用法: python ai_mgr_args.py <slot> [name]
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

CLASS = "Windows.AI.Management.Internal.AIComponentManager"
IID_FACTORY = bytes.fromhex("3500000000000000c000000000000046")

NAMES = [
    "WindowsWorkload.TextRecognition",
    "WindowsWorkload.TextRecognition.1",
    "TextRecognition",
    "Windows.Workload.ContentExtraction",
    "Windows.Workload.ContentExtraction.amd64",
    "WindowsWorkload.SemanticText",
    "WindowsWorkload.Manager",
    "WindowsWorkload.PSOnnxRuntime",
    "WindowsWorkload",
    "Microsoft.Windows.AI.TextRecognition",
]


def sl(ptr, n):
    vt = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0]
    return ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))[n]


def cname(ptr):
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(sl(ptr, 4))
    h = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(h))
    if hr < 0 or not h.value:
        return "?"
    ln = ctypes.c_uint(0)
    s = WindowsGetStringRawBuffer(h, ctypes.byref(ln))
    WindowsDeleteString(h)
    return s


def mkstr(s):
    h = ctypes.c_void_p()
    WindowsCreateString(s, len(s), ctypes.byref(h))
    return h


def get_mgr():
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
                            ctypes.POINTER(ctypes.c_void_p))(sl(fac.value, 6))
    o = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(fac.value), ctypes.byref(o))
    if hr < 0 or not o.value:
        raise RuntimeError("取实例失败")
    return o.value


def main():
    slot = int(sys.argv[1])
    names = sys.argv[2:] or NAMES
    mgr = get_mgr()
    for nm in names:
        h = mkstr(nm)
        # 形式 A: f(this, HSTRING, void** out)
        try:
            fnA = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
                                     ctypes.POINTER(ctypes.c_void_p))(sl(mgr, slot))
            o = ctypes.c_void_p()
            hr = fnA(ctypes.c_void_p(mgr), h, ctypes.byref(o))
            extra = ""
            if hr == 0 and o.value:
                try: extra = " -> " + cname(o.value)
                except Exception: extra = " -> obj"
            print(f"  [{nm}] A(HSTRING,out) 0x{hr & 0xffffffff:08x} out=0x{(o.value or 0):016x}{extra}")
        except Exception as e:
            print(f"  [{nm}] A 崩溃: {str(e)[:70]}")
        WindowsDeleteString(h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
