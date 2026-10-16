# Windows AI 工作负载产品 —— 本机清单（按产品整理）

生成方式：逐个产品解析其 RUM，并把每个实体的载荷名/版本与**本机 MSIX 的真实 Identity**（读 AppxManifest）逐条比对。
目录下每个产品都有：`load/`（按 RUM 命名的载荷）、`metadata/`（引擎+插件+RUM）、`install.ps1`、`INVENTORY.md`。

| 产品 | exact | 版本不符 | 缺失 | 能否离线安装 |
|---|---|---|---|---|
| `Windows.Workload.Analysis.365.amd64` | 12 | 0 | 0 | ✅ 可以 |
| `Windows.Workload.Analysis.LNL.amd64` | 12 | 0 | 0 | ✅ 可以 |
| `Windows.Workload.Analysis.STX.amd64` | 6 | 4 | 2 | ❌ 缺件，需下载 |
| `Windows.Workload.ContentExtraction.365.amd64` | 7 | 0 | 0 | ✅ 可以 |
| `Windows.Workload.ContentExtraction.LNL.amd64` | 6 | 1 | 0 | ❌ 缺件，需下载 |
| `Windows.Workload.ContentExtraction.STX.amd64` | 3 | 3 | 1 | ❌ 缺件，需下载 |
| `Windows.Workload.ImageSearch.365.amd64` | 5 | 7 | 0 | ❌ 缺件，需下载 |
| `Windows.Workload.ImageSearch.LNL.amd64` | 5 | 7 | 2 | ❌ 缺件，需下载 |
| `Windows.Workload.ImageSearch.STX.amd64` | 3 | 7 | 4 | ❌ 缺件，需下载 |
| `Windows.Workload.SettingsModel.LNL.amd64` | 2 | 3 | 0 | ❌ 缺件，需下载 |
| `Windows.Workload.SettingsModel.STX.amd64` | 2 | 3 | 0 | ❌ 缺件，需下载 |

## 已本机验证可用的功能

- `Windows.Workload.ContentExtraction.LNL.amd64` → **OCR 可用**（Gallery 实测）
- `Windows.Workload.Analysis.LNL.amd64` → **语义搜索可用**（Gallery 实测）

## 说明

- `exact` = 本机存在 RUM 声明**精确版本**的载荷（可直接安装）
- `版本不符` = 本机有同包名但版本不同 → 引擎会判缺件（`fileRequestCount > 0`）→ 安装被守卫拦下
- `缺失` = 本机完全没有该包
- `365` 族执行走 HybridCompute（云），本地通常不可用；`LNL/STX` 族部分组件带 CPU 路径（OCR、语义搜索已验证）