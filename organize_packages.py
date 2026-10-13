#!/usr/bin/env python3
"""
organize_packages.py — 把下载到的 AI 包按类别整理到下载目录

结构：
  Downloads\\Windows-AI-包\\
    ├── 说明.md
    ├── 00-清单\\            包清单.json / SHA256清单.json
    ├── 01-旧代3.7-KB5066835\\   与本机 workloads.json 匹配的一代
    │     ├── 1-核心编排\\
    │     ├── 2-推理运行时\\
    │     ├── 3-工作负载定义包\\
    │     ├── 4-会话包\\
    │     └── 5-模型数据包\\
    └── 02-新代5.2-KB5124010\\
          ├── 1-核心编排\\
          ├── 2-推理运行时\\
          ├── 3-执行提供程序\\
          ├── 4-工作负载定义包\\
          ├── 5-会话包\\
          └── 6-模型数据包\\
"""
import hashlib
import json
import pathlib
import shutil
import sys
import zipfile

HERE = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
DL = pathlib.Path(r"C:\Users\jianm\Downloads")
DEST = DL / "Windows-AI-包"

SRC = {
    "01-旧代3.7-KB5066835": HERE / "ai-packages-legacy",
    "02-新代5.2-KB5124010": HERE / "ai-packages",
}

PLATFORMS = ["365", "Lnl", "Stl", "Stx", "Qnn", "J32"]


def classify(pkg):
    """按包身份名分类 -> 子目录名"""
    if pkg.startswith("WindowsWorkload.EP."):
        return "3-执行提供程序"
    if pkg.startswith("WindowsWorkload.WinMLShared") or pkg.startswith("WindowsWorkload.PSOnnxRuntime"):
        return "2-推理运行时"
    if pkg in ("WindowsWorkload.Manager.1", "WindowsWorkload.SessionManager.1",
               "WindowsWorkload.QueryBlockList.1"):
        return "1-核心编排"
    if pkg.startswith("WindowsWorkload.Data."):
        # WindowsWorkload.Data.<功能>.<平台>.1  —— 51KB 的工作负载定义包
        return "4-工作负载定义包"
    # <功能>.Data.<n> —— 模型数据包
    parts = pkg.replace("WindowsWorkload.", "").split(".")
    if "Data" in parts[1:2] or (len(parts) > 1 and parts[1] == "Data"):
        return "6-模型数据包"
    if any(".Data." in pkg for _ in [0]):
        return "6-模型数据包"
    return "5-会话包"


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    if DEST.exists():
        print(f"目标已存在，先删除: {DEST}")
        shutil.rmtree(DEST, ignore_errors=True)
    DEST.mkdir(parents=True, exist_ok=True)

    # 旧代 GUID 名 -> 真实包名
    ident_file = HERE / "legacy-identified.json"
    guid2pkg = {}
    if ident_file.exists():
        ident = json.loads(ident_file.read_text(encoding="utf-8"))
        guid2pkg = {p["file"]: p["package"] for p in ident.get("packages", [])}

    inventory = []
    total = 0

    for gen, srcdir in SRC.items():
        if not srcdir.exists():
            print(f"跳过（不存在）: {srcdir}")
            continue
        msixs = sorted(srcdir.glob("*.msix"))
        print(f"\n=== {gen}  ({len(msixs)} 个) ===")
        for f in msixs:
            pkg = guid2pkg.get(f.name) or f.name.rsplit("_", 2)[0]
            cat = classify(pkg)
            outdir = DEST / gen / cat
            outdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, outdir / f.name)
            total += f.stat().st_size

            # 附带元数据
            mf = srcdir / (f.name + ".AppxManifest.xml")
            if mf.exists():
                shutil.copy2(mf, outdir / mf.name)
            elif ".AppxManifest.xml" not in f.name:
                try:
                    with zipfile.ZipFile(f) as z:
                        (outdir / (f.name + ".AppxManifest.xml")).write_bytes(
                            z.read("AppxManifest.xml"))
                except Exception:
                    pass
            sig = srcdir / (f.name + ".AppxSignature.p7x")
            if sig.exists():
                shutil.copy2(sig, outdir / sig.name)

            inventory.append({
                "generation": gen, "category": cat, "package": pkg,
                "file": f.name, "bytes": f.stat().st_size,
                "sha256": sha256_of(f),
            })
            print(f"  {cat:14} {pkg:52} {f.stat().st_size/1e6:9.2f} MB")

    # 清单
    ld = DEST / "00-清单"
    ld.mkdir(exist_ok=True)
    (ld / "包清单.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    (ld / "SHA256清单.json").write_text(
        json.dumps([{"file": r["file"], "sha256": r["sha256"], "bytes": r["bytes"]}
                    for r in inventory], indent=2, ensure_ascii=False), encoding="utf-8")

    # 统计
    from collections import Counter
    cnt = Counter((r["generation"], r["category"]) for r in inventory)
    summary = "\n".join(f"  {g} / {c:16} {n:3} 个" for (g, c), n in sorted(cnt.items()))

    readme = f"""# Windows AI 组件包集合

获取来源：微软 LCU（累积更新）内的 WIM 内嵌载荷
获取方式：见 `从微软服务器提取AI包-方法文档.md`
总计：**{len(inventory)} 个原版 MSIX / {total/1e6:.1f} MB**

全部经过：WIM 资源 SHA1 校验 + `Get-AuthenticodeSignature` = Valid（Microsoft Corporation）

## 目录结构

按 **代际 -> 角色** 分类。**代际不能混装**（运行时不兼容）。

### 01-旧代3.7-KB5066835
与本机 `C:\\Windows\\SystemApps\\Microsoft.AIFabric.CBS.*\\workloads*.json`
引用的版本匹配（3.7 代运行时）。

### 02-新代5.2-KB5124010
新代运行时（`WinMLShared.5.2` + `EP.*.Framework.1.8`），需要更新的 AIFabric 清单。

### 角色说明

| 目录 | 内容 |
|---|---|
| 1-核心编排 | `Manager.1` / `SessionManager.1` / `QueryBlockList.1` |
| 2-推理运行时 | `WinMLShared.*` / `PSOnnxRuntime.*`（含 CPU 执行后端） |
| 3-执行提供程序 | `EP.Intel.OpenVINO` / `EP.AMD.VitisAI` |
| 4-工作负载定义包 | `WindowsWorkload.Data.<功能>.<平台>.1`（约 51KB，声明依赖） |
| 5-会话包 | `TextRecognition` / `ScrRegDetection` / `SemanticText` / `QueryProcessor` 等（含 Session DLL） |
| 6-模型数据包 | `*.Data.<n>`（模型本体，几十到几百 MB） |

## 包数量分布

{summary}

## 平台标记

| 标记 | 含义 |
|---|---|
| `365` | Windows 365 云 PC（无 NPU，CPU 路径） |
| `Lnl` | Intel Lunar Lake |
| `Ptl` | Intel Panther Lake |
| `Stx` | AMD Strix |
| `Qnn` / `J32` | Qualcomm |
| （无后缀） | 通用 |

## 平台选择机制

系统按**检测到的 NPU 类型**选择 `workloads*.json`：

```
Microsoft.Windows.Workloads.dll
  WorkloadManagerLoadWorkloadsUsingBrokerNpuType
    -> NPUDetect\\npudetect.dll : npudetect_detect_npu()
       -> DXCore 枚举，找描述含 "NPU Compute Accelerator Device" 的设备
```

本机无 NPU -> `UnknownNpu` -> 加载**通用** `workloads.json`（它引用的是不带平台后缀的包名）。

## 依赖闭包完整度

| 平台 | ContentExtraction（Click to Do） | Analysis（语义搜索） |
|---|---|---|
| 365 | 7/7 完整 | 12/12 完整 |
| Lnl | 7/7 完整 | 12/12 完整 |
| Ptl | 7/7 完整 | 12/12 完整 |
| 通用 | 3/7 | 6/12 |
| Qnn/J32 | 缺 | 缺 |

## 安装提示（供参考，本目录未执行）

```
普通包：      Add-AppxPackage -Path <msix>
带 packageExtension 的包：
              Add-AppxProvisionedPackage -Online -PackagePath <msix> -SkipLicense
              （或 dism /Online /Add-ProvisionedAppxPackage）
最后：        Start-Service AppReadiness      <- 关键，默认是 Stopped
```

**注意**：即使安装成功，系统仍不会认领（`AIComponentManager` 枚举的
StateRepository `UupProduct` 记录不会被 `Add-AppxPackage` 创建）。
详见 `安装实验报告.md`。

## 校验

```
00-清单\\SHA256清单.json    每个包的 SHA256
00-清单\\包清单.json        含代际/类别/包身份/大小/哈希
```

逐包验证签名：

```powershell
Get-ChildItem -Recurse -Filter *.msix | ForEach-Object {{
  $s = Get-AuthenticodeSignature $_.FullName
  [pscustomobject]@{{ File=$_.Name; Status=$s.Status; Signer=$s.SignerCertificate.Subject }}
}}
```
"""
    (DEST / "说明.md").write_text(readme, encoding="utf-8")

    print(f"\n{'='*70}")
    print(f"完成：{len(inventory)} 个包 / {total/1e6:.1f} MB")
    print(f"目标：{DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
