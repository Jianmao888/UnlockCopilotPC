#!/usr/bin/env python3
"""
oneocr_test.py — 直接在非 Copilot+ PC 上调用 oneocr.dll 做 OCR

来源包：WindowsWorkload.TextRecognition.365.1（旧代，自包含，纯 CPU）
  oneocr.dll       42.7 MB   OCR 引擎
  oneocr.onemodel  58.5 MB   模型
  onnxruntime.dll  14.0 MB   标准 ONNX Runtime

FFI 签名来自 wangfu91/oneocr-rs 的 src/ffi.rs
"""
import ctypes
import os
import sys
from ctypes import c_char_p, c_void_p, c_int32, c_int64, c_float, POINTER, Structure

D = r"C:\Users\jianm\Code\DeepseekHarness\oneocr-extract"

# 来自 wangfu91/oneocr-rs 的 src/lib.rs:
#   pub(crate) const ONE_OCR_MODEL_KEY: &str = r#"kj)TGtrK>f]b[Piow.gU+nC@s""""""4"#;
OCR_KEY = 'kj)TGtrK>f]b[Piow.gU+nC@s' + '"' * 6 + '4'


class RawImage(Structure):
    _pack_ = 1
    _fields_ = [
        ("t", c_int32), ("col", c_int32), ("row", c_int32), ("_unk", c_int32),
        ("step", c_int64), ("data_ptr", c_int64),
    ]


class RawBBox(Structure):
    _pack_ = 1
    _fields_ = [(n, c_float) for n in ("x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4")]


def load():
    os.add_dll_directory(D)
    os.chdir(D)
    dll = ctypes.WinDLL(os.path.join(D, "oneocr.dll"))
    sig = {
        "CreateOcrInitOptions": ([POINTER(c_void_p)], c_int32),
        "OcrInitOptionsSetUseModelDelayLoad": ([c_void_p, ctypes.c_ubyte], c_int32),
        "CreateOcrPipeline": ([c_char_p, c_char_p, c_void_p, POINTER(c_void_p)], c_int32),
        "CreateOcrProcessOptions": ([POINTER(c_void_p)], c_int32),
        "OcrProcessOptionsSetRunBackendModelOnCPU": ([c_void_p, ctypes.c_ubyte], c_int32),
        "OcrProcessOptionsGetRunBackendModelOnCPU": ([c_void_p, POINTER(ctypes.c_ubyte)], c_int32),
        "OcrProcessOptionsSetMaxRecognitionLineCount": ([c_void_p, c_int32], c_int32),
        "OcrProcessOptionsSetResizeResolution": ([c_void_p, c_int32, c_int32], c_int32),
        "RunOcrPipeline": ([c_void_p, POINTER(RawImage), c_void_p, POINTER(c_void_p)], c_int32),
        "GetImageAngle": ([c_void_p, POINTER(c_float)], c_int32),
        "GetOcrLineCount": ([c_void_p, POINTER(c_int64)], c_int32),
        "GetOcrLine": ([c_void_p, c_int64, POINTER(c_void_p)], c_int32),
        "GetOcrLineContent": ([c_void_p, POINTER(c_char_p)], c_int32),
        "GetOcrLineBoundingBox": ([c_void_p, POINTER(POINTER(RawBBox))], c_int32),
        "GetOcrLineWordCount": ([c_void_p, POINTER(c_int64)], c_int32),
        "GetOcrWord": ([c_void_p, c_int64, POINTER(c_void_p)], c_int32),
        "GetOcrWordContent": ([c_void_p, POINTER(c_char_p)], c_int32),
        "GetOcrWordConfidence": ([c_void_p, POINTER(c_float)], c_int32),
        "ReleaseOcrResult": ([c_void_p], None),
        "ReleaseOcrInitOptions": ([c_void_p], None),
        "ReleaseOcrPipeline": ([c_void_p], None),
        "ReleaseOcrProcessOptions": ([c_void_p], None),
    }
    for n, (a, r) in sig.items():
        try:
            f = getattr(dll, n)
            f.argtypes = a
            f.restype = r
        except AttributeError:
            print(f"  (缺少导出 {n})")
    return dll


def make_test_image(path):
    """生成一张带黑字的白图"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  需要 Pillow"); return None
    img = Image.new("RGB", (640, 200), "white")
    dr = ImageDraw.Draw(img)
    dr.text((20, 40), "Hello OneOCR 2026", fill="black")
    dr.text((20, 90), "Copilot+ bypass test", fill="black")
    dr.text((20, 140), "12345 ABCDEF", fill="black")
    img.save(path)
    return path


def to_rawimage(path):
    from PIL import Image
    img = Image.open(path).convert("RGB")
    w, h = img.size
    data = img.tobytes()
    buf = ctypes.create_string_buffer(data, len(data))
    ri = RawImage()
    ri.t = 3          # 猜测: 3 = RGB（见注释，需实测）
    ri.col = w
    ri.row = h
    ri._unk = 0
    ri.step = w * 3
    ri.data_ptr = ctypes.cast(buf, c_void_p).value
    return ri, buf


def main():
    dll = load()
    model = os.path.join(D, "oneocr.onemodel")
    print(f"模型: {model}  ({os.path.getsize(model)/1e6:.1f} MB)\n")

    # 1) init options
    opt = c_void_p()
    hr = dll.CreateOcrInitOptions(ctypes.byref(opt))
    print(f"CreateOcrInitOptions      -> 0x{hr & 0xffffffff:08x}  opt={opt.value}")

    # 2) pipeline（用真 key）
    pipe = c_void_p()
    kb = OCR_KEY.encode("ascii")
    print(f"  key 长度 = {len(kb)} 字节: {OCR_KEY!r}")
    hr = dll.CreateOcrPipeline(model.encode(), kb, opt, ctypes.byref(pipe))
    print(f"CreateOcrPipeline(key=REAL) -> 0x{hr & 0xffffffff:08x}  pipeline={pipe.value}")
    if hr != 0 or not pipe.value:
        print("\n  key 仍不正确。")
        return 1

    # 3) process options
    popt = c_void_p()
    hr = dll.CreateOcrProcessOptions(ctypes.byref(popt))
    print(f"CreateOcrProcessOptions   -> 0x{hr & 0xffffffff:08x}  opt={popt.value}")
    if popt.value:
        cpu = ctypes.c_ubyte(0)
        hr2 = dll.OcrProcessOptionsGetRunBackendModelOnCPU(popt, ctypes.byref(cpu))
        print(f"  GetRunBackendModelOnCPU -> 0x{hr2 & 0xffffffff:08x}  value={cpu.value}")
        hr3 = dll.OcrProcessOptionsSetRunBackendModelOnCPU(popt, 1)
        print(f"  SetRunBackendModelOnCPU(1) -> 0x{hr3 & 0xffffffff:08x}")

    # 4) 图像
    img = os.path.join(D, "test.png")
    if not make_test_image(img):
        return 1
    ri, buf = to_rawimage(img)
    print(f"\n图像: {ri.col}x{ri.row} step={ri.step} type={ri.t}")

    # 5) 跑
    res = c_void_p()
    for t in (3, 0, 1, 2, 4):
        ri.t = t
        res = c_void_p()
        hr = dll.RunOcrPipeline(pipe, ctypes.byref(ri), popt, ctypes.byref(res))
        print(f"RunOcrPipeline(type={t})   -> 0x{hr & 0xffffffff:08x}  result={res.value}")
        if hr == 0 and res.value:
            break

    if res.value:
        ang = c_float()
        dll.GetImageAngle(pipe, ctypes.byref(ang))
        n = c_int64()
        dll.GetOcrLineCount(res, ctypes.byref(n))
        print(f"\n角度={ang.value:.2f}  识别到 {n.value} 行:")
        for i in range(n.value):
            line = c_void_p()
            dll.GetOcrLine(res, i, ctypes.byref(line))
            if not line.value:
                continue
            s = c_char_p()
            dll.GetOcrLineContent(line, ctypes.byref(s))
            txt = s.value.decode("utf-8", "replace") if s.value else ""
            bb = POINTER(RawBBox)()
            dll.GetOcrLineBoundingBox(line, ctypes.byref(bb))
            box = ""
            if bb:
                b = bb.contents
                box = f" [{b.x1:.0f},{b.y1:.0f},{b.x2:.0f},{b.y2:.0f}]"
            wc = c_int64()
            dll.GetOcrLineWordCount(line, ctypes.byref(wc))
            print(f"   [{i}] {txt!r}  词数={wc.value}{box}")
        dll.ReleaseOcrResult(res)

    dll.ReleaseOcrProcessOptions(popt)
    dll.ReleaseOcrPipeline(pipe)
    dll.ReleaseOcrInitOptions(opt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
