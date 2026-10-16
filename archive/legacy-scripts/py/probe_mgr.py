#!/usr/bin/env python3
"""probe_mgr.py - brute-force the AIComponentManager vtable slots.

Goal: find out whether get_Size==0 means "system has no components" or
      "we are calling the wrong slot / need a different construction".
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
GetRaw = _b("WindowsGetStringRawBuffer", ctypes.c_wchar_p,
            [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)])
RoInitialize = _b("RoInitialize", ctypes.c_long, [ctypes.c_int])

CLASS = "Windows.AI.Management.Internal.AIComponentManager"
IID_FACTORY = bytes.fromhex("3500000000000000c000000000000046")


def sl(ptr, n):
    vt = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0]
    return ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))[n]


def clsname(ptr):
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(sl(ptr, 4))
    h = ctypes.c_void_p()
    if fn(ctypes.c_void_p(ptr), ctypes.byref(h)) < 0 or not h.value:
        return "?"
    ln = ctypes.c_uint(0)
    s = GetRaw(ctypes.c_void_p(h.value), ctypes.byref(ln))
    WindowsDeleteString(h)
    return s


def call_0(ptr, n):
    """try f(this) -> hr ; some getters take no out-param"""
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(sl(ptr, n))
    return fn(ctypes.c_void_p(ptr))


def call_ptr(ptr, n):
    """try f(this, void** out)"""
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(sl(ptr, n))
    o = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(o))
    return hr, (o.value or 0)


def call_u32(ptr, n):
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_uint32))(sl(ptr, n))
    o = ctypes.c_uint32(0)
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(o))
    return hr, o.value


def call_bool(ptr, n):
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_ubyte))(sl(ptr, n))
    o = ctypes.c_ubyte(0)
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(o))
    return hr, o.value


def call_uint32_in(ptr, n, v):
    """f(this, uint32) -> hr"""
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.c_uint32)(sl(ptr, n))
    return fn(ctypes.c_void_p(ptr), ctypes.c_uint32(v))


def main():
    RoInitialize(1)
    h = ctypes.c_void_p()
    WindowsCreateString(CLASS, len(CLASS), ctypes.byref(h))
    iid = ctypes.create_string_buffer(IID_FACTORY, 16)
    fac = ctypes.c_void_p()
    hr = RoGetActivationFactory(h, ctypes.cast(iid, ctypes.c_void_p), ctypes.byref(fac))
    WindowsDeleteString(h)
    print(f"ActivationFactory hr=0x{hr & 0xffffffff:08x}  ptr=0x{fac.value or 0:x}")
    if hr < 0:
        return 1

    print(f"\nfactory class: {clsname(fac.value)}")
    print("factory vtable 6..14:")
    for s in range(6, 15):
        a = sl(fac.value, s)
        print(f"   slot[{s}] = 0x{a:x}")

    print("\n--- try ActivateInstance (factory slot 6, no args -> IInspectable*) ---")
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(sl(fac.value, 6))
    o = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(fac.value), ctypes.byref(o))
    print(f"   hr=0x{hr & 0xffffffff:08x}  instance=0x{o.value or 0:x}")
    if hr < 0 or not o.value:
        return 1
    mgr = o.value
    print(f"   class: {clsname(mgr)}")

    print("\n--- manager vtable scan (method 6..24) ---")
    vt = ctypes.cast(mgr, ctypes.POINTER(ctypes.c_void_p))[0]
    for s in range(6, 25):
        addr = ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))[s]
        line = f"  slot[{s:2}] 0x{addr:016x}"
        # f(this) -> hr
        try:
            hr0 = call_0(mgr, s)
            line += f"   [0-arg hr=0x{hr0 & 0xffffffff:08x}]"
        except Exception:
            pass
        print(line)

    print("\n--- manager: try out-param getters (6..20) ---")
    for s in range(6, 21):
        try:
            hr, p = call_ptr(mgr, s)
            if hr >= 0 and p:
                cn = clsname(p)
                print(f"  slot[{s:2}] -> ptr 0x{p:x}  class={cn}")
                # if it looks like a vector, get its size
                for vs in range(6, 12):
                    try:
                        hrv, n = call_u32(p, vs)
                        if hrv >= 0 and 0 < n < 100000:
                            print(f"        vector? slot[{vs}] size={n}")
                    except Exception:
                        pass
        except Exception:
            pass

    print("\n--- manager: try u32 getters (6..20) ---")
    for s in range(6, 21):
        try:
            hr, v = call_u32(mgr, s)
            if hr >= 0:
                print(f"  slot[{s:2}] u32 = {v}")
        except Exception:
            pass

    print("\n--- manager: try bool getters (6..20) ---")
    for s in range(6, 21):
        try:
            hr, v = call_bool(mgr, s)
            if hr >= 0:
                print(f"  slot[{s:2}] bool = {v}")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
