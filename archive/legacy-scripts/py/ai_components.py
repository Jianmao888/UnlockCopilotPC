#!/usr/bin/env python3
"""
ai_components.py — 枚举 Windows.AI.Management.Internal.AIComponentManager 返回的 AI 组件列表

链路：
  RoGetActivationFactory(AIComponentManager) -> factory
  factory.slot[6]()                          -> manager 实例
  manager.slot[6]()                          -> IVector<AIComponent>
  vector.slot[7]()                           -> size
  vector.slot[6](index)                      -> AIComponent
  component.slot[N]()                        -> 属性

用法: python ai_components.py
"""
import ctypes
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


def sl(ptr, n):
    vt = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0]
    return ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))[n]


def hstr(ptr):
    ln = ctypes.c_uint(0)
    s = WindowsGetStringRawBuffer(ctypes.c_void_p(ptr), ctypes.byref(ln))
    return s


def cname(ptr):
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(sl(ptr, 4))
    h = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(h))
    if hr < 0 or not h.value:
        return "?"
    s = hstr(h.value)
    WindowsDeleteString(h)
    return s


def call_out(ptr, n, *args):
    """f(this, args..., void** out)"""
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *([ctypes.c_uint32] * len(args)),
                            ctypes.POINTER(ctypes.c_void_p))(sl(ptr, n))
    o = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(ptr), *[ctypes.c_uint32(a) for a in args], ctypes.byref(o))
    return hr, (o.value or 0)


def call_size(ptr, n):
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_uint32))(sl(ptr, n))
    o = ctypes.c_uint32(0)
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(o))
    return hr, o.value


def hstring_out(ptr, n):
    """f(this, HSTRING* out)"""
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(sl(ptr, n))
    o = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(o))
    if hr < 0 or not o.value:
        return hr, None
    s = hstr(o.value)
    WindowsDeleteString(o)
    return hr, s


def bool_out(ptr, n):
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte))(sl(ptr, n))
    o = ctypes.c_ubyte(0)
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(o))
    return hr, bool(o.value)


def main():
    RoInitialize(1)
    h = ctypes.c_void_p()
    WindowsCreateString(CLASS, len(CLASS), ctypes.byref(h))
    iid = ctypes.create_string_buffer(IID_FACTORY, 16)
    fac = ctypes.c_void_p()
    hr = RoGetActivationFactory(h, ctypes.cast(iid, ctypes.c_void_p), ctypes.byref(fac))
    WindowsDeleteString(h)
    if hr < 0:
        print(f"激活失败 0x{hr & 0xffffffff:08x}"); return 1

    hr, mgr = call_out(fac.value, 6)
    if hr < 0 or not mgr:
        print(f"取实例失败 0x{hr & 0xffffffff:08x}"); return 1

    hr, vec = call_out(mgr, 6)
    print(f"IVector<AIComponent> = 0x{vec:016x}  (hr=0x{hr & 0xffffffff:08x})")
    if hr < 0 or not vec:
        return 1
    print(f"类名: {cname(vec)}")

    hr, n = call_size(vec, 7)
    print(f"\nget_Size -> hr=0x{hr & 0xffffffff:08x}  组件数 = {n}\n")

    if hr < 0:
        return 1

    for i in range(n):
        hr, item = call_out(vec, 6, i)
        if hr < 0 or not item:
            print(f"[{i}] GetAt 失败 0x{hr & 0xffffffff:08x}")
            continue
        print(f"[{i}] 0x{item:016x}  {cname(item)}")
        # 该组件对象 vtable
        for s in range(6, 16):
            try:
                vt = ctypes.cast(item, ctypes.POINTER(ctypes.c_void_p))[0]
                addr = ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))[s]
                print(f"      slot[{s}] = 0x{addr:016x}")
            except Exception:
                break
        # 试 HSTRING 属性
        for s in (6, 7, 8, 9, 10):
            try:
                hr2, v = hstring_out(item, s)
                if hr2 >= 0 and v:
                    print(f"      HSTRING(slot {s}) = {v!r}")
            except Exception:
                pass
        # 试 bool 属性
        for s in (6, 7, 8, 9, 10):
            try:
                hr2, v = bool_out(item, s)
                if hr2 >= 0:
                    print(f"      BOOL(slot {s}) = {v}")
            except Exception:
                pass
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
