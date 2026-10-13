#!/usr/bin/env python3
"""
register_uup_products.py — 按官方 add-OemPreload.ps1 的方式注册 UUP 产品

官方注册结构（来自 learn.microsoft.com 上发布的 add-OemPreload.ps1）：
  HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Appx\\AppxAllUserStore\\UUPProducts\\<productId>
      Version   = <productVersion>   REG_SZ
      IsPinned  = 1                  REG_DWORD
      <PackageFullName>\\            每个包一个子键

数据来源：包 manifest 的
  <uap17:PackageExtension Name="com.microsoft.windows.workload">
    <uap17:Properties><UupProducts>
      <UupProduct Id="Windows.Workload......." />

用法:
  python register_uup_products.py --dry-run     # 只列将要写的内容
  python register_uup_products.py --apply       # 实际写（需提权）
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

HERE = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
PKG_DIRS = [HERE / "ai-packages-legacy", HERE / "ai-packages"]

UAP17 = "http://schemas.microsoft.com/appx/manifest/uap/windows17"
UAP17_ALT = "http://schemas.microsoft.com/appx/manifest/uap/windows10/17"


def installed_packages():
    """扫 WindowsApps 下所有 WindowsWorkload 目录（含 provisioned 但未为当前用户注册的）"""
    out = []
    wd = pathlib.Path(r"C:\Program Files\WindowsApps")
    for sub in sorted(wd.glob("WindowsWorkload.*")):
        mf = sub / "AppxManifest.xml"
        if not mf.exists():
            continue
        out.append({"Name": sub.name.rsplit("_", 4)[0],
                    "PackageFullName": sub.name,
                    "Version": sub.name.rsplit("_", 4)[1] if "_" in sub.name else "0",
                    "dir": str(sub)})
    return out


def parse_uup_products(manifest_bytes):
    """从 manifest 抽取 <UupProduct Id=.../> 列表"""
    root = ET.fromstring(manifest_bytes)
    ids = []
    for el in root.iter():
        if el.tag.endswith("UupProduct"):
            pid = el.get("Id")
            if pid:
                ids.append(pid)
    return ids


def find_manifest(pkg_name):
    """在解压出来的包里找 manifest（新代没有独立 manifest 文件，从 msix 里读）"""
    for d in PKG_DIRS:
        if not d.exists():
            continue
        for f in d.glob("*.msix"):
            base = f.name.rsplit("_", 2)[0]
            if base == pkg_name or base.split("_")[0] == pkg_name:
                try:
                    with zipfile.ZipFile(f) as z:
                        return z.read("AppxManifest.xml")
                except Exception:
                    pass
        mf = d / (pkg_name + ".AppxManifest.xml")
        if mf.exists():
            return mf.read_bytes()
    # 退而求其次：从已安装目录读
    wd = pathlib.Path(r"C:\Program Files\WindowsApps")
    for sub in wd.glob(pkg_name + "*"):
        m = sub / "AppxManifest.xml"
        if m.exists():
            return m.read_bytes()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry = not args.apply

    pkgs = installed_packages()
    print(f"已注册的 WindowsWorkload 包: {len(pkgs)}\n")

    rows = []
    for p in pkgs:
        name = p["Name"]
        full = p["PackageFullName"]
        ver = p["Version"]
        mf = find_manifest(name)
        if not mf:
            print(f"  ⚠ {name}: 找不到 manifest")
            continue
        pids = parse_uup_products(mf)
        if not pids:
            print(f"  · {name}: 无 <UupProduct>")
            continue
        for pid in pids:
            rows.append({"productId": pid, "packageFullName": full,
                         "version": ver, "package": name})
            print(f"  ✔ {pid}")
            print(f"      <- {full}")

    print(f"\n共 {len(rows)} 条产品注册")

    def regkey(pid):
        return ("HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Appx"
                "\\AppxAllUserStore\\UUPProducts\\" + pid)

    if dry:
        print("\n[dry-run] 将执行:")
        seen = set()
        for r in rows:
            k = regkey(r["productId"])
            if k not in seen:
                seen.add(k)
                print(f"  reg add \"{k}\" /v Version  /t REG_SZ    /d {r['version']} /f")
                print(f"  reg add \"{k}\" /v IsPinned /t REG_DWORD /d 1 /f")
            print(f"  reg add \"{k}\\{r['packageFullName']}\" /f")
        print("\n（加 --apply 实际写入，需提权）")
        return 0

    lines = ["$ErrorActionPreference='Continue'"]
    seen = set()
    for r in rows:
        k = regkey(r["productId"])
        if k not in seen:
            seen.add(k)
            lines.append(f'& reg.exe add "{k}" /v Version  /t REG_SZ    /d "{r["version"]}" /f')
            lines.append(f'& reg.exe add "{k}" /v IsPinned /t REG_DWORD /d 1 /f')
        lines.append(f'& reg.exe add "{k}\\{r["packageFullName"]}" /f')
    lines.append('Write-Output "=== verify ==="')
    lines.append("$k='HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Appx\\AppxAllUserStore\\UUPProducts'")
    lines.append("if (Test-Path $k) { Get-ChildItem $k | ForEach-Object { Write-Output $_.PSChildName } }")
    script = HERE / "install-experiment" / "_register_uup.ps1"
    script.parent.mkdir(exist_ok=True)
    script.write_text("\n".join(lines), encoding="ascii")
    print(f"\n脚本已写入: {script}")
    print("用 sudo 执行它即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
