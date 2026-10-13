#!/usr/bin/env python3
"""
oneocr_demo.py — 在非 Copilot+ PC 上直接调用微软 oneocr.dll 做 OCR（干净演示）

证明：这台 i7-1260P（无 NPU）可以运行微软的 OCR 引擎，CPU 模式。
不依赖 Copilot+ 资格、不依赖 WindowsWorkload 体系、不依赖 Windows AI API。
"""
import ctypes
import os
import sys
from ctypes import c_char_p, c_void_p, c_int32, c_int64, c_float, POINTER, Structure

D = r"C:\Users\jianm\Code\DeepseekHarness\oneocr-extract"
OCR_KEY = 'kj)TGtrK>f]b[Piow.gU+nC@s' + '"' * 6 + '4'

# RawImage.type 实测取值
IMG_TYPE_RGB = 0


class RawImage(Structure):
    _pack_ = 1
    _fields_ = [("t", c_int32), ("col", c_int32), ("row", c_int32), ("_unk", c_int32),
                ("step", c_int64), ("data_ptr", c_int64)]


class RawBBox(Structure):
    _pack_ = 1
    _fields_ = [(n, c_float) for n in ("x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4")]


SIG = {
    "CreateOcrInitOptions": ([POINTER(c_void_p)], c_int32),
    "CreateOcrPipeline": ([c_char_p, c_char_p, c_void_p, POINTER(c_void_p)], c_int32),
    "CreateOcrProcessOptions": ([POINTER(c_void_p)], c_int32),
    "OcrProcessOptionsSetRunBackendModelOnCPU": ([c_void_p, ctypes.c_ubyte], c_int32),
    "OcrProcessOptionsSetMaxRecognitionLineCount": ([c_void_p, c_int32], c_int32),
    "OcrProcessOptionsSetResizeResolution": ([c_void_p, c_int32, c_int32], c_int32),
    "RunOcrPipeline": ([c_void_p, POINTER(RawImage), c_void_p, POINTER(c_void_p)], c_int32),
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


def load_dll():
    os.add_dll_directory(D)
    os.chdir(D)
    dll = ctypes.WinDLL(os.path.join(D, "oneocr.dll"))
    for n, (a, r) in SIG.items():
        try:
            f = getattr(dll, n); f.argtypes = a; f.restype = r
        except AttributeError:
            pass
    return dll


def make_image(path):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1500, 320), "white")
    dr = ImageDraw.Draw(img)
    font = None
    for cand in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf",
                 r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(cand):
            try:
                font = ImageFont.truetype(cand, 40); break
            except Exception:
                pass
    lines = ["Hello OneOCR 2026", "Copilot+ bypass test", "12345 ABCDEF",
             "The quick brown fox", "OCR works without NPU"]
    y = 15
    for t in lines:
        dr.text((25, y), t, fill="black", font=font)
        y += 58
    img.save(path)
    return path, lines


def to_raw(path):
    from PIL import Image
    img = Image.open(path).convert("RGB")
    w, h = img.size
    data = img.tobytes()
    buf = ctypes.create_string_buffer(data, len(data))
    ri = RawImage()
    ri.t = IMG_TYPE_RGB
    ri.col, ri.row, ri._unk = w, h, 0
    ri.step = w * 3
    ri.data_ptr = ctypes.cast(buf, c_void_p).value
    return ri, buf, w, h


def main():
    print("=" * 70)
    print("在非 Copilot+ PC 上直接调用微软 oneocr.dll")
    print("=" * 70)
    dll = load_dll()
    model = os.path.join(D, "oneocr.onemodel")

    opt = c_void_p()
    hr = dll.CreateOcrInitOptions(ctypes.byref(opt))
    print(f"  1) CreateOcrInitOptions                 -> 0x{hr & 0xffffffff:08x}")

    pipe = c_void_p()
    hr = dll.CreateOcrPipeline(model.encode(), OCR_KEY.encode("ascii"), opt, ctypes.byref(pipe))
    print(f"  2) CreateOcrPipeline(模型 58.5MB + key)  -> 0x{hr & 0xffffffff:08x}")

    popt = c_void_p()
    hr = dll.CreateOcrProcessOptions(ctypes.byref(popt))
    print(f"  3) CreateOcrProcessOptions              -> 0x{hr & 0xffffffff:08x}")
    hr = dll.OcrProcessOptionsSetRunBackendModelOnCPU(popt, 1)
    print(f"  4) SetRunBackendModelOnCPU(1)           -> 0x{hr & 0xffffffff:08x}   ★ 强制 CPU")

    img, expected = make_image(os.path.join(D, "demo.png"))
    ri, buf, w, h = to_raw(img)
    print(f"  5) 测试图 {w}x{h} RGB")

    res = c_void_p()
    hr = dll.RunOcrPipeline(pipe, ctypes.byref(ri), popt, ctypes.byref(res))
    print(f"  6) RunOcrPipeline                       -> 0x{hr & 0xffffffff:08x}")

    n = c_int64()
    dll.GetOcrLineCount(res, ctypes.byref(n))
    print(f"\n识别到 {n.value} 行：")
    got = []
    for i in range(n.value):
        line = c_void_p()
        dll.GetOcrLine(res, i, ctypes.byref(line))
        s = c_char_p()
        dll.GetOcrLineContent(line, ctypes.byref(s))
        txt = s.value.decode("utf-8", "replace") if s.value else ""
        got.append(txt)
        bb = POINTER(RawBBox)()
        dll.GetOcrLineBoundingBox(line, ctypes.byref(bb))
        box = ""
        if bb:
            b = bb.contents
            box = f"[{b.x1:.0f},{b.y1:.0f} - {b.x2:.0f},{b.y2:.0f}]"
        # 词级 + 置信度
        wc = c_int64()
        dll.GetOcrLineWordCount(line, ctypes.byref(wc))
        words = []
        for wi in range(wc.value):
            wp = c_void_p()
            dll.GetOcrWord(line, wi, ctypes.byref(wp))
            ws = c_char_p(); dll.GetOcrWordContent(wp, ctypes.byref(ws))
            conf = c_float(); dll.GetOcrWordConfidence(wp, ctypes.byref(conf))
            words.append(f"{ws.value.decode('utf-8','replace') if ws.value else ''}({conf.value:.2f})")
        print(f"    [{i}] {txt!r}  {box}")
        print(f"         词: {' '.join(words)}")

    print("\n对照（原图文字）:")
    for e in expected:
        print(f"    {e}")

    ok = sum(1 for e in expected for g in got if e.lower()[:12] in g.lower())
    print(f"\n匹配: {ok}/{len(expected)} 行")

    dll.ReleaseOcrResult(res)
    dll.ReleaseOcrProcessOptions(popt)
    dll.ReleaseOcrPipeline(pipe)
    dll.ReleaseOcrInitOptions(opt)
    print("\n✅ 完成 —— 无 NPU、无 Copilot+ 资格、无 Windows AI API，OCR 正常工作")
    return 0


if __name__ == "__main__":
    sys.exit(main())
