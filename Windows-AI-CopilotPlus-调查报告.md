# Windows AI（Copilot+）硬件限制调查报告

> 调查时间：2026-10-12 ~ 2026-10-13
> 目标机：Xiaomi Book Pro 16 2022 / i7-1260P / RTX 2050 + Iris Xe / 16 GB / Windows 26H2 (26300.9550) x64
> 调查性质：**全程只读为主**，仅在明确标注处修改注册表；所有修改均已回滚。

---

## 0. 摘要

**核心结论：**

1. **NPU 不是技术门槛，是分发门槛。** 目标功能的模型是小型 ONNX 模型，后端是 `PSOnnxRuntime`（跨硬件），本机 CPU/GPU 完全跑得动。
2. **Windows 并不认为本机"硬件不兼容"。** 实测 `TextRecognizer.GetReadyState() = 1 = NotReady`，而真正的硬件拒绝值是 `5 = NotCompatibleWithSystemHardware`。
3. **资格布尔值可以改，但改了没用。** 应用层的 Copilot+ 资格判断（`AIPlatformCapability` / `AICapabilities`）已被证明可在进程内翻转，但它只是"门牌"，不影响"发货"。
4. **★ 找到了产品声明机制并验证成功。** `HKLM\...\Update\TargetingInfo\{Installed,DynamicInstalled,PersistentDynamicInstalled}\<产品名>` 就是"向 WU 服务端声明本机拥有哪些产品"的开关 —— 加键后，客户端确实在 `ProductAttributes(CTAC)` 里声明了 `PN=Windows.Workload.Analysis.amd64`。
5. **但服务端根本不看产品名。** 直接构造请求做对照实验：乱写的产品名（`ZZZ.NotAReal.Product.amd64`）与真实产品名返回**完全相同**的 28 个结果。服务端只判断 `<Products>` 是否为空。
6. **返回的全是适用性判定实体，没有包。** 28 项全是 `Detectoid`(20) + `Category`(5)，**全部 `IsLeaf=false`，0 个文件名** —— 没有任何可下载内容。
7. **`StateRepository` 方向被证伪。** `UupProduct` / `UupProductPackage` 两表为空，且 CTAC 并非源自它。

**实用结论：** 想要"用上这些能力"，走**微软公开的 Windows ML + 公开模型**是唯一可兑现的路径（不受 Copilot+ 限制）；想要"那个原生外壳"，需要一台真正的 Copilot+ 机器导出模型包。

**通过 Windows Update 获取模型包的路径已全部走完，结论为否。**

---

## 1. 名词与硬件门槛

| 名称 | 含义 |
|---|---|
| **AI PC** | 纯营销词，厂商随意使用，**不保证**任何 Windows 独占功能 |
| **AI+ PC** / **Copilot+ PC** | 同一个东西的中英文名。硬指标：NPU ≥ 40 TOPS + 16 GB 内存 + 256 GB 存储 |
| CPU/GPU TOPS | **不能**与 NPU 相加抵算 |

**具体功能的附加条件：**

| 功能 | 依赖 |
|---|---|
| Click to Do | Copilot+ 资格 + 屏幕内容理解模型（OCR / 区域检测） |
| Recall | Copilot+ + 40 TOPS + 16 GB + 8 逻辑处理器 + 256 GB + 50 GB 空闲 + **设备加密/BitLocker + Windows Hello ESS + VBS Enclave** |
| Studio Effects（基础） | 部分效果可用 10+ TOPS NPU；**核心是 OEM 摄像头驱动链（WSE）**，不是模型包 |
| Studio Effects（增强） | 效果子集随 NPU/OEM 而异，部分限 Snapdragon X |

---

## 2. 本机基线（实测）

### 2.1 已安装组件

| 组件 | 版本 | 类型 | 位置 |
|---|---|---|---|
| `MicrosoftWindows.Client.CoreAI` | 1000.26100.9549.0 | System | `SystemApps\...CoreAI_cw5n1h2txyewy` |
| `Microsoft.AIFabric.CBS.1.6` | 1.6.951.100 | System (Framework) | `SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe` |
| `Microsoft.Windows.AI.Speech.Preview.CPU` | 1.2607.112.0 | **Store** | `WindowsApps\...` |
| `Microsoft.AIDevGallery` | 0.6.2.0 | Store | `WindowsApps\...` |

**服务：** `WSAIFabricSvc`（显示名"Windows AI 组件主机"）— Running / Auto

**CoreAI 包内含：** `ClickToDo.exe`、`aicontext.exe`、`DiscoveryOverlay.dll`、`AIContextService.dll`、`AIXHost\Assets\ClickToDo`

**AIFabric 包内含：** `Microsoft.Windows.Workloads.dll`、`Microsoft.Windows.Vision.dll`、`Microsoft.Windows.SemanticSearch.dll`、`Microsoft.Graphics.Imaging.dll`、`Microsoft.Windows.AI.Generative.dll`、`NPUDetect\NPUDetect.dll`、**7 份 workloads 清单**、19 份 winmd

### 2.2 缺失组件

**全部 `WindowsWorkload.*` 包 —— 一个都没有。**

（当前用户清单、所有用户清单均未找到；`C:\Program Files\WindowsApps` 与 `C:\Windows\SystemApps` 中无实体。）

### 2.3 相关注册表

```
HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsAI\LastConfiguration
  HardwareCompatibility             = 0     ← 系统判定"硬件不兼容"
  AttemptedInstallCount             = 0     ← 从未形成一次安装尝试
  MaxInstallAttemptsAllowed         = 5
  AllowedInRegion                   = 1     ← 地区已允许
  MeetsAdditionalDriverRequirements = 1
  PolicyConfigured / PolicyEnabled  = 0
  FTDisabledState                   = 0
  LastOperationKind                 = 2
  LastBuild                         = 9168
  LastKnownLCUVersion               = 10.0.26100.9550

HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WorkloadManager\HCF   (存在，无 Status 子键)

HKLM\SOFTWARE\Microsoft\WindowsRuntime\ActivatableClassId\
  Windows.AI.Management.Internal.AIComponentManager  →  C:\Windows\System32\AIComponentMgmt.dll
```

**重要：** `HardwareCompatibility` 是**评估结果记录**，不是开关。实测改为 1 后：
- 不重启服务 → 会被写回 0
- 重启服务 → 保持 1，但 `AttemptedInstallCount` 仍为 0，**不触发任何安装**

---

## 3. 完整组件链条

```
┌─ 应用层 ─────────────────────────────────────────────────────────┐
│  WinUI/打包应用（如 AI Dev Gallery，需 systemAIModels 能力声明）  │
│    → RoGetActivationFactory("Microsoft.Windows.AI.Imaging.TextRecognizer",
│                              IID_ITextRecognizerStatics)          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌─ 就绪层（系统组件）───────────▼───────────────────────────────────┐
│  ITextRecognizerStatics:                                          │
│    slot[6] GetReadyState()        → AIFeatureReadyState           │
│    slot[7] EnsureReadyAsync()     → IAsyncOperationWithProgress<  │
│                                       AIFeatureReadyResult,Double>│
│    slot[8] CreateAsync()                                          │
│         ↓                                                         │
│  Microsoft.Windows.Workloads.dll  (WorkloadManager / SessionManager)
│         ↓  解析 workloads.json                                    │
│    API 类 → SessionPackage 映射                                   │
└──────────────────────────────┬───────────────────────────────────┘
                               │  缺包
┌─ 获取层（Windows Update）─────▼───────────────────────────────────┐
│  MoUpdateOrchestrator（后台任务，非 API 触发）                     │
│    → Criteria = "(Product='Windows.Workload.ContentExtraction.amd64'
│                   and IsInstalled=0 and DeploymentAction=*)"      │
│    → ProductAttributes(Caller): PN=Windows.Workload....amd64&V=.. │
│         ↓ 联邦搜索                                                 │
│  Service 8B24B027-... ("Third party service")                     │
│    → https://fe3cr.delivery.mp.microsoft.com/.../client.asmx      │
│         ↓                                                         │
│  服务端按"客户端声明的产品清单 ProductAttributes(CTAC)"判定适用性   │
│    → 本机未声明该产品 → 返回 0                                     │
│    → 客户端记为 "Service doesn't support product specific search" │
└──────────────────────────────────────────────────────────────────┘

旁路：
  AIComponentManager (AIComponentMgmt.dll)
    → PE_CreateProductEnumerator
    → UupProducts / uupProductId
    → ms-uup://Product/com.microsoft.windows.workload.*
    → Windows.Internal.StateRepository.PkgExtension（产品注册来源）
```

---

## 4. 各层详解

### 4.1 能力声明层（App 看得见的那个）

| 类 | IID | 方法槽 |
|---|---|---|
| `Microsoft.Windows.AI.AICapabilities` | `IAICapabilitiesStatics` = `37968861-98ee-599c-aa38-aa79866d6ddc` | slot[6] `HasAICapability(category)` |
| `WindowsUdk.AI.PlatformCapabilities.AIPlatformCapability` | `bd64214c-9545-5ea9-9c65-8934640751e6` | slot[6] `IsFeatureAvailable(int32)`<br>slot[7] `IsCopilotPlusPC()` |
| `WindowsUdk.Management.Update.EnterpriseFeatureControl` | `82859d1f-647d-5dc4-b5e2-f22665a70f64` | slot[6] `IsFeatureEnabled(uint32)` |

**实测结果：**
- 本机 `IsCopilotPlusPC()` = false，`IsFeatureAvailable(0..7)` 全 false
- `EnterpriseFeatureControl.IsFeatureEnabled(56114500)`（Click to Do 发布门槛）= **true**（本机已是开的）
- **进程内 Hook 可成功翻转这些布尔值**（上一轮已验证：`false → true`，其他功能与 HRESULT 保持不变）

**应用侧判据（来自 `Microsoft.Windows.AI.winmd`）：**

```
AFeatureReadyState:
  0 Ready                          模型已安装并可供使用
  1 NotReady                       ← 本机实测值
  2 NotSupportedOnCurrentSystem    当前 OS 版本或硬件配置不支持
  3 DisabledByUser                 模型已被删除或禁用
  4 CapabilityMissing              缺少 systemAIModels 能力声明（EnsureReadyAsync 抛 access_denied）
  5 NotCompatibleWithSystemHardware 与硬件不兼容（没有 NPU，或 NPU 不符合要求）
  6 OSUpdateNeeded                 当前 OS 版本不兼容
```

**关键：本机 `GetReadyState() = 1 (NotReady)`，不是 `5`。就绪层没有判定硬件不兼容。**

### 4.2 就绪层

| 类 | IID | 方法槽（`*Statics`） |
|---|---|---|
| `Microsoft.Windows.AI.Imaging.TextRecognizer` | `3788c2fd-e496-53ab-85a7-e54a135824e9` | 6 GetReadyState / 7 EnsureReadyAsync / 8 CreateAsync |
| `Microsoft.Windows.AI.Imaging.ImageScaler` | 同上结构 | 6 / 7 / 8 |
| `Microsoft.Windows.AI.Text.LanguageModel` | `ILanguageModelStatics`（候选 IID 未逐一确证） | 6 / 7 / 8 |
| `Microsoft.Windows.Workloads.WorkloadManager` | `249826ba-1ddf-5983-9e3a-983bb11e7995` | — |

**包身份要求（重要）：**

| 类 | 未打包进程 | 打包应用内（AI Dev Gallery） |
|---|---|---|
| `Microsoft.Windows.AI.AICapabilities` | ❌ `REGDB_E_CLASSNOTREG` | ✅ 可激活 |
| `Microsoft.Windows.AI.Text.LanguageModel` | ❌ | ✅ |
| `Microsoft.Windows.AI.Imaging.TextRecognizer` | ❌ | ✅ |
| `Microsoft.Windows.AI.Imaging.ImageScaler` | ❌ | ✅ |
| `Microsoft.Windows.Workloads.WorkloadManager` | ❌ | ✅ |
| `Windows.AI.Management.Internal.AIComponentManager` | ✅ **任意进程可激活** | ✅ |

原因：前者由 AIFabric **框架包清单**注册，需要包图；后者注册在机器级 `ActivatableClassId`。

### 4.3 包解析层

`workloads.json`（以及 6 份平台变体）定义 `API 类 → SessionPackage` 映射。

**通用版（`workloads.json`）用无平台后缀的包：**

```
Microsoft.Windows.Vision.TextRecognizer
  → WindowsWorkload.TextRecognition.1_8wekyb3d8bbwe

Microsoft.Windows.Vision.ScreenRegionDetector
  → WindowsWorkload.ScrRegDetection.1_8wekyb3d8bbwe

Microsoft.Windows.SemanticSearch.SemanticTextEmbeddingsCreator
  → WindowsWorkload.SemanticText.1_8wekyb3d8bbwe
  → VectorSpaceId: 062DD372-42FB-445C-8BA1-CF99FABF6A6C
```

**平台版（如 `workloads.lnl.json`）用平台专属包：**

```
Microsoft.Windows.Vision.TextRecognizer
  → WindowsWorkload.TextRecognition.Lnl.1_8wekyb3d8bbwe
```

平台代号：`qnn`(Qualcomm) / `lnl`(Intel Lunar Lake) / `ptl`(Panther Lake) / `stx`(Strix/AMD) / `j32` / `365`(Windows 365)

**两个目标功能的完整包依赖：**

**Click to Do → `Windows.Workload.ContentExtraction`**

| 包 | 版本 |
|---|---|
| `WindowsWorkload.TextRecognition.1` | 1.2508.888.0 |
| `WindowsWorkload.ScrRegDetection.1` | 1.2509.1022.0 |
| `WindowsWorkload.ScrRegDetection.Data.1` | 1.2508.879.0 |
| `WindowsWorkload.Data.ContentExtraction.1` | 1.2509.1022.0 |
| `WindowsWorkload.Manager.1` | 1.2506.707.0 |
| `WindowsWorkload.PSOnnxRuntime.3.7` | 1.2509.1022.0 |
| `WindowsWorkload.SessionManager.1` | 1.2509.1022.0 |

**自然语言搜索 → `Windows.Workload.Analysis`**

| 包 | 版本 |
|---|---|
| `WindowsWorkload.SemanticText.1` | 1.2509.1022.0 |
| `WindowsWorkload.SemanticText.Data.1` | 1.7.817.0 |
| `WindowsWorkload.QueryProcessor.1` | 1.2509.1022.0 |
| `WindowsWorkload.QueryProcessor.Data.1` | 1.7.817.0 |
| `WindowsWorkload.QueryBlockList.1` | 1.2509.1022.0 |
| `WindowsWorkload.PSTokenizer.2.7` | 1.2509.1022.0 |
| `WindowsWorkload.PSTokenizerShared.3.7` | 1.2509.1022.0 |
| `WindowsWorkload.PSTokenizerShared.Data.3.7` | 1.2509.1022.0 |
| `WindowsWorkload.Data.Analysis.1` | 1.2509.1022.0 |
| `WindowsWorkload.Manager.1` | 1.2506.707.0 |
| `WindowsWorkload.PSOnnxRuntime.3.7` | 1.2509.1022.0 |
| `WindowsWorkload.SessionManager.1` | 1.2509.1022.0 |

**`PSOnnxRuntime` = ONNX Runtime = 跨硬件（CPU/GPU）执行后端。** 这是"NPU 不是必需"的直接证据。

### 4.4 获取层

**`Windows.AI.Management.Internal.AIComponentManager`**（`C:\Windows\System32\AIComponentMgmt.dll`）

实测方法表（机器级注册，**任意进程可激活**）：

| 路径 | 结果 |
|---|---|
| factory.slot[6]() | 返回 manager 实例 |
| manager.slot[6]() | `IVector<AIComponent>` —— **已安装组件列表（本机 = 0 项）** |
| manager.slot[7](HSTRING) | 返回 S_OK |
| manager.slot[8](HSTRING) | `IAsyncOperationWithProgress<AIComponentRemovalResult, AIComponentRemovalProgress>` —— **移除操作** |
| — | **没有任何"安装"方法** |

**`AIComponentMgmt.dll` 关键字符串：**
```
PE_CreateProductEnumerator
UupProducts / UupProduct / uupProductId
ms-uup://Product/
com.microsoft.windows.workload
Windows.Internal.StateRepository.PkgExtension
S-1-5-19 (LOCAL SERVICE)
```

**结论：`AIComponentManager` 只负责枚举与移除；获取走 UUP 产品通道。**

### 4.5 Windows Update 侧

**服务端点映射（从 ETL 日志提取）：**

| ServiceId | 标注 | 端点 |
|---|---|---|
| `9482F4B4-E343-43B6-B170-9A65BC822C77` | Microsoft Update | `https://fe2cr.update.microsoft.com/v6/ClientWebService/client.asmx`（SOAP 1.1 + authCookies） |
| `8B24B027-1DEE-BABB-9A95-3517DFB9C552` | **Third party service** | `https://fe3cr.delivery.mp.microsoft.com/ClientWebService/client.asmx` |
| `855E8A7C-ECB4-4CA3-B045-1DFA50104289` | Store | `https://tas01.cwsapp.update.microsoft.com/ClientWebService/client.asmx` |

**服务端能力清单（`GetConfig` 实测，fe3 与 fe3cr 相同）：**

```
ProtocolVersion                                    = 5.3
SyncUpdatesSupportsProductsSync                    = 1     ← 支持产品同步
SyncUpdatesSupportsTreatAppCategoryIdsAsInstalled  = 1
SyncUpdatesSupportsAdditionalFragments             = 1
SyncUpdatesSupportsCatalogSync                     = 0
MicrosoftPreferredCategoryIds = 0FA1201D-4330-4FA8-8AE9-B877473B6441;
                                E0789628-CE08-4437-BE74-2495B842F43B
MUUrl                                              = https://www.update.microsoft.com/v6
```

**workload 搜索的实际日志（10/12 19:30）：**

```
* START * Finding updates CallerId = MoUpdateOrchestrator Id = 2
Criteria = "(Product='Windows.Workload.ContentExtraction.amd64'
            and IsInstalled=0 and DeploymentAction=*)"
Product Targeting: 'PN=Windows.Workload.ContentExtraction.amd64&V=0.0.0.0'
Search Scope = {Machine}
Caller SID for Applicability: S-1-5-18
Service doesn't support product specific search.
Found 0 updates and 0 categories in search; evaluated appl. rules of 0 out of 0 deployed entities
```

**产品声明清单（10/13 新日志）：**

```
ProductAttributes(CTAC): PN=Client.OS.rs2.amd64&V=10.0.26300.9550&PrimaryOSProduct=1;
                        PN=Microsoft.NETFX.amd64&...;
                        PN=VisualStudio.Stable.x64&V=18.10.12224.181;
                        PN=VulnerableDriverBlocklist.amd64&V=0.0.0.0;
                        PN=Windows.OS.Emergency.MSI.amd64&IsEmergencyProduct=1&V=0.0.0.0
```

**`Windows.Workload.*` 不在这个清单里。**

### 4.6 ★ 突破：找到了 CTAC 产品声明的注册位置

**这是本轮调查最重要的发现。**

追踪 CTAC 清单里那个 `VisualStudio.Stable.x64`，定位到了它的注册位置：

```
HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo\
  ├─ Installed
  │    Client.OS.rs2.amd64            Version = 10.0.26300.9550
  │    Microsoft.NETFX.amd64          Version = 2400.26200.9347.1
  │    Windows.Appraiser.amd64
  │    Windows.AppraiserData.amd64
  │    Windows.Autopilot.amd64
  │    Windows.EmergencyUpdate.amd64
  │    Windows.OOBE.amd64
  │    Windows.OOBE.Cumulative.amd64
  │    Windows.OS.Emergency.CBS.amd64  Version = 0.0.0.0
  │    Windows.UpdateStackPackage.amd64
  ├─ DynamicInstalled
  │    Hammer.amd64                    Version = 0.0.0.0
  │    **osclient.coreai.amd64**        Version = 10.0.26100.9549   ← AI 外壳在这类
  │    OSClient.SxS.amd64              Version = 10.0.26100.9549
  │    SedimentPack.amd64              Version = 0.0.0.0
  │    UUS.amd64                       Version = 1510.2608.26052.0
  │    Windows.OS.Emergency.EXE.amd64  Version = 0.0.0.0
  │    {GUID}_amd64  × 12               Version = 0.0.0.0
  └─ PersistentDynamicInstalled
       DefenderPlatform.amd64          Version = 4.18.26080.4
       DefenderSignature.amd64         Version = 1.459.691.0
       MSRT.amd64                      Version = 5.145.26090.2001
       onedrive.amd64                  Version = 26.040.0301.0001
       RevocationList.amd64            Version = 0.0.0.0
       VisualStudio.Stable.x64         Version = 18.10.12224.181
       VulnerableDriverBlocklist.amd64 Version = 0.0.0.0
       Windows.OS.Emergency.MSI.amd64  Version = 0.0.0.0
```

**每个产品就是一个注册表键，键下只有一个 `Version`（REG_SZ）值。**

**CTAC 清单与这三类精确对应**（逐个核对：`Client.OS.rs2.amd64`、`Microsoft.NETFX.amd64`、`VisualStudio.Stable.x64`、`VulnerableDriverBlocklist.amd64`、`Windows.OS.Emergency.MSI.amd64` 的版本号完全一致）。

#### ✅ 已实验验证（10/13 12:31）

在 `DynamicInstalled` 下添加两个键：

```
Windows.Workload.ContentExtraction.amd64   Version = 0.0.0.0
Windows.Workload.Analysis.amd64            Version = 0.0.0.0
```

重启 `wuauserv`，触发 WU 扫描。**新 ETL 的 CTAC 里出现了：**

```
ProductAttributes(CTAC): PN=Client.OS.rs2.amd64&...;
                         ...
                         PN=Windows.Workload.Analysis.amd64;    ← ★ 出现了！
                         ...
```

**机制成立：`TargetingInfo` 就是"向服务端声明本机拥有哪些产品"的开关。**

#### ❌ 但仍未产生下载

| 检查 | 结果 |
|---|---|
| 服务端返回 | **`Found 0 updates`**（8B24B027 评估 124 个实体，返回 0） |
| `Product='...'` 专属搜索 | **未发生** |
| `AttemptedInstallCount` | **0 → 0** |
| 新包 | **0** |

**重启 `UsoSvc` + `wuauserv` + `WSAIFabricSvc` 并再次触发扫描后，仍然没有 workload 专属搜索。**

#### 结论

**声明产品 ≠ 请求产品。** WU 客户端会把它声明给服务端（现在已验证），但**不会主动去要它**。主动请求由 `MoUpdateOrchestrator` 的独立路径发起，而：

- 该路径的触发条件**仍未找到**
- 即使在 10/12 那次跑过，服务端也返回 0

### 4.7 StateRepository 调查（否定性结论）

用管理员权限获取了系统数据库副本：

```
C:\ProgramData\Microsoft\Windows\AppRepository\
  StateRepository-Machine.srd       8.4 MB  (+ -wal 2.8 MB)   SQLite / WAL
  StateRepository-Deployment.srd   15.7 MB  (+ -wal 5.7 MB)
```

**`StateRepository-Machine.srd` 里确实有产品注册表：**

```sql
CREATE TABLE UupProduct(
  _UupProductID INTEGER PRIMARY KEY, _Revision INTEGER,
  ProductID TEXT, Version INTEGER, Flags INTEGER, _Dictionary BLOB)

CREATE TABLE UupProductPackage(
  _UupProductPackageID INTEGER PRIMARY KEY, _Revision INTEGER,
  UupProduct INTEGER, PackageIdentity INTEGER, Flags INTEGER, _Dictionary BLOB)
```

**两张表都是 0 行（空）。**

**但关键是否定性证据**：CTAC 清单里有 `VisualStudio.Stable.x64`，而 `UupProduct` 是空的 —— **说明 CTAC 不是从 StateRepository 来的，而是从注册表 `TargetingInfo` 来的。**

（Deployment 库里 `File` 表那 80 个 "Workload" 命中，全是 AIFabric 包自身的文件如 `Microsoft.Windows.Workloads.dll`、`workloads.json`；`SemanticText` 那 3 条是某应用 node_modules 里的 Fluent UI 类型定义，均为误报。）

**→ 直接写 StateRepository 不仅风险高（WAL + 内存缓存 + 修订号），而且方向本来就是错的。**

---

## 5. 决定性实验记录

### 实验 1：资格 Hook（上一轮，已成功）

| 查询 | 修改前 | Hook 后 |
|---|---|---|
| Click to Do 功能资格 | false | **true** |
| Copilot+ 整机资格 | false | **true** |
| 发布开关 56114500 | true | 可改为 false |
| 未指定功能 0/2..7 | false | **保持 false** |
| HRESULT | S_OK | **保持 S_OK** |

**结论：资格布尔确实可伪造。但不能让功能运行。**

### 实验 2：`EnsureReadyAsync` 是否会触发下载（本轮）

**方法**：在 AI Dev Gallery 进程内，于 OCR 示例流程中同时观察：
- 注册表 `AttemptedInstallCount`
- WinRT 类激活
- 新加载模块
- 新装包

**结果：**

| 信号 | 结果 |
|---|---|
| `AttemptedInstallCount` | 0 → **0** |
| `AIComponentManager` 激活 | **无** |
| WU 相关激活/模块 | **无** |
| 新包 | **0** |
| `TextRecognizer.GetReadyState()` | **1 = NotReady** |
| `EnsureReadyAsync()` | 返回 `IAsyncOperationWithProgress<AIFeatureReadyResult, Double>` |

**实际出现的行为：**
```
[module+]  Microsoft.Windows.Workloads.dll
[activate] Microsoft.Windows.AI.Imaging.TextRecognizer
[activate] Windows.Security.Authorization.AppCapabilityAccess.AppCapability
[activate] Windows.Internal.CapabilityAccess.CapabilityAccess
[activate] Microsoft.Windows.Workloads.WorkloadManager
```

**结论：API 层调用不会触发任何获取动作。**

### 实验 3：`HardwareCompatibility=1` + 重启 wuauserv

| 检查 | 结果 |
|---|---|
| 设置后立即读 | 1 |
| 重启 wuauserv 后 | **保持 1**（未被写回） |
| `AttemptedInstallCount` | **仍为 0** |
| 新 ETL 里的 workload 搜索 | **没有出现** |
| 新包 | 0 |

**结论：**
- 正常 WU 扫描**不会**搜索 workload 产品
- `HardwareCompatibility=1` 单独**不触发**任何安装
- workload 搜索是**独立的编排器路径**，不是常规扫描的一部分

### 实验 4：服务端能力核查（本轮）

对 `fe3cr.delivery`（workload 服务）与 `fe3.delivery` 分别调 `GetConfig`：

**两者都返回 `SyncUpdatesSupportsProductsSync = 1`。**

**结论：客户端的 "Service doesn't support product specific search" 不是服务端能力缺失，而是客户端对"返回 0 条"的自我解读。**

---

## 6. 已验证 vs 未验证

### ✅ 已验证（可复现）

1. WU SOAP 协议完整可用，可从任意机器取得下载 URL（paint.net 实测）
2. `IsCopilotPlusPC` / `IsFeatureAvailable` 可在进程内翻转
3. 上报给服务端的 `DeviceAttributes` 是客户端可控字符串
4. `Windows.AI.Management.Internal.AIComponentManager` 任意进程可激活，其 API 仅枚举+移除
5. `Microsoft.Windows.AI.*` 类需要包身份（打包应用内可激活，普通进程 `REGDB_E_CLASSNOTREG`）
6. `TextRecognizer.GetReadyState()` = **1 (NotReady)**，非 5
7. `EnsureReadyAsync()` 可调用，返回异步操作；**但无安装动作**
8. 服务端 `SyncUpdatesSupportsProductsSync = 1`
9. 常规 WU 扫描不搜索 workload 产品
10. `HardwareCompatibility=1` 不触发安装
11. **★ `TargetingInfo` 是 CTAC 产品声明的来源** —— 加键后客户端确实声明了 `PN=Windows.Workload.Analysis.amd64`（ETL 实证）
12. **`StateRepository` 的 `UupProduct` / `UupProductPackage` 两表为空**，且 CTAC 非源自它
13. `StateRepository` 需管理员权限才能读取（副本可正常用 SQLite 打开）
14. **★ 服务端不解析 `<Products>` 的产品名** —— 乱写产品名与真实产品名返回完全相同的 28 项（对照实验）
15. **服务端对产品请求只返回 `Detectoid`/`Category`，全部 `IsLeaf=false`，0 个可下载文件名**

### ⚠️ 未验证 / 未完成

1. `EnsureReadyAsync` 异步完成后的**最终状态和结果**（上次测试被中断）
2. `WindowsWorkload.*` 包是否存在任何公开下载渠道 —— **未找到，但不能证明不存在**
3. WU `<Products>` 元素的**服务端正式 schema**（文本形式被接受但不解析；结构化形式一律 HTTP 500）
4. `MoUpdateOrchestrator` 发起 `Product='Windows.Workload.*'` 搜索的**触发条件**
5. `fe2cr` 端点（Microsoft Update）的配置 —— 需 SOAP 1.1 + authCookies，未取得
6. Windows 365 Cloud PC 路径（理论上可能提供 Copilot+ 环境）
7. 服务端"按产品名提供内容"的能力是否存在（可能只是客户端可用的接口形态下没有）

### ❌ 已排除

1. Microsoft Store 公开搜索（`manifestSearch` 对 WindowsWorkload / Windows.AI / TextRecognition 等均返回 0 条）
2. Microsoft Update Catalog（只有驱动类，无 AI 组件）
3. winget（msstore 源无结果）
4. NVIDIA/虚拟 NPU 类公开项目（核查后发现其桥接函数只有打印和 Sleep）
5. User-level / Machine-level WinHTTP 代理改道（WU 流量不走代理）

---

## 7. 工具清单

| 文件 | 作用 | 状态 |
|---|---|---|
| `wu_probe.py` | WU SOAP 客户端（端点/协议版本/分类/产品可配） | ✅ 可用 |
| `ms_store_download.py` | Store 包下载器（合规获取） | ✅ 实测可用 |
| `check_fe3cr.py` | 查询任意 WU 端点的 GetConfig | ✅ |
| `find_service_url.py` | 从 ETL 提取 ServiceId→URL 映射 | ✅ |
| `ro_activate_probe.py` | 按类名测试 WinRT 类可否激活 | ✅ |
| `ai_components.py` / `ai_mgr_scan.py` | 枚举 AI 组件 / 扫描 manager 方法槽 | ✅ |
| `frida_roget.py` | hook RoGetActivationFactory，抓取 (类名, IID) | ✅ |
| `frida_qi_test.py` | 用 QueryInterface 验证候选 IID | ✅ |
| `frida_copilot_hook.py` | 翻转 HasAICapability | ✅ |
| `frida_readiness_result.py` | 调用 GetReadyState / EnsureReadyAsync | ✅（异步轮询版有 bug） |
| `frida_ensure_final.py` | 非阻塞等待异步完成 | ⚠️ 未跑完 |
| `frida_activate_test.py` | 打包进程内激活测试 | ✅ |
| `observe_acquire.py` | 观察是否尝试获取包 | ✅ |
| `AI-Workload-Packages.ps1` | 从 Copilot+ PC 导出 / 安装 WindowsWorkload.* | 未在真机验证 |
| `ai-feature-feasibility.ps1` | 只读诊断 | ✅ |
| `xref_products.py` / `dump*.py` | PE 解析 / 反汇编辅助 | ✅ |

---

## 8. 结论与剩余选项

### 为什么改资格布尔没用

```
资格布尔（A 层）  = "门牌" —— 告诉 App 这台机器算不算 Copilot+
包投递（C 层）    = "发货" —— 由服务端按客户端声明的产品清单决定
```

**两者独立。改 A 不影响 C。**

### 闭环的本质

```
本机没装 WindowsWorkload 包
   ↓
AIComponentManager 枚举出 0 个组件
   ↓
客户端不声明 PN=Windows.Workload.*
   ↓
服务端没有理由返回该产品的更新
   ↓
搜索返回 0
   ↓
包装不上
```

### 剩余选项

| 选项 | 说明 | 成本 | 成功率 |
|---|---|---|---|
| **A. 攻 StateRepository 产品注册** | 让产品枚举器返回该产品，从而让客户端声明它 | 高（需 TrustedInstaller 级权限或 hook 系统服务） | 中低 |
| **B. 从真 Copilot+ 机器导出包** | 用 `AI-Workload-Packages.ps1` 搬运 | 需要一个外部资源 | **高** |
| **C. 走 Windows ML 公开路径** | 用微软公开的 Windows ML + 公开模型，在任意机器上跑 | 低 | **高**（但拿不到原生外壳） |

### 关于选项 C 的说明

微软把 AI 运行时**公开**在 NuGet 上，且明确支持老设备：

```
Microsoft.Windows.AI.MachineLearning
   Requirements: Windows 10 19H1 (build 18362) or later
   Includes: ONNX Runtime 1.30.0 + DirectML
```

```
Microsoft.AI.Foundry.Local        官方模型目录（可浏览/下载/运行）
Microsoft.WindowsAppSDK.AI        Windows AI API 层
Microsoft.AI.DirectML             GPU 执行提供程序
```

**这条路径不包含原生 Shell（Click to Do 右键菜单、Recall），但包含"能力"。**

---

## 9. 环境恢复记录

| 项目 | 状态 |
|---|---|
| `HardwareCompatibility` | 已改回 **0** |
| 机器级 CA（DSH WU Capture CA） | 已删除 |
| 用户级 CA | 已删除 |
| WinHTTP 代理 | 已复位为直连 |
| 用户级 IE 代理 | 已恢复（`ProxyEnable=0`） |
| 后台进程（Frida/Python/AIDevGallery） | 已全部清理 |
| `srd-copy`（系统数据库副本） | **已删除** |
| 系统 DLL / 驱动 / Secure Boot / HVCI | **全程未修改** |
| **⚠️ `TargetingInfo` 测试键** | **仍遗留，需手动清理**（见下） |

### ⚠️ 需要手动清理的两项

本轮提权在后期被会话策略禁用，导致两项未能自动回滚。

**1. 两个测试用产品注册键**（应删除）：

```
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo\DynamicInstalled\Windows.Workload.ContentExtraction.amd64
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo\DynamicInstalled\Windows.Workload.Analysis.amd64
```

以**管理员**身份运行：

```cmd
reg delete "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo\DynamicInstalled\Windows.Workload.ContentExtraction.amd64" /f
reg delete "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo\DynamicInstalled\Windows.Workload.Analysis.amd64" /f
```

**完整备份**（含修改前的全部分类）在：

```
C:\Users\jianm\Code\DeepseekHarness\targeting-backup\TargetingInfo-before.reg
```

如需恢复：`reg import "C:\Users\jianm\Code\DeepseekHarness\targeting-backup\TargetingInfo-before.reg"`

**2. 本地生成的 MITM CA 私钥**（建议删除，已从证书存储移除）：

```
C:\Users\jianm\Code\DeepseekHarness\mitm-ca\
```

**保留这两个键的后果**：本机将持续向 WU 服务端声明拥有两个不存在的产品，每次扫描都会多评估一次（当前实测为无害的返回 0）。**建议删除。**

---

## 10. 一句话总结

> **NPU 不是拦你的东西，"微软的服务器不给你发货"才是。资格检查能骗过，产品声明也能加上（都验证了），但服务端连你声明的产品名都不看 —— 它只回一堆判定规则，一个包都没有。**

---

## 12. 最终结论

**四个层次逐一验证，全部走通到"客户端侧能力边界"：**

```
① 资格布尔      → 可在进程内翻转 ✅     → 但只是"门牌"，不影响发货
② 就绪状态      → NotReady(1)，非硬件不兼容(5) ✅ → 系统认为"可以装，只是没装"
③ 产品声明      → TargetingInfo 加键即生效 ✅     → 客户端确实上报了该产品
④ 服务端请求    → 服务端不解析产品名 ❌           → 只返回判定规则，0 个包
```

**断点在 ④，而 ④ 在微软的服务器上，客户端已无任何可控变量。**

| 想要的 | 可行路径 |
|---|---|
| **原生外壳**（Click to Do 右键菜单 / Recall） | 只能从真正的 Copilot+ 机器导出模型包（`AI-Workload-Packages.ps1` 已就绪） |
| **AI 能力本身** | 走微软公开的 Windows ML + 公开模型，本机 CPU/GPU 完全够用 |

---

## 11. 直接请求实验（最后一条路，已做，结论为否）

在掌握 `TargetingInfo` 声明机制后，直接向 workload 服务手工构造请求，看服务端是否会因为"本机声明拥有该产品"而返回包。

**目标端点**：`https://fe3cr.delivery.mp.microsoft.com/ClientWebService/client.asmx`（`8B24B027` 服务）

### 11.1 承载位置的试探

| 变体 | 结果 |
|---|---|
| `<Products>PN=Windows.Workload.ContentExtraction.amd64&V=0.0.0.0</Products>` | ✅ 返回 50348 字符 / 28 个 UpdateID |
| `<Products><Product Id=".." Version=".."/></Products>` | ❌ HTTP 500（schema 不符） |
| `<Products><string>PN=..</string>...</Products>` | ❌ HTTP 500 |
| `<ProductAttributes>PN=..</ProductAttributes>` | 返回空结果（元素名被接受但无内容） |
| `CallerAttributes` 里追加 `PN=..&V=..` | ❌ HTTP 500 |
| `<Products/>`（空） | 返回 1012 字符 / 0 个 UpdateID |

**唯一有效形态**：`<Products>` 元素的**文本内容**为 `PN=<名称>&V=<版本>`。

### 11.2 ★ 对照实验（决定性）

对七个不同的产品名发送同一请求：

| 请求 | 响应长度 | UpdateID 数 | 类型分布 |
|---|---|---|---|
| `<Products/>`（空） | 1012 | 0 | — |
| `PN=ZZZ.NotAReal.Product.amd64&V=0.0.0.0`（**乱写**） | 50348 | 28 | Detectoid×20, Category×5 |
| `PN=Foo.Bar.Baz.x64&V=1.2.3.4`（**乱写**） | 50348 | 28 | 同上 |
| `PN=Windows.Workload.ContentExtraction.amd64&V=0.0.0.0` | 50348 | 28 | 同上 |
| `PN=Windows.Workload.Analysis.amd64&V=0.0.0.0` | 50348 | 28 | 同上 |
| `PN=osclient.coreai.amd64&V=10.0.26100.9549` | 50348 | 28 | 同上 |
| `PN=Microsoft.AIFabric.CBS.1.6&V=1.6.951.100` | 50348 | 28 | 同上 |

**七个请求返回的 UpdateID 集合完全相同。**

**结论：服务端不解析 `<Products>` 里的产品名。** 它只判断该元素是否为空：
- 空 → 返回 0 项
- 非空（无论内容）→ 返回**同一组固定的 28 个 Detectoid/Category**

### 11.3 返回内容的性质

对返回的 25 个 `<UpdateInfo>` 逐条解析其内嵌 `<Xml>`：

```
UpdateType 分布:  Detectoid  20
                  Category    5
IsLeaf:           全部 false      ← 没有任何真实包
FileName:         0 个            ← 没有任何可下载文件
Action:           全部 Evaluate
```

**全部是"适用性判定实体"和"分类"，没有一个是可下载的包。**

（`GetExtendedUpdateInfo2` 调用返回空结果，因为没有任何叶子更新可供查询详情。）

### 11.4 结论

**这条路的终点是明确的：**

| 环节 | 结果 |
|---|---|
| `TargetingInfo` 加键 → 客户端声明产品 | ✅ **已验证有效**（4.6 节） |
| 直接向服务端请求该产品 | ❌ **服务端忽略产品名**（11.2 节对照实验） |
| 任何路径下拿到真实包 | ❌ **从未出现 `IsLeaf=true` 或文件名** |

**服务端对该设备没有 `WindowsWorkload.*` 包可给，而且连"按产品名查询"这个能力都不存在（至少本客户端可用的接口形态下不存在）。**

**→ 至此，通过 Windows Update 获取模型包的路径全部走完，结论为否。**

### 11.5 还剩什么

| 选项 | 说明 | 成本 | 成功率 |
|---|---|---|---|
| **从真 Copilot+ 机器导出包** | 用 `AI-Workload-Packages.ps1` 搬运 | 需外部资源 | **高** |
| **走 Windows ML 公开路径** | 微软公开的运行时 + 公开模型 | 低 | **高**（但拿不到原生外壳） |
| 分析 MS 服务器为何不返回 | 已无客户端可控变量 | 极高 | 极低 |
