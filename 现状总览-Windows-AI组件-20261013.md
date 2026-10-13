# 现状总览：让非 Copilot+ 电脑用上 Copilot+ 功能

> **写完时间**：2026-10-13 21:35
> **电脑**：小米 Book Pro 16 2022 / i7-1260P（**物理上没有 NPU**）/ 16GB / Windows 11 build 26300.9550
> **工作目录**：`C:\Users\jianm\Code\DeepseekHarness`
> **这份文档的作用**：把之前 8 份文档 + 另一个 AI 的调查 + 今天的抓包实验结果**合在一处**。看完这一份，不用再翻别的。
> **写法说明**：不绕弯、不堆术语。凡是"确定"的都有实测证据，凡是"猜的"我都会明说是猜的。

---

# 一、先说结论（三句话）

1. **包我们都拿到了、也装上了，但系统不认账。**
2. **不认账的原因已经查到最底层的一环**：系统去装 AI 组件时，先做一个"**这个产品对这台机器适用吗**"的检查，检查结果是**不适用**，于是整个流程卡死（不是下载失败，是被判定不合格）。
3. **所有"骗过检查"的常规手段都已试过且失败**（改注册表、改数据库、假装自己是 AI PC、改配置指向我们有的包……）。剩下真正没打过的只有两处：**系统要的那个"名字"为什么不出现**，和**"适用性"这个判定到底读什么数据**。

---

# 二、目标是什么

| 级别 | 想要的效果 | 怎么算成功 |
|---|---|---|
| **L1** | Windows AI API 能调用 | `TextRecognizer.GetReadyState()` 返回 `0 (Ready)` |
| **L2** | 原生功能能用 | 右键"单击以执行"(Click to Do) 真能 OCR；Recall 能记录 |

**用户明确要求**：不要自己写 OCR 工具、不要自训模型——要的是**可复用的原生绕过方法**；网上没有现成方案不算停下来的理由。

---

# 三、现在到底卡在哪（大白话版）

系统要装 AI 组件，必须连过**三道门**：

```
第一道门：包在不在、装给谁了
    → 我们：19 个包都在，其中 11 个装给用户、6 个只是"暂存"、7 个已装给 LocalService
    → 这一道基本能过（剩下几个没装全，可以补）

第二道门：系统按名字找包
    → 系统喊的名字是【通用名】：WindowsWorkload.Data.ContentExtraction.1
    → 我们手里的包叫【平台名】：WindowsWorkload.Data.ContentExtraction.365.1 / .Lnl.1
    → 通用名的包在微软两代更新包里【根本不存在】（我们翻遍了）
    → 这道门走不通：名字对不上

第三道门：产品适用性检查（★ 真正的死点）
    → 系统问自己："uup://Product/Windows.Workload.ContentExtraction.amd64 这台机器能用吗"
    → 答案："不适用"（错误码 0x80073D3B）
    → 于是卡死，并且【永远等不到结果】——API 就一直转圈（挂起）
```

**关键点**：第一、二道门我们还能动手（补装、改名），**第三道门会把前两道门的努力全部作废**——这就是为什么"装包、写注册表、伪造 AI PC"都白费。

---

# 四、今天的完整链路（每一环都有实测证据）

```
App 调用 TextRecognizer.EnsureReadyAsync()
  │
  ├─ 1. 检查能力声明（CapabilityAccess）        ✅ 通过
  ├─ 2. 检查用户上下文（UserManager）           ✅ 通过
  │
  ├─ 3. 交给 WSAIFabricSvc（系统服务，LocalService 账户）接管
  │     │
  │     ├─ 3a. 拉起 Windows Update 编排器（MoUsoCoreWorker）
  │     │      → 向 fe3cr.delivery.mp.microsoft.com 发 SOAP 请求（18138 字节）
  │     │      → 请求里写着："要产品 PN=Windows.Workload.ContentExtraction.amd64（任意版本）"
  │     │      → 同时上报 84 项设备信息，其中包括【IsA9CapablePC=0】= "我不是 AI PC"
  │     │      → 服务器回 HTTP 200，内容为空（没有更新）
  │     │      → ★ 而且客户端收到后就关连接了，根本没读这个回应
  │     │
  │     ├─ 3b. 走 AppX 部署：uup://Product/Windows.Workload.ContentExtraction.amd64
  │     │      → ❌ 0x80073D3B「产品不适用」   ← ★ 死在这里
  │     │      （失败位置 deploymentrequest.cpp 2503/2908，发起人 = WSAIFabricSvc）
  │     │
  │     └─ 3c. 按通用家族名注册包
  │            WindowsWorkload.Data.ContentExtraction.1  → ❌ 这个包不存在
  │
  └─ 4. 异步操作永远不完成 → 一直转圈（90 秒以上仍是"进行中"）
```

---

# 五、确定的事实清单

## 5.1 包与安装状态

| 项目 | 状态 |
|---|---|
| 官方签名 MSIX | **77 个**，2985.8 MB，`C:\Users\jianm\Downloads\Windows-AI-包\`（签名全部为 Microsoft） |
| 已装 `WindowsWorkload.*` | **19 个**，Status 全 Ok |
| 账户分布 | ✅ **19 个全部注册给 `S-1-5-19`(LocalService) = Installed**（22:02 补注册完成；此前是 11 个用户 + 6 个仅 SYSTEM 暂存 + 7 个 LocalService） |
| 当前 `workloads.json` | 已被改成"最小 365 版"（17:03，重启后仍在） |
| 需要的家族 | **23 个**；其中 **8 个本机完全没有**；**6 个只是 Staged** |
| 原始（备份）config | 需要 **39 个家族，缺 36 个** |

**8 个缺失家族**：
```
Analysis 缺 4：PSTokenizerShared.Data.3.7 / QueryBlockList.1 / QueryProcessor.Data.1 / SemanticText.Data.1
ImageSearch 缺 5：ImageContentModeration.1 / ImageContentModeration.Data.1 /
                  ImageSearch.Data.3 / ImageTextSearch.Data.3 / PSTokenizerShared.Data.3.7
```

## 5.1b ★ 补注册实验（2026-10-13 22:02–22:05，已完成）

**做了什么**：把 config 需要、但当时只属于用户或仅 SYSTEM 暂存的 **12 个包**，以 **LocalService 身份**注册。
**怎么做的**（可复现，脚本在 `.dsh-tmp\lsvc-register.ps1` + `run-lsvc-register.ps1`）：
```
1. 建计划任务，主体 = S-1-5-19 / LogonType=ServiceAccount / RunLevel=Limited
2. 任务里执行 Add-AppxPackage -Register "<安装目录>\AppxManifest.xml" -DisableDevelopmentMode
   （备选路径是 PackageManager.RegisterPackageByFullNameAsync，但它的 1 参数重载不存在，
     3 参数版在 PowerShell 里做 IAsyncOperation 等待会失败 → 最终用 Add-AppxPackage -Register 成功）
3. 任务跑完即删除
```
**结果**：12/12 成功；**19/19 个 `WindowsWorkload.*` 包现在都是 `S-1-5-19=Installed`**（SYSTEM 暂存状态全部消失）。
**然后实测接口**（全新重启的 App 进程，22:04）：

```
GetReadyState      = 1 (NotReady)      ← 没有变化
EnsureReadyAsync   = 调用成功，但 20 秒后仍是 Started（挂起）  ← 没有变化
```

→ **"包没注册给正确账户"这个变量已被实测排除。** 卡点在它上游（通用名字 + 适用性判定）。

## 5.1c ★ 补齐闭包（22:23）—— 那 8 个"缺失家族"其实在归档里

**发现**：扫归档时发现，config 缺的 8 个家族**在 77 包归档里全都有**，只是当年没装。于是用
`Add-AppxProvisionedPackage -Online -SkipLicense` 装上，再以 LocalService 身份注册。

**结果**：
```
装包前：23 个必需家族里 8 个"完全没有"、6 个"仅 SYSTEM 暂存"
装包后：8 个全部装入；再注册给 LocalService
最终：27 个 WindowsWorkload 包，全部 S-1-5-19 = Installed
      config 三个工作负载 missing = 0（ContentExtraction 7/7、Analysis 12/12、ImageSearch 12/12）
```
→ **config 闭包 100% 齐全 + 全部注册给服务账户。这一步也做完了。**

## 5.1d ★ UUP 产品部署对照实验（22:35，关键阴性结果）

**方法**：用公开 API `PackageManager.AddPackageByUriAsync(uup://Product/<id>, AddPackageOptions)`
自己发起部署（这个 API **接受 `uup://` 方案**），分别请求 5 个产品名。

| 请求的产品 ID | 结果 | 耗时 |
|---|---|---|
| `Windows.Workload.ContentExtraction.amd64`（系统要的通用名） | ❌ **0x80073D3B** | 11.5 s |
| `Windows.Workload.ContentExtraction.365.amd64`（我们的平台包） | ❌ **0x80073D3B** | 30.2 s |
| `Windows.Workload.ContentExtraction.LNL.amd64` | ❌ **0x80073D3B** | 22.1 s |
| `Windows.Workload.Analysis.365.amd64` | ❌ **0x80073D3B** | 18.9 s |
| **`ZZZ.NotAReal.Product.amd64`（完全乱写）** | ❌ **0x80073D3B** | 10.5 s |

**三条结论：**
1. **平台包用 UUP 请求，报的错和通用包一模一样**（都是 0x80073D3B）。
2. **一个完全乱写的产品名，报的错也一样** → 这个错误码**不区分**"产品存在但设备不合格"和"根本没有这个产品"。
   它的原文就是"**产品不适用或找不到**"（not applicable **or** not found）——两种含义本来就没分开。
3. **耗时差别有信号**：平台名（18–30 s）明显比乱写名（10.5 s）慢 —— 说明平台名**被识别了、走了更多解析步骤**，但最终仍不"适用/可解析"。

→ **推论**：`uup://Product/<id>` 的成功与否，取决于**本地是否存在该产品的有效记录**（产品→包的映射 + 元数据），
而不是"这台设备够不够格"。这正好回到当年那件事：手写的 `UupProduct` 行 `_Dictionary = NULL` —— 很可能就是缺的那一块。

## 5.2 "通用名" 这条路是死的

实测 6 个通用家族**一个都不存在**：
```
WindowsWorkload.Data.ContentExtraction / TextRecognition / ScrRegDetection / Manager / SessionManager / Analysis
```
而系统开口要的就是通用名 → 永远找不到。

## 5.3 Windows Update 那一侧（今天新做的实验）

- **抓到了完整请求**：`POST fe3cr.delivery.mp.microsoft.com/ClientWebService/client.asmx`，18138 字节 SOAP，`SyncUpdates`。
- 请求里明确写着要 **`PN=Windows.Workload.ContentExtraction.amd64&V=0.0.0.0`**（就是那个不存在的通用名）。
- 上报的设备信息有 **84 项**，包括 CPU 型号、OEM 型号、固件版本、内存、AI Fabric 版本，以及 **`IsA9CapablePC=0`**。
- `IsA9CapablePC` 在系统文件 `ctac.json` 里的别名就是 **`aipc`（AI PC）**。**服务器不用猜，我们直接告诉了它"我不是 AI PC"。**
- **我们自己伪造了 13 种请求**（改成 AI PC、换成平台产品名、换成真实产品名、伪造 NPU、去掉 cookie……）→ **服务器一律回答"没有更新"**，连真实产品名也一样。
- 结论：**服务端这条路也不是"讨要"能拿到的**；而且客户端自己都**不读**服务器回的响应——说明它压根不是在等下载。

## 5.4 平台选择（决定系统用哪套包）

- 系统根据 `NpuType`（None / Qnn / Lnl / Stx / Win365）决定读哪份 `workloads*.json`。
- 本机无 NPU → 选"通用" → 于是要通用名的包 → 而通用包不存在。
- 我们试过 hook NPU 检测（AmperageKit 的老办法）：**`NPUDetect.dll` 在整个调用过程中从未被加载**（平台判断在服务启动早期就做完了并缓存）。
- 而且发现 **AmperageKit 当年打错了导出**：它 patch `npudetect_detect_npugeneration`，但实际被调用的是 **`npudetect_detect_npu`**。

## 5.5 "适用性判定"就是那道死门

```
ErrorCode           = 0x80073D3B
说明                = [UUP product Windows.Workload.ContentExtraction.amd64 is not applicable]
失败位置            = deploymentrequest.cpp:2503 / :2908
发起进程            = svchost.exe,WSAIFabricSvc
```
**这是"不合格"的判定，不是"没下载到"。** 它发生在部署前置校验层，比"包装给谁"更靠前。

## 5.6 已经确定能用的东西（唯一的正面成果）

**`oneocr.dll`（微软 OCR 引擎）在无 NPU 的 CPU 上跑通 5/5**，置信度 0.97–1.00。
它本来就在本机：`Microsoft.ScreenSketch`（截图工具的"文本操作"就是它）、Photos、GamingApp。
→ 有完整 FFI 签名和模型解密 key（见 §八）。

## 5.7 Recall 是岔路

`Recall` 在本机是"按需功能"（`DisabledWithPayloadRemoved`），x64 的功能定义 `.mum` 在，但 WinSxS 里**没有载荷**。它还有独立的安全栈（BitLocker + Windows Hello ESS + VBS），和 Windows AI API 是两条独立的难关 → **放弃此路**。

---

# 六、已经被证明没用的做法（别再试了）

**本地注册类**（全部无效）：
1. 写 `UUPProducts\<产品ID>`（官方格式）
2. 写 `TargetingInfo\DynamicInstalled\<产品ID>`
3. 写 NPU 芯片 GUID 注册表（DWORD / REG_SZ 都试过）
4. 建 `Pinned\<家族名>`（19 个）
5. 建 `ApplicationData\<家族名>\Machine` + LocalService ACL
6. 手写 StateRepository 的 `UupProduct` / `UupProductPackage` 表（3 行 / 22 行）
7. 假装自己是 AI PC（翻转 `IsA9CapablePC` / 伪造 NPU 属性）—— **今天用真实请求实测，服务端照样不发**

**服务端请求类**：
8. WUA COM API 定向查询（各种产品名、各种条件、两个端点）
9. 我们自己伪造 SOAP 请求（13 种变体）—— **一律拿到"没有更新"**

**其它**：
10. 整机重启、重启相关服务、开发者模式、以 SYSTEM 注册、LocalService 计划任务
11. 反编译 `AIComponentMgmt.dll` 想找开关（它疑似只是"设置 → AI 组件"页面的数据提供者，不在主链路上）

**第三方工具**：唯一真正成功过的 **AmperageKit 只有 ARM64 版**，2024-06 后停更；作者原话是"检查代码已经内联进每个系统组件，骗不了了"。**x86_64 上公开的成功记录为零。**

---

# 七、还剩哪些路（按性价比排序）

| 顺序 | 要做什么 | 大概成本 | 成功的可能性 | 说明 |
|---|---|---|---|---|
| **1** | ✅ **已做（22:02）**：把当时仍未注册给 LocalService 的 12 个包补注册 → 19/19 全部 `S-1-5-19=Installed`；重测结果**仍为 `1 (NotReady)` + 挂起** | 已完成 | — | **用实测排除了"账户注册不够"这个变量**（预测被证实） |
| **2** | 补齐 8 个缺失家族 | 半小时 | 低 | 闭包不完整是硬伤，但补完也过不了第三道门 |
| **3** | **查清"通用名"这个名字从哪来**；或把 `.365` 包**改名重打包成通用名**再装 | 中 | **中** | 唯一能同时满足"系统要的名字"和"我们有包"的做法；打包后签名是难点 |
| **4** | **攻"适用性判定"**：`0x80073D3B` 到底读什么数据才判"不适用" | 高 | **中** | **这是真正的死门**，也是唯一还没被打开的门 |
| **5** | **拿一台真 Copilot+ 电脑做对照**（演示机 / 恢复镜像） | 看机会 | **高**（信息量） | 能一次性拿到"正确答案长什么样"，消除大量猜测。仍是最有价值的一手资料 |
| 6 | 放弃系统集成，基于 `oneocr` 做能力层 | 中 | 高（能出效果） | 用户明确说过不要自写工具 → **只作备选，需你拍板** |

---

# 八、关键信息速查

```
# oneocr 模型解密 key
kj)TGtrK>f]b[Piow.gU+nC@s""""""4

# 死点错误码
0x80073D3B  = 产品不适用（UUP product ... is not applicable）
部署 URI    = uup://Product/Windows.Workload.ContentExtraction.amd64

# 系统要的通用名 vs 我们有的平台名
WindowsWorkload.Data.ContentExtraction.1        ← 系统要，不存在
WindowsWorkload.Data.ContentExtraction.365.1    ← 我们有
WindowsWorkload.Data.ContentExtraction.Lnl.1    ← 我们有

# 平台选择
NpuType = None, Qnn, Lnl, Stx, Win365, Unknown
配置文件：C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\workloads*.json（7 份）

# 数据库
C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd（SQLite）

# CTAC 属性定义（AI PC 就在这里）
C:\Windows\System32\ctac.json
    "aipc": "s:IsA9CapablePC"        ← AI PC 属性
C:\Windows\System32\CtacWorker.exe   ← 属性值组装者

# Copilot+ 判定实现（新线索）
C:\Windows\System32\WSAIFabricHost.dll
    SessionManagerBrokerCoPilotPlusDetection / ...GateOverride / ...NPUGateBlocked
    （AI Fabric 包里有 ProxyStub → 是可以通过 IPC 调用的接口）
C:\Windows\System32\Windows.Internal.AI.PlatformCapability.dll

# WU 请求端点
https://fe3cr.delivery.mp.microsoft.com/ClientWebService/client.asmx
票据 = 微软签发的 JWE（RSA-OAEP + A128CBC-HS256），有效期 5 分钟，只能抓用、不能自己造
```

---

# 九、这台机器被改了什么 / 怎么还原

| 项目 | 现状 | 还原方法 |
|---|---|---|
| 19 个 `WindowsWorkload` 包 | 已装（11 用户 / 6 暂存 / 7 LocalService） | `Remove-AppxPackage -AllUsers` |
| `workloads.json` | 已改成最小 365 版 | 备份在**同目录** `workloads.json.orig-backup` |
| 注册表 `UUPProducts` / `Pinned` / `DynamicInstalled` | 有我们写的条目 | 删对应子键 |
| StateRepository `UupProduct` 表 | 手写 3 行 / 22 行 | 备份 `srd-before-uupwrite.srd` |
| NPU 注册表 | 已还原原值 | — |
| `ApplicationData` / `AppRepository` 所有权 | 已改为 Administrators（原 TrustedInstaller） | ⚠️ 唯一需要注意的副作用 |
| 服务 | 相关服务运行正常，启动类型未改 | — |

---

# 十、文档与资产索引

## 10.1 阅读顺序（重要）

| 顺序 | 文档 | 内容 |
|---|---|---|
| **1** | **本文档** | 现状总览（整合版） |
| 2 | [交接文档-完整已知信息与操作记录.md](交接文档-完整已知信息与操作记录.md) | 18:03 的详细交接（16 节，最全的技术细节） |
| 3 | [交接文档-补充-20261013-2040.md](交接文档-补充-20261013-2040.md) | 18:03–20:11 的工作（ETW 抓到死点、WU 对照实验） |
| 4 | [抓包结果-AI-PC属性门控-20261013.md](抓包结果-AI-PC属性门控-20261013.md) | 20:57–21:26：完整 SOAP、84 项设备属性、13 组变体请求实验室 |
| 5 | [交叉核对-对方AI结果-20261013.md](交叉核对-对方AI结果-20261013.md) | 与另一个 AI 结果的实测核对 |
| 6 | [可行性评估与踩坑记录.md](可行性评估与踩坑记录.md) / [第四阶段报告-外部调研与战略结论.md](第四阶段报告-外部调研与战略结论.md) / [第五阶段-走法A推进状态报告.md](第五阶段-走法A推进状态报告.md) / [安装实验报告.md](安装实验报告.md) | 早期评估与实验报告 |
| 7 | [从微软服务器提取AI包-方法文档.md](从微软服务器提取AI包-方法文档.md) / [AI包获取结果.md](AI包获取结果.md) | 77 个包的提取方法与清单 |
| 8 | [Windows-AI-CopilotPlus-调查报告.md](Windows-AI-CopilotPlus-调查报告.md) | ⚠️ 最早的调查报告，**部分结论已被证伪**，只作历史参考 |

## 10.2 实测证据

| 位置 | 内容 |
|---|---|
| `capture-http\soap-request.bin` / `.xml` | 抓到的真实 WU 请求（18138 字节） |
| `capture-http\device-attributes.txt` | 84 项设备属性解码表 |
| `capture-http\replay\` | 请求实验室：带票据的模板 + 13 组变体的服务器响应 |
| `capture-http\server-response-SyncUpdatesResponse.xml` | 服务器应答样本（空结果） |
| `.dsh-tmp\sid-verify.txt` / `cross-ref.txt` / `pkg-verify.txt` | 包账户状态 / config 需求交叉表 / 缺口统计 |
| `C:\Users\jianm\Downloads\Windows-AI-包\` | 77 个 MSIX 最终归档 |

## 10.3 可复用脚本

| 脚本 | 作用 |
|---|---|
| `.dsh-tmp\hook_wu_http2.py` | 抓 wuauserv 的 WinHTTP 请求（原始版） |
| `.dsh-tmp\hook_wu_rewrite.py` | 抓包 + **任意改写请求体**（换产品名、改属性） |
| `.dsh-tmp\hook_wu_template.py` | 抓"模板 + 新鲜票据"（供自建请求复用） |
| `.dsh-tmp\wu_post_variants.py` | **自己发 WU 请求并读响应**（本批 13 组变体） |
| `.dsh-tmp\trigger_ensure.py` | 在 AI Dev Gallery 里调用 `EnsureReadyAsync` |
| `.dsh-tmp\run-capture2.ps1` / `run-rewrite.ps1` / `run-template.ps1` | 一键编排（提权运行） |

## 10.4 会话抢救方法（防止再次丢上下文）

DSH 的会话记录在 `C:\Users\jianm\.dsh\sessions\<工作目录>\<会话ID>\session.v4.jsonl.zstd`。
它是 **zstd 多帧拼接**文件，`zlib.zstdDecompressSync` 只能解第一帧——需要**按帧魔数 `28 B5 2F FD` 切帧**逐帧解压（Node.js v24 内置 zstd；Python 没有 `zstandard`）。
已解出的可读全文：`.dsh-tmp\session-*.convo.md`（上一轮 67 轮对话完整恢复）。

---

# 十一、必须遵守的踩坑规则

| # | 规则 |
|---|---|
| 1 | **所有 `.ps1` 必须纯 ASCII**（PowerShell 5.1 按 GBK 读，中文注释会吃掉下一行） |
| 2 | 提权一律 `sudo -N powershell -NoProfile -ExecutionPolicy Bypass -File <脚本>`；**必须加 `-N`**（内联模式返回 exit 5） |
| 3 | **不要随便 detach Frida 会话**——会让 `wuauserv` 崩溃（错误模块 `frida-agent.dll`）。正确做法：**跑完直接 `sc stop wuauserv`**，让 agent 随进程销毁 |
| 4 | 读内存前必须校验地址可读（`Process.findRangeByAddress`），否则会把服务打崩 |
| 5 | `AIDevGallery` 每次调用 `EnsureReadyAsync` 后约 90 秒 **fail-fast 自杀** → **一次 App 启动 = 一枪** |
| 6 | `WinHttpSendRequest` 参数：`args[1]/[2]` 是 headers，`args[3]/[4]` 才是 body；搞错会崩服务 |
| 7 | 结论必须配对照实验；"X 无效"必须有否证 |
| 8 | 研究结论要标清【已实测】/【推断】/【未知】，别把推断当结论（**这份整合文档已经纠正了 3 处此前的错误结论**） |

---

# 十二、此前文档中已确认错误的结论（避免误导）

| 曾经的结论 | 实际情况 |
|---|---|
| "三个 365 工作负载闭包 100% 齐备" | ❌ **错**。Analysis 缺 4 个、ImageSearch 缺 5 个（共 8 个家族缺失） |
| "19 个包全部安装走通" | ❌ 过强。账户级注册不完整：6 个仅 SYSTEM 暂存 |
| "`EnsureReadyAsync` 失败" | ❌ 错。是**挂起**（永远等不到完成），而且它**根本不读** WU 的响应 |
| "系统按通用平台查找包（推断）" | ✅ **已实测证实**（抓包 + AppX 事件） |
| "AmperageKit 通过 patch `npudetect_detect_npugeneration` 伪造 NPU" | ⚠️ 打偏了。实际被导入/调用的是 **`npudetect_detect_npu`** |
| "x64 的 Recall 载荷从未发布" | ❌ 错。x64 的 `.mum` 定义在本机（载荷被移除） |
| "通用 `workloads.json` 是占位配置、通用包从未发布" | ✅ 支持（服务端 13 组变体全空 + 两代 LCU 无通用包） |
