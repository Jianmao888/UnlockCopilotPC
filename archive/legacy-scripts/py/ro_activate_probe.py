#!/usr/bin/env python3
"""
ro_activate_probe.py — 用 RoGetActivationFactory 逐个测试 Windows AI 运行时类是否可激活

Windows AI 的类型不在 WinMetadata 里，所以 PowerShell 无法投影，
但如果类已注册（AIFabric 包注册了它们），RoGetActivationFactory 按名字就能拿到 factory。
"""
import ctypes
from ctypes import wintypes

combase = ctypes.WinDLL("combase.dll")

RoGetActivationFactory = combase.RoGetActivationFactory
RoGetActivationFactory.restype = ctypes.c_long
RoGetActivationFactory.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.POINTER(ctypes.c_void_p)]

WindowsCreateString = combase.WindowsCreateString
WindowsCreateString.restype = ctypes.c_long
WindowsCreateString.argtypes = [wintypes.LPCWSTR, wintypes.UINT,
                                ctypes.POINTER(ctypes.c_void_p)]

WindowsDeleteString = combase.WindowsDeleteString
WindowsDeleteString.restype = ctypes.c_long
WindowsDeleteString.argtypes = [ctypes.c_void_p]

RoInitialize = combase.RoInitialize
RoInitialize.restype = ctypes.c_long
RoInitialize.argtypes = [ctypes.c_int]

# 先初始化 WinRT apartment（否则 RoGetActivationFactory 返回 0x800401f0 CO_E_NOTINITIALIZED）
hr_init = RoInitialize(1)   # RO_INIT_MULTITHREADED
print(f"RoInitialize -> 0x{hr_init & 0xffffffff:08x} "
      f"({'OK' if hr_init >= 0 else 'HRESULT 非 0（可能已初始化，可忽略）'})\n")

IID_IActivationFactory = bytes.fromhex("3500000000000000c000000000000046")
buf = ctypes.create_string_buffer(IID_IActivationFactory, 16)


def activate(class_name):
    h = ctypes.c_void_p()
    hr = WindowsCreateString(class_name, len(class_name), ctypes.byref(h))
    if hr < 0:
        return hr, None
    out = ctypes.c_void_p()
    hr = RoGetActivationFactory(h, ctypes.cast(buf, ctypes.c_void_p), ctypes.byref(out))
    WindowsDeleteString(h)
    return hr, (out.value if hr >= 0 else None)


CANDIDATES = [
    # 能力 / 就绪
    "Microsoft.Windows.AI.AICapabilities",
    "Microsoft.Windows.AI.AIFeatureReadyResult",
    # 视觉 / OCR（Click to Do 需要）
    "Microsoft.Windows.Vision.TextRecognizer",
    "Microsoft.Windows.Vision.ScreenRegionDetector",
    "Microsoft.Windows.AI.Imaging.TextRecognizer",
    "Microsoft.Windows.AI.Imaging.ScreenRegionDetector",
    "Microsoft.Windows.AI.Imaging.ImageScaler",
    "Microsoft.Windows.AI.Imaging.ImageObjectExtractor",
    # 语言模型
    "Microsoft.Windows.AI.Text.LanguageModel",
    # 语义搜索（自然语言搜索需要）
    "Microsoft.Windows.SemanticSearch.SemanticTextEmbeddingsCreator",
    "Microsoft.Windows.SemanticSearch.QueryProcessor",
    # 工作负载 / 组件管理
    "Microsoft.Windows.Workloads.WorkloadManager",
    "Windows.AI.Management.Internal.AIComponentManager",
    "Microsoft.Windows.AI.ContentSafety.ImageContentModeration",
    # 内部会话类
    "Microsoft.Windows.Internal.Vision.TextRecognizerSession",
    "Microsoft.Windows.Internal.SemanticSearch.SemanticTextSession",
    "Microsoft.Windows.Private.Workloads.SessionManager.SessionManager",
    "Microsoft.Windows.Internal.SessionMock.SessionMock",
]


def main():
    ok, fail = [], []
    for c in CANDIDATES:
        hr, ptr = activate(c)
        if hr >= 0:
            ok.append((c, hr))
            print(f"  OK    0x{hr & 0xffffffff:08x}  {c}")
        else:
            fail.append((c, hr))
            print(f"  FAIL  0x{hr & 0xffffffff:08x}  {c}")
    print(f"\n可激活 {len(ok)} / 共 {len(CANDIDATES)}")
    return 0


if __name__ == "__main__":
    main()
