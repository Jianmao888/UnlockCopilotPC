#!/usr/bin/env python3
"""
wu_hunt.py — 从 AI 组件二进制中提取所有 GUID，批量作为 WuCategoryId 试探

思路：
  Store 应用的 WuCategoryId 是一个每应用独有的 GUID。
  该 GUID 由微软在发布时分配，公开 Store 页面上拿不到（WindowsWorkload.* 未公开）。
  但它有可能以某种形式硬编码在 AI 组件的二进制/清单里（例如产品注册 ID）。

  本脚本把 AI 相关文件里出现的所有 GUID 全部提取出来，分批塞进
  SyncUpdates 的 FilterAppCategoryIds，看哪一批能返回 UpdateIdentity。

用法：
  python wu_hunt.py                # 提取 + 分批试探
  python wu_hunt.py --list         # 只列出提取到的 GUID
"""

import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wu_probe as wp  # noqa: E402

GUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

TARGET_DIRS = [
    r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe",
    r"C:\Windows\SystemApps\MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy",
]
TARGET_EXTS = (".dll", ".exe", ".json", ".winmd", ".xml")
SINGLE_FILES = [
    r"C:\Windows\System32\AIComponentMgmt.dll",
    r"C:\Windows\System32\WSAIFabricHost.dll",
    r"C:\Windows\System32\Windows.Internal.AI.PlatformCapability.dll",
    r"C:\Windows\System32\Windows.AI.Agents.dll",
]

# 已知的 WU 内置分类（排除它们，避免噪声）
WU_BUILTIN = {
    "0fa1201d-4330-4fa8-8ae9-b877473b6441",  # Security Updates
    "28bc880e-0592-4cbf-8f95-c79b17911d5f",  # Update Rollups
    "cd5ffd1e-e932-4e3a-bf74-18bf0b1bbd83",  # Updates
    "e0789628-ce08-4437-be74-2495b842f43b",  # Definition Updates
    "8c3fcc84-7410-4a95-8b89-a166a0190486",  # Defender
    "a3c2375d-0c8a-42f9-bce0-28333e198407",  # Windows 10
}


def collect_guids():
    """从 AI 组件文件里提取 GUID。返回 {guid: [来源文件]}"""
    hits = {}
    files = list(SINGLE_FILES)
    for d in TARGET_DIRS:
        if not os.path.isdir(d):
            continue
        for root, _dirs, names in os.walk(d):
            # System32 太大，只扫顶层
            if root.rstrip("\\").lower() == r"c:\windows\system32":
                for n in names:
                    if n.lower().endswith(TARGET_EXTS):
                        files.append(os.path.join(root, n))
                _dirs[:] = []
            else:
                for n in names:
                    if n.lower().endswith(TARGET_EXTS):
                        files.append(os.path.join(root, n))

    for f in files:
        try:
            if os.path.getsize(f) > 60 * 1024 * 1024:
                continue
            data = open(f, "rb").read()
        except OSError:
            continue
        text = data.decode("ascii", errors="ignore")
        text += "\x00" + data.decode("utf-16-le", errors="ignore")
        for m in GUID_RE.finditer(text):
            g = m.group(0).lower()
            hits.setdefault(g, set()).add(os.path.basename(f))
    return hits


def main():
    only_list = "--list" in sys.argv
    hits = collect_guids()

    # 过滤掉明显不是分类的
    candidates = {g: v for g, v in hits.items() if g not in WU_BUILTIN}
    print(f"提取到 {len(hits)} 个 GUID，其中候选 {len(candidates)} 个\n")

    for g, srcs in sorted(candidates.items()):
        print(f"  {g}   <- {', '.join(sorted(srcs))[:90]}")

    if only_list:
        return 0

    print("\n" + "=" * 70)
    print("开始分批试探（每批 8 个 GUID）")
    print("判据：响应中出现 WindowsWorkload / TextRecognition / SemanticText 等字样")
    print("=" * 70)

    # 噪声 GUID：全零、WinRT 基础接口
    NOISE = {
        "00000000-0000-0000-0000-000000000000",
        "00000001-0000-0000-c000-000000000046",
        "00000035-0000-0000-c000-000000000046",
        "00000040-0000-0000-c000-000000000046",
    }
    # 标记词
    MARKERS = ["WindowsWorkload", "TextRecognition", "SemanticText",
               "ScrRegDetection", "PSOnnxRuntime", "PhiSilica",
               "ContentExtraction", "ImageSearch", "LanguageModel"]

    guids = sorted(g for g in candidates if g not in NOISE)
    print(f"（已排除 {len(candidates) - len(guids)} 个噪声 GUID，实际试 {len(guids)} 个）")

    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hunt-out")
    os.makedirs(outdir, exist_ok=True)

    batch_size = 6
    real_hits = []
    for i in range(0, len(guids), batch_size):
        batch = guids[i:i + batch_size]
        n = i // batch_size + 1
        print(f"\n--- 批次 {n} ---")
        for g in batch:
            print(f"    {g}")
        try:
            cookie = wp.get_cookie("en-US")
            xml = wp.sync_updates(cookie, category_ids=batch, also_regular=False)
        except Exception as e:
            print(f"    请求失败: {str(e)[:150]}")
            continue

        path = os.path.join(outdir, f"batch{n:02d}.xml")
        open(path, "w", encoding="utf-8").write(xml)

        text = xml.replace("&lt;", "<").replace("&gt;", ">")
        n_id = text.count("UpdateIdentity")
        marks = [m for m in MARKERS if m in text]
        print(f"    响应 {len(xml)} 字符, UpdateIdentity={n_id}")
        if marks:
            print(f"    *** 命中标记: {marks}")
            real_hits.append((n, batch, marks, path))
            wp.summarize(xml, f"batch{n}")
        elif n_id:
            print(f"    （有 {n_id} 个身份，但无 AI 关键字 -> 视为普通更新噪声）")

    print("\n" + "=" * 70)
    if real_hits:
        print(f"真实命中 {len(real_hits)} 批：")
        for n, batch, marks, path in real_hits:
            print(f"  批次 {n}: {marks}")
            print(f"    文件: {path}")
    else:
        print("所有批次均未出现 AI 组件关键字。")
        print("结论：这些 GUID 不是 WindowsWorkload 的 WuCategoryId。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
