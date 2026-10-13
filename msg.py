import ctypes, ctypes.wintypes as w
for code in (0x80073D3B, 0x3D3B):
    buf = ctypes.c_wchar_p()
    n = ctypes.windll.kernel32.FormatMessageW(0x00001000, None, code, 0, ctypes.byref(buf), 0, None)
    if n: print(f"  0x{code:08X}: " + buf.value.strip())
    else: print(f"  0x{code:08X}: (no message, err={ctypes.GetLastError()})")
