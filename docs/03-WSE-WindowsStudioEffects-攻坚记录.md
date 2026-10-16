# Windows Studio 效果：无 NPU 电脑启用、CPU 适配与服务固化指南

> 2026-10-16 仓库审核补充：本文是原本机发布包的完整使用指南。Git 只收录该包的自编写源码和管理脚本，位于 `studio-cpu/`，没有预编译工具/运行库。请先按 [源码与资产重建](06-源码与资产重建.md) 补齐，不能把“克隆仓库”当成“已取得本文工具包”。2026-10-16 只读检查确认两个服务运行且桥接 active，但原部署记录仍是 rebootVerified=false；未据此冒充重启后的效果验收。

更新：2026-10-15。本文对应同目录提供的 `StudioEffects-CPU-Service-2026-10-15` 工具包。

## 1. 先看能做到什么

这套方案已经在一台没有 NPU 的 Intel 第 12 代笔记本上，实现 Windows 原生 Studio 面板中的自动取景和背景模糊。用户已确认视觉效果；相机服务内的模型推理也已验证。

本轮又将临时 Hook 改造成独立的开机自启服务。服务重启、工作进程异常退出自动恢复，以及恢复后的连续 5 秒录像均已验证。用户确认服务模式下两项效果仍正常。

**目前不能承诺“所有电脑、所有 Studio 效果都可用”。** 本文提供的是完整、可复现的研究方案，并把支持边界、未验证部分和失败时的处理写清楚。

| 项目 | 当前状态 |
|---|---|
| Intel Core i7-1260P、无 NPU | 已实机验证 |
| Windows 11 x64，26300.9550 | 已实机验证 |
| Xiaomi USB 摄像头，VID 1BCF / PID 2D03，NV12 1280×720 | 已实机验证 |
| 其他 Windows 11 x64 电脑和 USB 摄像头 | 迁移候选；需要按本文逐层验证 |
| AMD x64 CPU | 未实机验证，不能由“x64”直接推断成功 |
| ARM64 Windows、32 位 Windows | 当前工具包不适用 |
| 非 USB / MIPI / IPU 摄像头 | 当前安装器未适配 |
| 自动取景、背景模糊 | 用户确认生效 |
| 人像光照及其他视觉效果 | 部分模型可运行，GUI 效果未全部确认 |
| 眼神交流 / 新版资源 119 | 仍有未转换模型，未跑通 |
| 麦克风、语音聚焦、其他 Copilot+ 功能 | 不属于本次已验证成果 |
| 真正的整机重启后自动恢复 | 启动依赖已配置；尚待用户实际重启验收 |

安装器目前把 Windows 11 build 26100 及以上作为候选范围；这不代表该范围内每个版本均已验证。真实可用性还取决于摄像头格式、显卡/媒体框架、驱动版本及系统策略。

## 2. 方案原理

需要解决两层不同问题。

第一层是让相机正确接上微软效果组件。正常安装硬件驱动时，上下级设备由硬件枚举关系建立。无对应硬件时，仅把零散软件组件挂到设备树根节点，会导致效果组件找不到父设备上的 `MEPAssets` 路径。工具中的设备树服务创建合法的 Windows 软件设备关系，让微软原版相机 DLL 能找到效果引擎。

关系如下：

```text
Windows 设备树根
└─ SWD\CodexStudio\MepAssets1
   ├─ 硬件标识：SWC\MEP_VEN_8086_DEV_B03E
   ├─ Device Parameters\MEPAssets → 已安装的微软效果包目录
   └─ Windows 自动创建的 MEP_CAMERA_COMPONENT 子设备
      └─ WindowsEffectsCameraMediaSource.dll
```

这里创建的是软件组件关系，没有安装或模拟物理 PCI NPU。

第二层是真正执行 AI。新版 MEP 3.0.8.0 的模型已编译为 NPU 产物，不能仅修改 `NPU` 字符串就交给 CPU。我们从旧版微软包中取得完整 OpenVINO 模型图和权重，在目标电脑上重新编译为 CPU 产物，适配新版引擎的输入输出，再用进程内 Hook 接入。

```text
摄像头
  → 微软原版 Studio 相机外壳 / PerceptionCore
  → 选择 OpenVINO CPU 执行插件
  → 加载适配后的 CPU 模型
  → 使用普通 CPU 内存
  → 微软原有取景、模糊等处理
  → Windows 设置、视频通话等应用收到处理后的画面
```

## 3. 固化采用的结构

| 组件 | 作用 | 安装位置 |
|---|---|---|
| `CodexStudioSoftwareHostV2` | 创建设备树、选择摄像头的 Studio 接入 | `C:\ProgramData\CodexStudioHostV2` |
| `CodexStudioCpuBridge` | 开机启动独立工作进程，自动挂接 FrameServer | `C:\ProgramData\CodexStudioCpuBridge` |
| 私有 Python 3.12.10 + Frida 17.23.3 | 执行桥接工作进程 | CPU 桥接服务目录的 `python` 子目录 |
| OpenVINO CPU 插件、IR frontend、CPU 模型 | 供效果引擎使用 | CPU 桥接服务目录的 `cpu-runtime` 子目录 |

两个服务均以 LocalSystem 运行。安装目录限制普通用户写入，LocalService 可以读取挂接所需文件。它们不依赖当前登录账户的 Python，也不依赖本次研究的临时目录。

启动顺序已配置为：CPU 桥接挂接准备完成 → 设备树服务启动。工作进程异常退出时由 Windows 服务恢复机制重启。相机服务自己退出、换 PID 后，桥接进程会重新寻找并挂接它。

服务会维护相机服务和 Hook，但**不会主动打开摄像头或持续录像**。只有用户打开相机应用，或明确执行录像验证命令时，才会启动采集。

## 4. 驱动和模型从哪里下载

当前固定版本，不能直接拿“最新驱动”替换。

| 用途 | 微软目录版本 | 更新标识 |
|---|---|---|
| 新版效果引擎和模型外壳，B03E 平台 | MEP 3.0.8.0 | `6bb40ca4-7e4c-474a-9bca-db1c53283dc9` |
| 新版 Studio 相机软件组件，B03E 平台 | 3.0.8.0 | `40d5256a-8775-411e-8816-9f4c65596036` |
| 旧版完整模型图和权重，7D1D 平台 | 驱动 1.0.41.0，内部文件 2.3.7.105676 | `52b47555-d209-4e81-a81f-f3d1b9570497` |

目录入口：

- [新版效果引擎](https://www.catalog.update.microsoft.com/ScopedViewInline.aspx?updateid=6bb40ca4-7e4c-474a-9bca-db1c53283dc9)
- [新版相机组件](https://www.catalog.update.microsoft.com/ScopedViewInline.aspx?updateid=40d5256a-8775-411e-8816-9f4c65596036)
- [旧版模型来源](https://www.catalog.update.microsoft.com/ScopedViewInline.aspx?updateid=52b47555-d209-4e81-a81f-f3d1b9570497)

`Prepare.ps1` 已写入微软目录返回的 CDN 地址和 SHA-256，默认自动下载并校验这三个 CAB。它们分别用于安装当前驱动和提取旧模型。**旧版包只离线读取资源，不安装进系统。**

如果目录页面打不开，可以在 [Microsoft Update Catalog](https://www.catalog.update.microsoft.com/) 搜索：

```text
SWC\MEP_VEN_8086_DEV_B03E
SWC\MEP_CAM&VEN_8086_DEV_B03E
SWC\MEP_VEN_8086_DEV_7D1D
```

需注意同版本号可能存在不同平台包。准备工具以具体文件哈希为准，找错包会停止，不能通过删除校验“解决”。

你提供的 `MEP_Microsoft_3.0.6_ExMEP_2.0.28.6.zip` 虽然文件名写着 3.0.6，内部实际是本次使用的 3.0.8.0，也可以作为新版驱动来源。

**不需要安装 `Intel_PTL_NPU.zip`。** 物理 NPU 驱动不会让没有 NPU 的电脑获得 NPU；本方案只用到微软的软件效果组件和 CPU 执行库。

## 5. 准备环境

将工具包解压到固定工作目录，例如：

```text
C:\StudioEffectsCPU
```

日常运行服务会使用 ProgramData 中的独立副本；这个解压目录用于准备、安装、更新和恢复。

需要：Windows 11 x64、管理员权限、正常工作的 USB 摄像头。安装前先确认关闭 Studio 效果时，普通相机应用能正常预览。

若系统没有 Microsoft Visual C++ x64 运行库，先从[微软官方下载地址](https://aka.ms/vs/17/release/vc_redist.x64.exe)安装。`Setup.ps1` 会检查当前原版效果引擎所需的三个运行库文件；缺少时会给出明确提示。

工具包已经提供模型准备工具、独立 Python、Frida、CPU 插件及必要文件。普通使用者不需要 Visual Studio、Python 开发环境、Ghidra 或 REA。

## 6. 在目标电脑准备模型

打开 64 位 PowerShell。此步只做下载、校验、解包及模型编译，不注册服务、不修改系统驱动。

默认从微软服务器取得驱动和旧模型：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\StudioEffectsCPU\Prepare.ps1"
```

如果已经有本次提供的新版驱动 ZIP：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\StudioEffectsCPU\Prepare.ps1" -DriverZip "C:\Downloads\MEP_Microsoft_3.0.6_ExMEP_2.0.28.6.zip"
```

也可以指定已解包的新版驱动目录；该目录中应只有一份符合哈希的原始引擎和相机组件：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\StudioEffectsCPU\Prepare.ps1" -DriverDirectory "C:\Downloads\MEP-Unpacked"
```

离线准备时，再增加 `-LegacyResourceDll`，指向从旧版 1.0.41.0 CAB 中解出的原版 `PerceptionCoreResources.dll`。工具会验证其签名。

准备时会：

1. 校验新版核心 DLL，确认使用已分析的版本。
2. 从旧版资源 DLL 读取完整模型图和权重。
3. 使用独立 OpenVINO 模型准备工具，在本机 CPU 上编译 4 个模型。
4. 执行真实的零输入推理，检查输出是有限数值；这只验证模型能计算，不代表已验证真实画面质量。
5. 转换张量布局、适配输出，并生成新版 `EPContext` 外壳。
6. 生成模型哈希、载荷清单以及目标 CPU 信息。

应看到：

```text
model=face101 cpu_inference=passed
model=matting109 cpu_inference=passed
model=pose113 cpu_inference=passed
model=light132 cpu_inference=passed
```

必须在准备安装的电脑上执行此步。迁移到另一台电脑时重新运行；安装器会检查 CPU 信息是否与准备阶段一致。

## 7. 安装签名驱动并建立正确设备关系

关闭相机设置、相机应用、视频会议等正在使用摄像头的程序。然后以管理员身份打开 64 位 PowerShell：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\StudioEffectsCPU\Setup.ps1"
```

只有一台 USB 摄像头时会自动选择。多台摄像头时，先查看：

```powershell
Get-PnpDevice -PresentOnly -Class Camera | Select-Object FriendlyName, InstanceId
```

再明确指定要接入 Studio 的摄像头：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\StudioEffectsCPU\Setup.ps1" -CameraInstanceId "USB\VID_XXXX&PID_YYYY&MI_00\实际实例路径"
```

安装过程包含：

- 用 PnPUtil 将微软原版 `MicrosoftEffectPack.inf` 和 `mep_camera_component.inf` 加入驱动存储。
- 验证原版目录签名；不编辑 INF、不修改微软 DLL。
- 创建设备树服务，让原版 INF 自动建立 MEP 相机子组件和注册媒体源。
- 在选中摄像头的 VIDEO_CAMERA 接口 `#GLOBAL` 下设置 `FSMEnableMsEffects=1`。
- 安装独立 CPU 桥接服务，并设置开机启动及故障恢复。
- 设置设备树服务依赖 CPU 桥接服务，减少开机时相机先调用未适配引擎的机会。

`FSMEnableMsEffects` 只负责接入效果链，并不能独立解决父设备路径、模型、执行插件和内存分配问题。不要只抄这一条注册表修改。

已有本次研究创建的 V2 服务时，安装器会复用它；不会主动删除已有设备树。若本来已有正常工作的原生 Studio 效果，先保留原有方案，不需要叠加本研究服务。

## 8. 在系统界面验证

重新打开“设置 → 蓝牙和设备 → 相机 → 目标摄像头”，或从快速设置打开 Studio 效果。

先只验证已跑通的两项：

1. **自动取景：** 左右移动身体，观察画面是否跟随或缩放。
2. **背景模糊：** 观察人物轮廓和背景是否产生明确差别。

开启不报错、有画面、模型会话创建成功，是三种不同程度的进展。只有看到了正确效果，才应把该功能标为可用。

再运行连续录像验证：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\ProgramData\CodexStudioCpuBridge\Verify-Bridge.ps1" -RecordFiveSeconds
```

成功时应包含：

```text
RESULT hr=0x00000000 passed=1 ... video_ms=至少5000 wall_ms=至少5000
```

同时检查状态中的 `inference_counts`。在开启相应效果时，应出现 `face101`、`pose113`、`matting109` 的真实推理记录。录像保存在本地 CPU 桥接服务目录，不会上传。

## 9. 真正重启后验收

服务重启测试不等于整机重启测试。本次没有自动重启你的电脑。

方便时由你正常重启 Windows，先验证自动取景和背景模糊，再以管理员身份运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\StudioEffectsCPU\Confirm-AfterReboot.ps1" -GuiVerified
```

脚本会确认系统启动时间确实晚于安装阶段，再检查服务、设备树和 5 秒录像。没有发生真实重启时，它会拒绝标记为“重启已验证”。只有你已经验证界面效果时才传入 `-GuiVerified`。

## 10. 具体的模型选择与 Hook 位置

本方案固定用于当前已校验的引擎二进制；并非跨版本通用地址。

| 资源 | CPU 模型来源与适配 |
|---|---|
| 101 | 旧版人脸检测模型，NCHW 转 NHWC，保持新版输出名称和尺寸 |
| 109 | 旧版背景分割模型，输入及两个输出转换布局并匹配新版名称 |
| 113 | 从旧姿态图选择真实的两个中间结果，匹配新版所需热图和 logits |
| 132 | 旧版图像处理模型，适配布局及名称；效果质量仍待单独确认 |
| 119 | 尚未替换，仍有 NPU 编译产物加载失败 |
| 142、148 | 本次未适配的音频等模型，不列为可用 |

关键调用：

- `PerceptionCore.dll` 导入表处找到它实际使用的私有 `ps-onnxruntime.dll`。
- 获取 ORT API 17 的接口表。
- 通用执行器注册接口，槽 216：将 OpenVINO 设备选择改为 CPU。
- 模型会话创建接口，槽 8：用 CPU 模型替换指定原模型缓冲区；同时检查原模型长度和头尾特征。
- 内存信息接口，槽 68：将 `OpenVINO_RT_NPU` 一类内存请求改为普通 CPU 内存。
- 槽 131：观察分配器错误；槽 133：观察实际 `RunWithBinding` 推理结果。
- 文件查找、动态库加载和 frontend 目录枚举：让原版引擎找到独立目录中的 CPU 插件和 IR frontend。

没有伪造推理结果，也没有将失败状态统一改为成功。模型计算失败仍会记录错误。

## 11. 日常查看与错误定位

```powershell
Get-Service CodexStudioCpuBridge, CodexStudioSoftwareHostV2
Get-Content "C:\ProgramData\CodexStudioCpuBridge\status.json"
Get-Content "C:\ProgramData\CodexStudioCpuBridge\bridge.jsonl" -Tail 30
```

`active=true` 表示工作进程已挂接当前相机服务；它本身不保证所有效果均已成功加载。具体模型看 `session_ready`、`inference` 和错误事件。

| 现象 / 错误 | 优先检查 |
|---|---|
| 没有 Studio 入口 | 摄像头接口选择、软件设备树、原版相机组件注册、设置页重新打开 |
| `0x80070002` / 找不到对象 | MEP 相机子组件的父设备及父设备 Device Parameters 中的 MEPAssets |
| `Failed to load provider OpenVINO` | 是否仍请求 NPU，CPU 插件是否能被找到和加载 |
| CPU 不支持 EPContext | 是否只换了执行器，却没有重新生成 CPU 模型 |
| 无法读取/反序列化模型 | CPU 编译产物是否匹配，以及 IR frontend 是否加载 |
| 输入输出名称不匹配 | 旧图的结果选择、布局、名称和形状是否正确 |
| `No requested allocator available` | 是否仍请求 NPU 专用内存 |
| 只有资源 119 报错 | 当前未适配功能的已知缺口；不能据此否定取景和模糊已跑通 |
| `Driver changed` | Windows 更新替换了已固定的二进制，需重新适配或恢复匹配版本 |

系统更新后，不要把新的文件哈希填进旧配置就继续使用旧地址。应先关闭效果，检查实际加载文件，重新确认接口和模型版本。

## 12. 更新模型

重新运行 `Prepare.ps1` 后，需要把新生成的模型更新进已安装服务时：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\StudioEffectsCPU\Update-Models.ps1"
```

更新脚本先校验模型、备份旧模型，停止两个服务，替换后重启并执行 5 秒验证。失败时恢复备份。它不会更新微软原版驱动或给新版本 DLL 套用旧 Hook 地址。

## 13. 停用与恢复

**先在 Studio 面板关闭效果，并关闭使用摄像头的应用。** 停止桥接服务后，原版引擎会回到默认的 NPU 路径；保持效果开启时可能再次无法使用相机。

仅卸载 CPU 桥接服务，保留现有设备树和签名驱动：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\ProgramData\CodexStudioCpuBridge\Uninstall-Bridge.ps1"
```

它会还原安装前的服务依赖，删除 CPU 桥接服务，保留文件、模型和诊断记录。

若设备树服务也是由这套工具在一台干净电脑上新建的，可用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\StudioEffectsCPU\Uninstall-All.ps1"
```

完整卸载会撤销本工具记录的摄像头设置、移除软件设备树和服务；保留共享的微软签名驱动包，避免误删其他设备使用的包。

在当前研究笔记本上，V2 服务属于此前已有的研究状态。完整卸载脚本会拒绝直接移除它，避免丢失原有恢复路径；这里只应使用 CPU 桥接卸载，设备树恢复参考此前的 V2 恢复记录。工具只能撤销自己记录的变化，不能自动还原其他 AI 在更早阶段做过、且没有备份的修改。

## 14. 本轮验证记录与仍需完成的工作

已验证：

- 独立 Python / Frida 可运行，Python 可执行文件签名有效。
- 原版相机组件可从微软 CDN 取得，DLL 与现有驱动哈希一致。
- 使用提供的原版驱动 ZIP，完整准备流程能在目标电脑重建 4 个 CPU 模型并通过推理测试。
- 服务模式连续录像通过；用户确认自动取景和背景模糊正常。
- 服务重启后连续录像通过。
- 模拟工作进程崩溃，Windows 自动恢复；恢复后连续录像与推理通过。
- 通过发布包的模型准备工具生成的模型已接回相机服务并完成连续录像。

待验证或待研究：其他实机、实际整机重启、干净系统首次安装、长时间负载、非 USB 摄像头、剩余效果及新版模型来源。它们不能通过当前一台电脑的成功结果直接推定。

官方背景资料：[Studio Effects 概述](https://learn.microsoft.com/zh-cn/windows/apps/develop/windows-integration/studio-effects)、[EPContext 设计](https://onnxruntime.ai/docs/execution-providers/EP-Context-Design.html)、[Python 嵌入式运行环境](https://www.python.org/downloads/release/python-31210/)。
