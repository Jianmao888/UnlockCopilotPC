#!/usr/bin/env python3
"""
ai_manager_probe.py — 调用 AIComponentManager 的 slot[6]，检查返回对象并枚举

slot[6] 在探测中返回 S_OK + 非空指针，疑似 GetInstalledComponents() 之类。
本脚本：
  1. 激活 factory，调 slot[6] 拿到返回对象
  2. 读该对象的运行时类名（GetRuntimeClassName）确认类型
  3. 若像 IVector<T>，尝试 get_Size / GetAt 枚举
所有调用都在子进程里做，崩溃被隔离。
"""
import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

combase = ctypes.WinDLL("combase.dll")


def _bind(name, restype, argtypes):
    f = getattr(combase, name)
    f.restype = restype
    f.argtypes = argtypes
    return f


RoGetActivationFactory = _bind("RoGetActivationFactory", ctypes.c_long,
                               [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)])
WindowsCreateString = _bind("WindowsCreateString", ctypes.c_long,
                            [wintypes.LPCWSTR, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p)])
WindowsDeleteString = _bind("WindowsDeleteString", ctypes.c_long, [ctypes.c_void_p])
WindowsGetStringRawBuffer = _bind("WindowsGetStringRawBuffer", ctypes.c_wchar_p,
                                  [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)])
RoInitialize = _bind("RoInitialize", ctypes.c_long, [ctypes.c_int])

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


def slot(ptr, n):
    vt = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0]
    return ctypes.cast(vt, ctypes.POINTER(ctypes.c_void_p))[n]


def class_name(ptr):
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(slot(ptr, 4))
    h = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(h))
    if hr < 0 or not h.value:
        return f"<失败 0x{hr & 0xffffffff:08x}>"
    ln = ctypes.c_uint(0)
    s = WindowsGetStringRawBuffer(h, ctypes.byref(ln))
    WindowsDeleteString(h)
    return s


def call0_out(ptr, n):
    """调用 f(this, void** out) 形式的方法"""
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p))(slot(ptr, n))
    o = ctypes.c_void_p()
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(o))
    return hr, (o.value or 0)


def call_size(ptr, n):
    """调用 f(this, UINT32* out)"""
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_uint32))(slot(ptr, n))
    o = ctypes.c_uint32(0)
    hr = fn(ctypes.c_void_p(ptr), ctypes.byref(o))
    return hr, o.value


def do_inspect():
    f = get_factory()
    print(f"factory 类名 = {class_name(f)}")
    hr, obj = call0_out(f, 6)
    print(f"\nslot[6](factory) -> HRESULT 0x{hr & 0xffffffff:08x}, obj=0x{obj:016x}")
    if hr < 0 or obj == 0:
        return
    print(f"返回对象类名 = {class_name(obj)}")
    print("\n--- 该对象 vtable 前 20 槽 ---")
    for i in range(20):
        print(f"  [{i:2}] = 0x{slot(obj, i):016x}")
    print("\n--- 尝试 get_Size (IVector 通常是 slot 7) ---")
    for n in (6, 7, 8):
        try:
            hr, sz = call_size(obj, n)
            print(f"  slot[{n}] as get_Size -> HRESULT 0x{hr & 0xffffffff:08x}, size={sz}")
        except Exception as e:
            print(f"  slot[{n}] 失败: {str(e)[:80]}")


def do_examine(obj):
    print(f"对象类名 = {class_name(obj)}")
    for n in (6, 7, 8):
        try:
            hr, sz = call_size(obj, n)
            print(f"  slot[{n}] get_Size -> 0x{hr & 0xffffffff:08x} size={sz}")
        except Exception as e:
            print(f"  slot[{n}] 失败 {str(e)[:60]}")


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    if a == "inspect":
        do_inspect()
    elif a == "examine":
        do_examine(int(sys.argv[2], 0))
