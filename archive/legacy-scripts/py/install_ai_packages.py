#!/usr/bin/env python3
"""
install_ai_packages.py — 安装 WindowsWorkload 包并观察系统反应

在独立 PowerShell 中逐个 Add-AppxPackage，捕获每个包的成败与错误码。
不修改系统文件；只做包注册。

用法:
  python install_ai_packages.py --preset lnl-ce      # Lnl 平台 ContentExtraction 最小集
  python install_ai_packages.py --preset 365-ce      # 365 平台最小集
  python install_ai_packages.py --files a.msix b.msix
  python install_ai_packages.py --uninstall          # 卸载所有 WindowsWorkload 包
"""
import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
NEW = HERE / "ai-packages"          # KB5124010
OLD = HERE / "ai-packages-legacy"   # KB5066835

# 以"包身份名"为键，指向实际文件（新包按文件名，旧包按 GUID 文件名）
def index_dir(d, ident_file=None):
    out = {}
    if not d.exists():
        return out
    guid2pkg = {}
    if ident_file and ident_file.exists():
        ident = json.loads(ident_file.read_text(encoding="utf-8"))
        guid2pkg = {p["file"]: p["package"] for p in ident.get("packages", [])}
    for f in d.glob("*.msix"):
        pkg = guid2pkg.get(f.name)
        if not pkg:
            pkg = f.name.rsplit("_", 2)[0]
        out[pkg] = f
    return out


NEW_IDX = index_dir(NEW)
OLD_IDX = index_dir(OLD, HERE / "legacy-identified.json")

PRESETS = {
    # Lnl ContentExtraction 完整闭包
    "lnl-ce": ["WindowsWorkload.Data.ContentExtraction.Lnl.1",
               "WindowsWorkload.Manager.1",
               "WindowsWorkload.PSOnnxRuntime.Lnl.3.7",
               "WindowsWorkload.ScrRegDetection.Data.1",
               "WindowsWorkload.ScrRegDetection.Lnl.1",
               "WindowsWorkload.SessionManager.1",
               "WindowsWorkload.TextRecognition.Lnl.1"],
    # 365 ContentExtraction 完整闭包
    "365-ce": ["WindowsWorkload.Data.ContentExtraction.365.1",
               "WindowsWorkload.Manager.1",
               "WindowsWorkload.PSOnnxRuntime.365.3.7",
               "WindowsWorkload.ScrRegDetection.Data.1",
               "WindowsWorkload.ScrRegDetection.365.1",
               "WindowsWorkload.SessionManager.1",
               "WindowsWorkload.TextRecognition.365.1"],
    # 仅通用核心（对照：系统默认选通用 JSON 时它想要的三个）
    "core": ["WindowsWorkload.Manager.1", "WindowsWorkload.SessionManager.1",
             "WindowsWorkload.QueryBlockList.1"],
}


def run_ps_sudo(script_text, timeout=900):
    """把脚本写到临时 .ps1，用 sudo 提权执行（避免 sudo 拆散带空格的参数）"""
    tmp = HERE / "install-experiment" / "_run.ps1"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(script_text, encoding="ascii", errors="replace")  # 必须纯 ASCII
    r = subprocess.run(["sudo", "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(tmp)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    return (r.stdout or "").strip(), (r.stderr or "").strip()


def install_file(path):
    """提权安装单个包，返回 (ok, message)"""
    ps = (
        "$ErrorActionPreference='Stop'\n"
        f"try {{\n"
        f"  Add-AppxPackage -Path '{path}' -ForceUpdateFromAnyVersion -ErrorAction Stop\n"
        f"  Write-Output 'OK'\n"
        f"}} catch {{\n"
        f"  Write-Output ('ERR: ' + $_.Exception.Message)\n"
        f"  Write-Output ('HR: ' + $_.Exception.HResult)\n"
        f"}}\n"
    )
    out, err = run_ps_sudo(ps)
    if "OK" in out:
        return True, out.replace("\n", " ")
    return False, (out or err).replace("\n", " ")[:400]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=list(PRESETS))
    ap.add_argument("--files", nargs="*", default=[])
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.uninstall:
        print("=== 卸载所有 WindowsWorkload 包 ===")
        ps = ("Get-AppxPackage -ErrorAction SilentlyContinue |\n"
              "Where-Object { $_.Name -match '^WindowsWorkload[.]' } |\n"
              "ForEach-Object {\n"
              "  Write-Output ('REMOVING ' + $_.PackageFullName)\n"
              "  Remove-AppxPackage -Package $_.PackageFullName -ErrorAction SilentlyContinue\n"
              "}\n"
              "Write-Output 'DONE'\n")
        out, err = run_ps_sudo(ps, timeout=2400)
        print(out or "(无输出)")
        if err:
            print("stderr:", err[:400])
        return 0

    targets = []
    if args.preset:
        for pkg in PRESETS[args.preset]:
            f = OLD_IDX.get(pkg) or NEW_IDX.get(pkg)
            if f is None:
                print(f"  ⚠ 找不到包: {pkg}")
                continue
            targets.append((pkg, f))
    for f in args.files:
        targets.append((pathlib.Path(f).stem, pathlib.Path(f)))

    if not targets:
        print("没有选中任何包")
        return 1

    print(f"待安装 {len(targets)} 个包:\n")
    for pkg, f in targets:
        src = "旧 MSU" if f.parent == OLD else "新 MSU"
        print(f"  [{src}] {pkg:52} {f.stat().st_size/1e6:8.2f} MB")

    if args.dry_run:
        return 0

    print("\n=== 开始安装（每个包一次提权）===\n")
    results = []
    for i, (pkg, f) in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {pkg}")
        ok, msg = install_file(f)
        print(f"      {'✔ 成功' if ok else '✗ 失败'}  {msg[:220]}")
        results.append({"package": pkg, "file": str(f), "ok": ok, "message": msg[:600]})
        sys.stdout.flush()

    outdir = HERE / "install-experiment"
    outdir.mkdir(exist_ok=True)
    (outdir / "install-results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    okc = sum(1 for r in results if r["ok"])
    print(f"\n{'='*70}")
    print(f"成功 {okc} / {len(results)}")
    for r in results:
        if not r["ok"]:
            print(f"  ✗ {r['package']}: {r['message'][:150]}")
    print(f"结果: {outdir/'install-results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
