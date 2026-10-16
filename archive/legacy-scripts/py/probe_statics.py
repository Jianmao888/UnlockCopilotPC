#!/usr/bin/env python3
"""probe_statics.py - call the AIComponentManager activation-factory STATIC methods.

WinRT activation factory layout:
  0-2 IUnknown | 3-5 IInspectable | 6 ActivateInstance | 7.. <Class>Statics methods
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


def sl(p, n):
    vt = ctypes.cast(p, ctypes.POINTER(ctypes.c_void_p))[0]
    return ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))[n]


def clsname(p):
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(sl(p, 4))
    h = ctypes.c_void_p()
    if fn(ctypes.c_void_p(p), ctypes.byref(h)) < 0 or not h.value:
        return "?"
    ln = ctypes.c_uint(0)
    s = GetRaw(ctypes.c_void_p(h.value), ctypes.byref(ln))
    WindowsDeleteString(h)
    return s


def hs(s):
    h = ctypes.c_void_p()
    WindowsCreateString(s, len(s), ctypes.byref(h))
    return h


def main():
    RoInitialize(1)
    h = hs(CLASS)
    iid = ctypes.create_string_buffer(IID_FACTORY, 16)
    fac = ctypes.c_void_p()
    hr = RoGetActivationFactory(h, ctypes.cast(iid, ctypes.c_void_p), ctypes.byref(fac))
    WindowsDeleteString(h)
    print(f"factory 0x{fac.value:x}  hr=0x{hr & 0xffffffff:08x}", flush=True)
    F = fac.value

    print("\n=== A. static slot 7..20 : f(this, void** out) ===", flush=True)
    for s in range(7, 21):
        try:
            fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                    ctypes.POINTER(ctypes.c_void_p))(sl(F, s))
            o = ctypes.c_void_p()
            r = fn(ctypes.c_void_p(F), ctypes.byref(o))
            tag = ""
            if r >= 0 and o.value:
                tag = f" -> 0x{o.value:x}  class={clsname(o.value)}"
            print(f"  slot[{s:2}] hr=0x{r & 0xffffffff:08x}{tag}", flush=True)
        except Exception as e:
            print(f"  slot[{s:2}] exc {e}", flush=True)

    print("\n=== B. static slot 7..20 : f(this, HSTRING name, void** out) ===", flush=True)
    for s in range(7, 21):
        for name in ("Windows.Workload.ContentExtraction.365.amd64",):
            try:
                hn = hs(name)
                fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.POINTER(ctypes.c_void_p))(sl(F, s))
                o = ctypes.c_void_p()
                r = fn(ctypes.c_void_p(F), hn, ctypes.byref(o))
                WindowsDeleteString(hn)
                if r >= 0:
                    tag = f" -> 0x{o.value:x} class={clsname(o.value)}" if o.value else ""
                    print(f"  slot[{s:2}] (name) hr=0x{r & 0xffffffff:08x}{tag}", flush=True)
            except Exception:
                pass

    print("\n=== C. static slot 7..20 : f(this, void** out, void** out2) ===", flush=True)
    for s in range(7, 21):
        try:
            fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                    ctypes.POINTER(ctypes.c_void_p),
                                    ctypes.POINTER(ctypes.c_void_p))(sl(F, s))
            a = ctypes.c_void_p(); b = ctypes.c_void_p()
            r = fn(ctypes.c_void_p(F), ctypes.byref(a), ctypes.byref(b))
            if r >= 0:
                print(f"  slot[{s:2}] hr=0x{r & 0xffffffff:08x} a=0x{a.value or 0:x} b=0x{b.value or 0:x}", flush=True)
        except Exception:
            pass

    print("\n=== D. if a slot returned a vector, read its size ===", flush=True)
    for s in range(7, 21):
        try:
            fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                    ctypes.POINTER(ctypes.c_void_p))(sl(F, s))
            o = ctypes.c_void_p()
            r = fn(ctypes.c_void_p(F), ctypes.byref(o))
            if r < 0 or not o.value:
                continue
            for vs in range(6, 12):
                try:
                    vf = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.c_uint32))(sl(o.value, vs))
                    n = ctypes.c_uint32(0)
                    if vf(ctypes.c_void_p(o.value), ctypes.byref(n)) >= 0 and 0 < n.value < 10000:
                        print(f"  slot[{s}] -> obj slot[{vs}] size={n.value}   class={clsname(o.value)}", flush=True)
                except Exception:
                    pass
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
