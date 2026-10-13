# Windows AI 模型包获取结果

获取日期：2026-10-13
目标机：Xiaomi Book Pro 16 2022 / i7-1260P / RTX 2050 / Windows 26300.9550 (26H2)
**全程只读取微软 CDN 字节，未安装任何包、未改注册表、未改服务**

---

## 一、总成果

```
合计 77 个原版 MSIX / 2847.5 MB
全量 Get-AuthenticodeSignature 验证：Valid 77 / 77，签名者 Microsoft Corporation
SHA1 与 MSU 内 WIM 资源表逐项一致     下载失败 0
```

| 来源 | 包数 | 体积 |
|---|---:|---:|
| KB5124010（新代 5.2 / EP 1.8） | 53 | 1981.4 MB |
| KB5066835（旧代 3.7，与本机匹配） | 24 | 866.0 MB |

输出目录：
- `ai-packages\` — KB5124010 的 53 个包
- `ai-packages-legacy\` — KB5066835 的 24 个包
- `ai-packages-inventory.json` — 完整清单
- `legacy-identified.json` — 旧 MSU 全部 56 个 GUID 包的**真实身份**映射

---

## 二、依赖闭包完整度

对本机 `C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe` 的 7 份 `workloads*.json` 逐项核对：

| 平台 | `Windows.Workload.ContentExtraction`（Click to Do） | `Windows.Workload.Analysis`（语义搜索） |
|---|---|---|
| **365** | **7 / 7　缺 0** ✅ | **12 / 12　缺 0** ✅ |
| **Lnl** | **7 / 7　缺 0** ✅ | **12 / 12　缺 0** ✅ |
| **Ptl** | **7 / 7　缺 0** ✅ | **12 / 12　缺 0** ✅ |
| Stx | 6 / 7（缺 `PSOnnxRuntime.Stx.3.7`） | 9 / 12 |
| 通用 | 3 / 7 | 6 / 12 |
| qnn / j32 | 缺 | 缺 |

**365 / Lnl / Ptl 三个平台已可直接进入安装实验。**

---

## 三、关键方法

### 3.1 定位原始分发位置

微软 OEM 指南说明 AI workloads 随 LCU 分发。本次两个 MSU：

| MSU | 大小 | 内容 |
|---|---:|---|
| `Windows11.0-KB5124010-x64.msu` | 4.69 GB | 53 个 `WindowsWorkload.*` MSIX（5.2 / EP 1.8 新代） |
| `Windows11.0-KB5066835-x64.msu` | 3.59 GB | 56 个 GUID 命名的 MSIX（3.7 旧代） |

**MSU 外层没有 AI 包名，必须在 WIM 资源表里找内嵌载荷。** 这是定位的关键。

### 3.2 免下载全量的字节提取

```
UUP 元数据 → MSU URL（HTTP Range 可用）
  → WIM 资源表（offset / size / sha1）
  → HTTP Range 取所选 payload 的完整字节
  → WIM 资源 SHA1 校验
```

**未下载任何完整 MSU**，只取所需区间。

### 3.3 ★ 廉价识别 GUID 命名的包（本次新增）

旧 MSU 的 56 个包文件名是 GUID，身份藏在包内 `AppxManifest.xml`。

**难点**：包最大 447 MB，逐个下载不可行。

**做法**：zip 的中央目录在文件末尾。实现一个由 HTTP Range 支撑的只读文件对象交给标准库 `zipfile`，它只需读 EOCD + 中央目录 + 目标条目。

**结果：56 个包全部识别，总共只取 0.12 MB。**

工具：`identify_legacy_packages.py`

---

## 四、重要技术发现

### 4.1 平台按「检测到的 NPU 类型」选择，不是 CPU

`Microsoft.Windows.Workloads.dll`：

```
导出 WorkloadManagerLoadWorkloadsUsingBrokerNpuType    ← 通过 broker 取 NPU 类型
     → NPUDetect\npudetect.dll : npudetect_detect_npu()
         → DXCore 枚举适配器，找描述含 "NPU Compute Accelerator Device" 的设备
     → 本机无 NPU → UnknownNpu → 加载通用 workloads.json
```

`npudetect.dll` 导出与符号：
```
npudetect_detect_npu / npudetect_detect_npugeneration
npudetect_get_driverversion / npudetect_get_version
class NPUDetector / NPUDetectorDXCore
字符串 ">NPU Compute Accelerator Device" / GenuineIntel / AuthenticAMD
```

**没有注册表覆盖开关。**

### 4.2 平台 → 包名映射

| JSON | `TextRecognizer` 指向 |
|---|---|
| `workloads.json`（本机默认） | `WindowsWorkload.TextRecognition.1` |
| `workloads.lnl.json` | `WindowsWorkload.TextRecognition.Lnl.1` |
| `workloads.365.json` | `WindowsWorkload.TextRecognition.365.1` |
| `workloads.stx.json` | `WindowsWorkload.TextRecognition.Stx.1` |

**本机默认选通用 JSON，而通用会话包在两个 MSU 里都不存在**（旧 MSU 只有通用的 **Data** 包，没有通用**会话**包）。这解释了为什么之前"本机默认期待的泛型包始终取不到"。

### 4.3 代际划分

| 代 | 运行时 | 出现在 |
|---|---|---|
| 3.7 | `PSOnnxRuntime.3.7` + `PSTokenizerShared.3.7` | KB5066835 |
| 5.2 | `WinMLShared.5.2` + `EP.*.Framework.1.8` | KB5124010 |

**本机全部 7 份 workloads JSON 引用的都是 3.7 代**，因此**旧 MSU 的包与本机匹配**，新 MSU 的包需要更新的 AIFabric 清单。

### 4.4 执行后端

`PSOnnxRuntime.Lnl.3.7`（包 `5a4c95f6-...`）内容：

```
ps-onnxruntime.dll               15.1 MB   ← 含 CPUExecutionProvider（内建）
openvino.dll                     13.9 MB
openvino_intel_npu_plugin.dll     2.8 MB
onnxruntime_providers_openvino.dll 1.1 MB
```

`ps-onnxruntime.dll` 内含 `CPUExecutionProvider` / `CPUAllocator` / `CPUDataTransfer`，说明**该运行时自带 CPU 执行后端**，NPU 插件是附加项。**但代码是否在 NPU 插件初始化失败时回退到 CPU，尚未验证。**

`WinMLShared.5.2` 内含 `onnxruntime.dll` 21.7 MB + `DirectML.dll` 18.7 MB。

### 4.5 包清单要点（以 TextRecognition.Lnl.1 为例）

```xml
<Framework>true</Framework>
<Dependencies>
  <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.22621.0" MaxVersionTested="10.0.26000.0" />
</Dependencies>                                    ← 零 PackageDependency

<accesscontrol:Register Sddl="O:SYG:SYD:(A;;GA;;;LS)" />   ← 注册表归 SYSTEM，仅 LocalService
<appdata:MachineFolder Sddl="(A;OICI;GA;;;LS)" />          ← 数据目录同权限

<Extension Category="windows.activatableClass.inProcessServer">
  <Path>TextRecognitionSession.dll</Path>
  <ActivatableClass ActivatableClassId="Microsoft.Windows.Internal.Vision.TextRecognizerSession" />
</Extension>

<uap17:PackageExtension Name="com.microsoft.windows.workload">
  <UupProducts>
    <UupProduct Id="Windows.Workload.ContentExtraction.LNL.amd64" />   ← 产品名带 LNL
  </UupProducts>
</uup17:PackageExtension>
```

---

## 五、逐包清单

### KB5124010（53 个，新代）

数据/会话（各平台）
```
0.05 MB  Data.Analysis.365.1 / .Lnl.1 / .Stx.1
0.05 MB  Data.ContentExtraction.365.1 / .Lnl.1 / .Stx.1
0.05 MB  Data.ImageSearch.365.1 / .Lnl.1 / .Stx.1
0.05 MB  Data.SettingsModel.Lnl.1 / .Stx.1
0.92 MB  ScrRegDetection.365.1 / .Lnl.1 / .Stx.1
0.81 MB  SemanticText.365.1 / .Lnl.1 / .Stx.1
0.86 MB  QueryProcessor.365.1 / .Lnl.1 / .Stx.1
0.67 MB  TextRecognition.365.1
17.15 MB TextRecognition.Lnl.1 / .Stx.1
0.35 MB  PSTokenizer.365.2.7 / .Lnl.2.7 / .Stx.2.7
1.30 MB  ImageSearch.365.3 / .Lnl.3 / .Stx.3
1.15 MB  ImageTextSearch.365.3 / .Lnl.3 / .Stx.3
3.30 MB  SettingsModel.Lnl.1 / .Stx.1
```

运行时/编排
```
0.43 MB  Manager.1                  v1.2511.1196.0
0.34 MB  SessionManager.1           v1.2608.951.0
2.32 MB  QueryBlockList.1
17.87 MB WinMLShared.5.2
52.80 MB PSTokenizerShared.365.5.2
26.41 MB PSTokenizerShared.Lnl.5.2 / .Stx.5.2
57.78 MB EP.Intel.OpenVINO.Framework.1.8
252.39 MB EP.AMD.VitisAI.Framework.1.8
```

数据（大）
```
16.94 MB  ScrRegDetection.Data.1
29.24 MB  SemanticText.Data.1
89.63 MB  QueryProcessor.Data.1
80.70 MB  ImageSearch.Data.3
81.21 MB  ImageTextSearch.Data.3
43.39 MB  ImageContentModeration.Data.1
448.48 MB SettingsModel.Data.1
638.22 MB PSTokenizerShared.Data.5.2
153.90 MB TextRecognition.Data.OPT.1
```

### KB5066835（24 个，3.7 代，与本机匹配）

```
0.29 MB  Manager.1                          v1.2506.707.0
0.36 MB  SessionManager.1                   v1.2509.1022.0
2.33 MB  QueryBlockList.1
5.49 MB  PSOnnxRuntime.365.3.7              ← 365 运行时
14.35 MB PSOnnxRuntime.Lnl.3.7
11.35 MB PSTokenizerShared.365.3.7
12.50 MB PSTokenizerShared.Lnl.3.7
0.33 MB  PSTokenizer.365.2.7 / .Lnl.2.7
0.77 MB  QueryProcessor.365.1 / .Lnl.1
0.85 MB  ScrRegDetection.365.1 / .Lnl.1
0.72 MB  SemanticText.365.1 / .Lnl.1
89.64 MB QueryProcessor.Data.1
16.78 MB ScrRegDetection.Data.1
29.24 MB SemanticText.Data.1
81.75 MB TextRecognition.365.1              v1.2508.888.0  ← 精确匹配 workloads.365.json
638.44 MB PSTokenizerShared.Data.3.7
0.05 MB  Data.Analysis.365.1 / .Lnl.1
0.05 MB  Data.ContentExtraction.365.1 / .Lnl.1
```

---

## 六、仍未取得

| 包 | 平台 | 说明 |
|---|---|---|
| `TextRecognition.1` / `ScrRegDetection.1` / `SemanticText.1` | 通用 | **两个 MSU 中都不存在**；旧 MSU 只有通用 Data 包，无通用会话包 |
| `PSOnnxRuntime.3.7` / `PSTokenizer.2.7` / `QueryProcessor.1` / `Data.Analysis.1` / `Data.ContentExtraction.1` | 通用 | 同上 |
| `*.Qnn.*` / `*.J32.*` | Qualcomm | 不在这两个 MSU |
| `TextRecognition.Stx.1` (v1.2508.888.0, 210MB) / `PSOnnxRuntime.Stx.3.7` (87.6MB) | Stx | 未下载（可补） |
| `PSTokenizerShared.Stx.3.7` | Stx | 未下载（可补） |

---

## 七、工具清单

| 工具 | 作用 |
|---|---|
| `fetch_all_ai_payloads.py` | 从 KB5124010 批量提取（支持 `--only`/`--max-size`/断点续传） |
| `fetch_legacy_payloads.py` | 从 KB5066835 按包名/预设提取（`--preset core/365/lnl`） |
| `identify_legacy_packages.py` | **廉价识别 GUID 命名包**（56 包仅取 0.12 MB） |
| `coverage.py` | 各平台依赖闭包覆盖度分析 |
| `inventory.py` | 生成完整清单 JSON |
| `check_url.py` | 检查 CDN URL 有效期 |
| `legacy-identified.json` | 56 个 GUID → 真实包名映射 |
| `ai-packages-inventory.json` | 77 个包清单 |

---

## 八、下一步可选方向

1. **补齐 Stx 平台**（约 300 MB）→ 四个平台全覆盖
2. **尝试安装 365 或 Lnl 平台包**，验证：
   - `Add-AppxPackage` 是否需要计划任务模式
   - `windows.packageExtension` 是否能让 `WorkloadManager` 找到它
3. **解决平台选择问题**：让系统加载 `workloads.365.json` / `workloads.lnl.json`
   - 选择走 broker（`WorkloadManagerLoadWorkloadsUsingBrokerNpuType`），可能存在可拦截点
4. **继续找通用平台包**：查其他 LCU
5. **验证 CPU 回退**：`ps-onnxruntime.dll` 是否在无 NPU 时回退 CPU
