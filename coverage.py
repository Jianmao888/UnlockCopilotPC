#!/usr/bin/env python3
"""
coverage.py — 各平台包覆盖度分析

对本机 7 份 workloads*.json，逐个平台算出：
  该平台所有 workload 需要的包  vs  我们已下载的包
给出精确缺口清单。
"""
import glob
import json
import os
import pathlib
import re

AIFABRIC = pathlib.Path(r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe")
HERE = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
NEW = HERE / "ai-packages"           # KB5124010（5.2/1.8 代）
OLD = HERE / "ai-packages-legacy"    # KB5066835（3.7 代）
REF = pathlib.Path(r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验")


def fam(name):
    """文件名 -> FamilyName（仅适用于 WindowsWorkload.* 命名的新包子）"""
    n = name[:-5] if name.endswith(".msix") else name
    parts = n.rsplit("_", 2)
    return parts[0] + "_8wekyb3d8bbwe" if len(parts) == 3 else n


def collect(d):
    out = {}
    if not d.exists():
        return out
    for f in d.glob("*.msix"):
        out[fam(f.name)] = f.name
    return out


def collect_legacy(d, ident_file):
    """旧包文件名是 GUID，必须用识别结果里的真实包名"""
    out = {}
    if not d.exists() or not ident_file.exists():
        return out
    ident = json.loads(ident_file.read_text(encoding="utf-8"))
    guid2pkg = {p["file"]: p["package"] for p in ident.get("packages", [])}
    for f in d.glob("*.msix"):
        pkg = guid2pkg.get(f.name)
        if pkg:
            out[pkg + "_8wekyb3d8bbwe"] = f.name
        else:
            out[fam(f.name)] = f.name
    return out


have_new = collect(NEW)
have_old = collect_legacy(OLD, HERE / "legacy-identified.json")
have_ref = collect(REF / "模型包-当前")
have_ref.update(collect(REF / "模型包-旧接口"))
have = {**have_ref, **have_new, **have_old}

print(f"已拥有包总数: {len(have)}")
print(f"  参考副本 {len(have_ref)}   新 MSU {len(have_new)}   旧 MSU {len(have_old)}")
print()

FOCUS = {
    "Windows.Workload.ContentExtraction",
    "Windows.Workload.Analysis",
    "Windows.Workload.ContentExtraction.Lnl",
    "Windows.Workload.Analysis.Lnl",
    "Windows.Workload.ContentExtraction.365",
    "Windows.Workload.Analysis.365",
    "Windows.Workload.ContentExtraction.Stx",
    "Windows.Workload.Analysis.Stx",
}

for jf in sorted(AIFABRIC.glob("workloads*.json")):
    d = json.load(open(jf, encoding="utf-8-sig"))
    plat = jf.name.replace("workloads", "").replace(".json", "") or "(通用)"
    workloads = d.get("Workloads", [])
    apiinfos = d.get("ApiInfos", [])

    # TextRecognizer / ScrRegDetection / SemanticText 的会话包（最贴近 Click to Do）
    keyapi = {}
    for a in apiinfos:
        cn = a.get("ApiClassName", "")
        for want in ("TextRecognizer", "ScreenRegionDetector", "SemanticTextEmbeddingsCreator"):
            if cn.endswith(want):
                keyapi[want] = a.get("SessionPackage", "")

    print("=" * 78)
    print(f"平台 {plat:8}  ({jf.name})   Workloads={len(workloads)} ApiInfos={len(apiinfos)}")
    print("=" * 78)
    for k, v in keyapi.items():
        ok = "✅ 有" if v in have else "❌ 缺"
        print(f"   {k:30} -> {ok}  {v}")

    # ContentExtraction / Analysis 的完整依赖
    for wid in sorted(FOCUS):
        w = next((x for x in workloads if x.get("Id") == wid), None)
        if not w:
            continue
        need = [p.get("FamilyName", "") for p in w.get("Packages", []) if p.get("FamilyName")]
        miss = [x for x in need if x not in have]
        print(f"\n   workload {wid}:  需要 {len(need)}  有 {len(need)-len(miss)}  缺 {len(miss)}")
        if miss:
            for m in miss:
                print(f"        ❌ {m}")
    print()
