# Click to Do：已跑通的完整链条

## 当前能做什么

原版 Click to Do 覆盖层可以识别并选择文字/图像。用户在一次 Windows 重启后确认复制和打开也能工作；尚未定位重启解决的是哪项状态，不能声称已修改了某个动作分发函数。改写、摘要等其他操作和 Recall 不属于已验证成果。

已恢复**原生 Win＋Q**：由原版客户端自己的窗口接收 WM_HOTKEY，没有全局键盘/鼠标监听器。Win＋鼠标单击仍短暂出现后消失，未完成修复。

## 从安装到真正执行，共需要四处适配

```text
安装 LNL 产品及精确依赖
  → 既有 WSAIFabricHost.dll 补丁选择 LNL
  → 原版 ClickToDo.exe 的能力/界面检查
  → 原版 WorkloadsSessionHost.exe 启动时的进程保护适配
  → LNL 的 cacheapi.dll、srdapi.dll 选择 OpenVINO CPU
  → 原版宿主返回真实区域和 OCR
  → 原版覆盖层及操作菜单
```

这不是自己仿造一个模型宿主：实际执行和注册原版 WinRT 工厂的是微软的 WorkloadsSessionHost.exe。自编写的辅助程序只是受限启动调试器和 Hook 控制器。

### 服务端选包

`C:\Windows\System32\WSAIFabricHost.dll` 原 SHA256：
`ea8f782b722161a15c2cc5bcff1407d4844aa972af4bb7bf45b5c0751e486170`。

当前补丁后 SHA256：
`dbe0d2a3a7f314f8764deef43354af19dd73ffd660d086a792ce37e4f7ca7717`。

文件偏移 400087 的立即数低字节 E8→E9，对应 `MOV EDI,1000`→`MOV EDI,1001`，并重算 PE 校验和。这里不是把 CALL 指令 E8 改为 JMP E9；必须结合原文件和上下文字节理解。

仓库 `native-install/tools/patch-fabric.py` 只在 ProgramData 制作候选副本，**不会自动替换系统文件**。系统替换、权限与 ACL、原文件、服务重启需独立记录；已有机器先读哈希，不要重复打补丁。本次文档审核未触碰系统 DLL。

### 客户端与真实宿主

- `phase2-hook/capability-hook.js`：限定能力检查和企业功能门槛。
- DiscoveryOverlay RVA `0x2bbe28`、`0x1bb1c4`：当前版本支持/就绪界面判据。
- `optional-source-only.js`：针对调用来源可选字段的窄范围兼容处理；最近成功测试未观察到它必须触发，不可声称所有场景均需要。
- 宿主启动适配：在新创建的原版宿主内将 RVA `0xddfe`、`0xde22` 两处 DWORD 从 1 改为 0；在 RVA `0xda36` 初始化断点衔接后恢复断点和线程上下文，挂接 CPU Hook，再恢复原版线程。
- 该宿主仍使用原有 LocalService / Session 0 身份；没有修改磁盘上的 WorkloadsSessionHost.exe。
- 只对精确宿主路径临时配置 IFEO。存在他人的 IFEO 时拒绝覆盖；正常退出清除自己的注册。

### CPU 执行选择

| 实际 DLL | SHA256 | 当前拦截点 |
|---|---|---|
| WinMLShared.5.2 / cacheapi.dll | `671de69b81da93bd2ce3e5cd6048a9a398f68dda7ef62112461dd01a43c6a8cd` | RVA `0x7cb6c` |
| ScrRegDetection.Lnl.1 / srdapi.dll | `fe2049fb2da34080fed109661b940b1612a47bbbfee6c2649fb3ac1f536ba440` | RVA `0x5c91c` |

在已核对指令处，将 `[rbp-0x58]` 的设备选择 2 改为 0，走 **OpenVINO CPU**。这与单纯把 ONNX Runtime 默认 CPU fallback 打开不同。相关调用完成了真实场景检测和 OCR，不是只改 HRESULT。

所有实现见 `work/phase21-host-ifeo/host-cpu-hook.js`、`HostStartupDebugger.cs`、`attach-real-hosts.py`。不能给新版文件填上新的 SHA256 后继续沿用旧偏移。

## Win＋Q 为什么原来打开搜索

Explorer 注册函数 RVA `0x6ed88` 对热键 ID 570（0x23A）查询 RVA `0xcc630`。只有满足 Click to Do 条件时才跳过搜索注册。本机未满足，因此 Explorer 先占用 Win＋Q。

DiscoveryOverlay RVA `0x1bc66c` 创建窗口类 **ScreenrayOwnerWindow**，在 RVA `0x1bc7e1` 调用：

```text
RegisterHotKey(原版窗口, 42, WIN|MOD_NOREPEAT=0x4008, VK_Q=0x51)
```

这次失败未被客户端处理。已验证的办法是在两个原版 UI 线程上依次执行：Explorer 注销 570，CTD 注册 42。结束时反向操作归还搜索。调度只使用独特标记的 WM_NULL，不合成输入。

用户实按后确认“能正常打开并选择内容”；120 秒测试和整合启动器关闭都记录了搜索恢复成功。源码为 `work/phase26-shell-entry/native-hotkey-*`，证据见 `evidence/2026-10-16/`。

## 日常入口与恢复

按 [资产重建](06-源码与资产重建.md) 编译并打包后：

```powershell
# 从仓库根目录运行。也可以创建指向此 GUI 程序的普通快捷方式。
& '.\outputs\ClickToDo-实验启动器\ClickToDoLauncher.exe'
# 只预热并交接原生热键，不立刻显示覆盖层：
& '.\outputs\ClickToDo-实验启动器\ClickToDoLauncher.exe' --warm
# 结束本次会话、归还搜索、撤销临时注册：
& '.\outputs\ClickToDo-实验启动器\ClickToDoLauncher.exe' --stop
```

默认约 15 分钟，会申请一次正常管理员权限。GUI 程序和 pythonw 隐藏后台终端，清单固定 17 个运行/配置文件，摘要嵌入 EXE。重启后需要先启动一次；未设置登录任务。Explorer 或客户端重启、强杀协调器也可能中断恢复，不能声称所有异常都已覆盖。

本机开始菜单添加了实验启动器快捷方式。原版 AUMID `MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy!ClickToDoApp` 原本已存在，manifest 没有对该项隐藏 AppListEntry。把当前 SessionInfo 的 ClickToDoHideEntryPoint 临时从 1 改为 0 后，用户反馈无变化，已恢复为 1；这不是可用修复。

## 尚待定位的 Win＋单击

手势曾进入 DiscoveryOverlay dispatch `0x1c13c4` 和 window-activation `0x1bcc00`，未记录相同的 URI/WM_COPYDATA 路径。下一轮只需在同一预热客户端记录成功 Win＋Q 与手势的最早差异，不要重新从下载包开始。

已有一次客户端崩溃与异常观察 Hook 有明确对照：撤掉 RaiseException / RtlRaiseException 两类观察后，识别与选择稳定。不要把这些调试 Hook 混入成功版本。
