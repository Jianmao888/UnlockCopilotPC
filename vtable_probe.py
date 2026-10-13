#!/usr/bin/env python3
"""
vtable_probe.py — 探测 Windows.AI.Management.Internal.AIComponentManager 的方法槽

背景：
  该类是机器级注册的 WinRT 类，RoGetActivationFactory 能成功拿到 factory。
  但没有公开 winmd 给出静态接口的 IID，所以无法直接 QueryInterface。
  办法：读 factory 的 vtable，逐个尝试调用槽位（每个槽位在独立子进程里试，崩了不影响）。

vtable 布局（x64, 标准 WinRT）：
  0 QueryInterface  1 AddRef  2 Release
  3 GetIids         4 GetRuntimeClassName  5 GetTrustLevel
  6+ 该类的静态方法

用法：
  python vtable_probe.py dump            # 只打印 vtable 指针
  python vtable_probe.py try <slot>      # 在子进程里试调用某个槽位
  python vtable_probe.py scan            # 扫描 6..24
"""
import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

combase = ctypes.WinDLL("combase.dll")
RoGetActivationFactory = combase.RoGetActivationFactory
RoGetActivationFactory.restype = ctypes.c_long
RoGetActivationFactory.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.POINTER(ctypes.c_void_p)]
WindowsCreateString = combase.WindowsCreateString
WindowsCreateString.restype = ctypes.c_long
WindowsCreateString.argtypes = [wintypes.LPCWSTR, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p)]
WindowsDeleteString = combase.WindowsDeleteString
WindowsDeleteString.restype = ctypes.c_long
WindowsDeleteString.argtypes = [ctypes.c_void_p]
RoInitialize = combase.RoInitialize
RoInitialize.restype = ctypes.c_long
RoInitialize.argtypes = [ctypes.c_int]

CLASS = "Windows.AI.Management.Internal.AIComponentManager"
IID_FACTORY = bytes.fromhex("3500000000000000c000000000000046")


def get_factory():
    RoInitialize(1)
    h = ctypes.c_void_p()
    WindowsCreateString(CLASS, len(CLASS), ctypes.byref(h))
    iid = ctypes.create_string_buffer(IID_FACTORY, 16)
    out = ctypes.c_void_p()
    hr = RoGetActivationFactory(h, ctypes.cast(iid, ctypes.c_void_p), ctypes.byref(out))
    WindowsDeleteString(h)
    if hr < 0:
        raise RuntimeError(f"激活失败 0x{hr & 0xffffffff:08x}")
    return out.value


def cmd_dump():
    f = get_factory()
    print(f"factory = 0x{f:016x}")
    vt = ctypes.cast(f, ctypes.POINTER(ctypes.c_void_p))[0]
    print(f"vtable  = 0x{vt:016x}")
    slots = ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))
    for i in range(0, 26):
        print(f"  slot[{i:2}] = 0x{slots[i]:016x}")

    # 调 GetRuntimeClassName（slot 4）验证布局
    GetRuntimeClassName = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                             ctypes.POINTER(ctypes.c_void_p))(slots[4])
    name = ctypes.c_void_p()
    hr = GetRuntimeClassName(f, ctypes.byref(name))
    print(f"\nGetRuntimeClassName -> 0x{hr & 0xffffffff:08x}")
    if hr >= 0 and name.value:
        buf = ctypes.create_unicode_buffer(256)
        ln = ctypes.c_uint(0)
        WindowsGetStringRawBuffer = combase.WindowsGetStringRawBuffer
        WindowsGetStringRawBuffer.restype = ctypes.c_wchar_p
        WindowsGetStringRawBuffer.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
        s = WindowsGetStringRawBuffer(name, ctypes.byref(ln))
        print(f"  运行时类名 = {s}")


def cmd_try(slot):
    """在子进程里试调一个槽位：假设签名是 HRESULT f(this, void** out)"""
    f = get_factory()
    vt = ctypes.cast(f, ctypes.POINTER(ctypes.c_void_p))[0]
    slots = ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(slots[slot])
    out = ctypes.c_void_p()
    hr = fn(f, ctypes.byref(out))
    print(f"slot[{slot}] -> HRESULT 0x{hr & 0xffffffff:08x}  out=0x{(out.value or 0):016x}")
    return 0


def cmd_scan(lo=6, hi=24):
    print(f"扫描槽位 {lo}..{hi}（每个在独立子进程里试，崩溃会被隔离）")
    for s in range(lo, hi + 1):
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "try", str(s)],
                           capture_output=True, text=True, timeout=60)
        line = (r.stdout or "").strip().splitlines()
        msg = line[-1] if line else (r.stderr or "").strip()[-160:]
        if r.returncode != 0:
            msg = f"崩溃/退出码 {r.returncode}  {msg[:120]}"
        print(f"  {msg}")


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "dump"
    if a == "dump":
        cmd_dump()
    elif a == "try":
        cmd_try(int(sys.argv[2]))
    elif a == "scan":
        cmd_scan(*(int(x) for x in sys.argv[2:4]) if len(sys.argv) > 2 else ())
