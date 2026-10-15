"""Organise the Windows AI workload products we have locally, per product.

For every product RUM found in the metadata pool:
  * read every local MSIX's real AppxManifest Identity (name + version + arch)
  * match each RUM entity payload against those identities (exact / version-mismatch / missing)
  * build  ai-products\<ProductID>\{load, metadata, install.ps1, INVENTORY.md}
  * write  ai-products\SUMMARY.md + inventory.json

Nothing here installs anything; it only organises files and reports truthfully.
"""
import json
import os
import pathlib
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(r"C:\Users\jianm\Code\DeepseekHarness")
OUT = ROOT / "ai-products"
ENGINE_SRC = ROOT / "native-install" / "source-analysis365" / "metadata"

# ---- locate metadata pool
POOL = None
for d in os.listdir(r"C:\Users\jianm\OneDrive"):
    c = pathlib.Path(r"C:\Users\jianm\OneDrive") / d / "ChatGPT" / "2026-10-12" / "qing" / "outputs" / "Windows-AI-UUP-product-metadata" / "KB5066835"
    if c.is_dir():
        POOL = c
        break
assert POOL, "metadata pool not found"

# ---- index every local MSIX by real identity
TREES = []
for p in pathlib.Path(r"C:\Users\jianm\Downloads").glob("Windows-AI-*"):
    TREES.append(p)
for extra in (ROOT / "native-install" / "source-analysis365", ROOT / "native-install" / "source-analysislnl",
              ROOT / "ai-packages", ROOT / "ai-packages" / "lnl-extra"):
    if extra.is_dir():
        TREES.append(extra)

index = {}          # name -> {version: path}
byfile = []
for t in TREES:
    for f in t.rglob("*.msix"):
        try:
            if f.stat().st_size < 10000:
                continue
            with zipfile.ZipFile(f) as z:
                if "AppxManifest.xml" not in z.namelist():
                    continue
                root = ET.fromstring(z.read("AppxManifest.xml"))
            ident = next(n for n in root if n.tag.endswith("Identity"))
            name = ident.attrib.get("Name")
            ver = ident.attrib.get("Version")
            arch = ident.attrib.get("ProcessorArchitecture")
            index.setdefault(name, {})[ver] = f
            byfile.append((name, ver, arch, f))
        except Exception:
            continue

# ---- build per-product directories
rum_files = sorted(POOL.glob("*.rum.json"))
summary = []
inv_all = {}

for rum_path in rum_files:
    prod_meta = json.loads(rum_path.read_text(encoding="utf-8", errors="replace"))
    up = prod_meta["UpdateProduct"][0]
    prod = up["ProductIdentifier"]
    arch = up.get("ProductArchitecture", "amd64")
    full_id = "%s.%s" % (prod, arch)
    pdir = OUT / full_id
    load = pdir / "load"
    meta = pdir / "metadata"
    if pdir.exists():
        shutil.rmtree(pdir)
    load.mkdir(parents=True)
    meta.mkdir(parents=True)

    # engine + plugins
    for f in ENGINE_SRC.iterdir():
        if f.is_file() and (f.suffix.lower() == ".dll" or f.name in ("msix.installer.json", "hardware.installer.json")):
            shutil.copy2(f, meta / f.name)
    cab = POOL / (full_id + ".rum.json.cab")
    if cab.exists():
        shutil.copy2(cab, meta / cab.name)
    else:
        (meta / (full_id + ".rum.json")).write_text(rum_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

    rows = []
    exact = vmis = miss = 0
    for ent in up.get("UpdateEntityCollection", []):
        ename = ent["EntityIdentifier"]["EntityName"]
        pkg = ename.split("_")[0]
        pays = ent.get("EntityPayload", {}).get("Canonical", []) or []
        if not pays:
            rows.append((pkg, "-", "no-payload", ""))
            continue
        for pl in pays:
            pname = pl["PayloadName"]
            if not pname.endswith(".msix"):
                rows.append((pkg, pname, "non-msix", ""))
                continue
            want_ver = pname.split("_")[1]
            have = index.get(pkg, {})
            if want_ver in have:
                src = have[want_ver]
                shutil.copy2(src, load / pname)
                exact += 1
                rows.append((pkg, want_ver, "exact", str(src)))
            elif have:
                other = sorted(have.keys())[-1]
                rows.append((pkg, want_ver, "VERSION-MISMATCH (have %s)" % other, str(have[other])))
                vmis += 1
            else:
                rows.append((pkg, want_ver, "MISSING (no local msix)", ""))
                miss += 1

    # per-product inventory
    lines = ["# %s" % full_id, "", "RUM: `%s`  (ProductVersion %s)" % (rum_path.name, up.get("ProductVersion")), "",
             "| package | want version | status | local source |", "|---|---|---|---|"]
    for pkg, ver, st, src in rows:
        lines.append("| `%s` | %s | %s | %s |" % (pkg, ver, st, ("`%s`" % src) if src else ""))
    lines += ["", "**exact=%d  version-mismatch=%d  missing=%d**" % (exact, vmis, miss), ""]
    if vmis or miss:
        lines.append("> 该系统产品**当前无法离线安装**：必须先取得上表未 `exact` 的载荷（RUM 声明的精确版本）。")
    else:
        lines.append("> 载荷齐备（全部 exact），可直接执行 `install.ps1`。")
    lines.append("")
    lines.append("## 安装")
    lines.append("```powershell")
    lines.append("# 管理员运行；同一次只跑一个安装")
    lines.append(r"$py='C:\Users\jianm\AppData\Local\Programs\Python\Python312\python.exe'")
    lines.append(r"& $py -u 'C:\Users\jianm\Code\DeepseekHarness\native-install\tools\run_install.py' attempt-<newname> '%s' '%s.rum.json.cab' '%s'" % (pdir, full_id, prod))
    lines.append("```")
    (pdir / "INVENTORY.md").write_text("\n".join(lines), encoding="utf-8")

    # per-product install script
    install = r"""# Install product: %(full)s   (run ELEVATED, one install at a time)
param(
  [Parameter(Mandatory=$true)][string]$RunName   # e.g. attempt-lnl-analysis7
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = 'C:\Users\jianm\AppData\Local\Programs\Python\Python312\python.exe'
$launcher = 'C:\Users\jianm\Code\DeepseekHarness\native-install\tools\run_install.py'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run elevated' }
& $py -u $launcher $RunName $here '%(full)s.rum.json.cab' '%(prod)s'
Write-Host ''
Write-Host '--- verify ---'
$tools = Split-Path -Parent $launcher
$ev = Join-Path $tools ($RunName + '.events.txt')
if (Test-Path $ev) { Get-Content $ev | Select-String 'fileRequestCount|guard|install\.end' }
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\UUPProducts' |
  Where-Object { $_.PSChildName -eq '%(prod)s' } |
  ForEach-Object { '{0} packages={1}' -f $_.PSChildName, @(Get-ChildItem $_.PSPath).Count }
""" % {"full": full_id, "prod": prod}
    (pdir / "install.ps1").write_text(install, encoding="utf-8")

    inv_all[full_id] = dict(product=prod, arch=arch, rum=str(rum_path), exact=exact,
                            version_mismatch=vmis, missing=miss,
                            rows=[dict(package=r[0], want=r[1], status=r[2], source=r[3]) for r in rows])
    summary.append((full_id, exact, vmis, miss))

# ---- summary
lines = ["# Windows AI 工作负载产品 —— 本机清单（按产品整理）", "",
         "生成方式：逐个产品解析其 RUM，并把每个实体的载荷名/版本与**本机 MSIX 的真实 Identity**（读 AppxManifest）逐条比对。",
         "目录下每个产品都有：`load/`（按 RUM 命名的载荷）、`metadata/`（引擎+插件+RUM）、`install.ps1`、`INVENTORY.md`。", "",
         "| 产品 | exact | 版本不符 | 缺失 | 能否离线安装 |", "|---|---|---|---|---|"]
for full, e, v, m in summary:
    ok = "✅ 可以" if (v == 0 and m == 0) else "❌ 缺件，需下载"
    lines.append("| `%s` | %d | %d | %d | %s |" % (full, e, v, m, ok))
lines += ["", "## 已本机验证可用的功能", "",
          "- `Windows.Workload.ContentExtraction.LNL.amd64` → **OCR 可用**（Gallery 实测）",
          "- `Windows.Workload.Analysis.LNL.amd64` → **语义搜索可用**（Gallery 实测）", "",
          "## 说明", "",
          "- `exact` = 本机存在 RUM 声明**精确版本**的载荷（可直接安装）",
          "- `版本不符` = 本机有同包名但版本不同 → 引擎会判缺件（`fileRequestCount > 0`）→ 安装被守卫拦下",
          "- `缺失` = 本机完全没有该包",
          "- `365` 族执行走 HybridCompute（云），本地通常不可用；`LNL/STX` 族部分组件带 CPU 路径（OCR、语义搜索已验证）"]
(OUT / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
(OUT / "inventory.json").write_text(json.dumps(inv_all, ensure_ascii=False, indent=2), encoding="utf-8")

print("products:", len(summary))
for full, e, v, m in summary:
    print("  %-46s exact=%-3d mismatch=%-3d missing=%-3d" % (full, e, v, m))
print("local msix identities indexed:", sum(len(v) for v in index.values()))
