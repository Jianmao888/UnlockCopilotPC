#!/usr/bin/env python3
"""
snapshot.py — 安装实验的基线/对比快照

记录：
  1. WindowsWorkload 类包注册情况
  2. AIComponentManager 看到的已安装组件
  3. WindowsAI LastConfiguration 注册表
  4. 关键目录状态
用法: python snapshot.py <标签>
"""
import json
import os
import pathlib
import subprocess
import sys

LABEL = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
OUT = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness\install-experiment")
OUT.mkdir(exist_ok=True)


def ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


snap = {"label": LABEL}

print("=" * 70)
print(f"快照: {LABEL}")
print("=" * 70)

# 1) 包注册
print("\n[1] WindowsWorkload 类包注册")
out = ps("Get-AppxPackage -ErrorAction SilentlyContinue | "
         "Where-Object { $_.Name -match 'WindowsWorkload' } | "
         "Select-Object Name,Version,PackageFamilyName,Status | ConvertTo-Json -Compress")
snap["appx"] = out
print("   " + (out if out and out != "null" else "(无)"))

# 2) 注册表
print("\n[2] WindowsAI LastConfiguration")
out = ps("$p=Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsAI\\LastConfiguration' "
         "-ErrorAction SilentlyContinue; $p | Select-Object HardwareCompatibility,AttemptedInstallCount,"
         "MaxInstallAttemptsAllowed,LastOperationKind | ConvertTo-Json -Compress")
snap["registry"] = out
print("   " + (out or "(读取失败)"))

# 3) 关键目录
print("\n[3] 关键目录")
for d, pat in ((r"C:\Program Files\WindowsApps", "WindowsWorkload"),
               (r"C:\Windows\SystemApps", "WindowsWorkload")):
    out = ps(f"@(Get-ChildItem '{d}' -Directory -ErrorAction SilentlyContinue | "
             f"Where-Object {{ $_.Name -match '{pat}' }}).Count")
    snap[f"dir::{d}"] = out
    print(f"   {d}: {out or '?'} 个匹配目录")

# 4) AIFabric 版本
print("\n[4] AIFabric 包版本")
out = ps("Get-AppxPackage -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'AIFabric' } | "
         "Select-Object Name,Version | ConvertTo-Json -Compress")
snap["aifabric"] = out
print("   " + (out or "(无)"))

(OUT / f"snapshot-{LABEL}.json").write_text(
    json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n已保存: {OUT / ('snapshot-' + LABEL + '.json')}")
