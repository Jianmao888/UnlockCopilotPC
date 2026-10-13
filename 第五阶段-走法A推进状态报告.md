# 第五阶段：走法 A 的实质推进 —— 状态报告

日期：2026-10-13
目标：可复用的绕过方法，让任意 PC 开原生 Copilot+ 功能

---

## 一、这一轮换了思路，而且找到了一条从没人走过的路

**之前的失败都集中在"注册表写资格标记"。这一轮换成了"让系统使用它自己的配置机制"。**

### 已完成的动作（全部可回滚）

| # | 动作 | 结果 |
|---|---|---|
| 1 | 装齐 **365 平台闭包的 19 个包** | ✅ 全部 `Status = Ok` |
| 2 | 把 `workloads.json` 换成**只含三个可满足 workload 的最小配置** | ✅ 已加载（12,066 字符） |
| 3 | 注册 UUP 产品（官方 `UUPProducts` 格式） | ✅ 4 个产品 ID |
| 4 | 注册 AmperageKit 路径（`TargetingInfo\DynamicInstalled`） | ✅ 4 个产品 ID |
| 5 | Pin 全部 19 个家族（官方 pinned 模型） | ✅ 19 条 |
| 6 | 重启 `WSAIFabricSvc` / `StateRepository` / `wuauserv` | ✅ |

### 关键成果

**① 三个 workload 闭包 100% 齐备**

```
Windows.Workload.Analysis.365          (12 包)  ✅ 全有
Windows.Workload.ContentExtraction.365  (7 包)  ✅ 全有
Windows.Workload.ImageSearch.365       (12 包)  ✅ 全有
```

**② 这三个 workload 覆盖的 API**

```
Microsoft.Windows.Vision.TextRecognizer          ← OCR（Windows AI API）
Microsoft.Windows.Vision.ScreenRegionDetector    ← 区域检测（Click to Do 核心）
Microsoft.Windows.SemanticSearch.*               ← 语义搜索全套
Microsoft.Windows.AI.*（非 Experimental 别名）    ← 公开 API 面
```

**③ 发现了平台的真实选择机制**

```
workloads.json         → 通用家族（我们一个都没有）
workloads.365.json     → .365. 家族（我们 100% 有）
workloads.lnl.json     → .Lnl. 家族
workloads.{qnn,stx,ptl,j32}.json

NpuType 枚举: None, Qnn, Lnl, Stx, Win365, Unknown
```

**④ 拿到了正确的产品 ID 格式（与微软官方文档一致）**

```
Windows.Workload.ContentExtraction.365.amd64
Windows.Workload.Analysis.365.amd64
Windows.Workload.ImageSearch.365.amd64
Windows.Workload.ContentExtraction.LNL.amd64
```

---

## 二、还差最后一步

### 现象

```
StateRepository-Machine.srd:
    Package.PackageFullName   含 WindowsWorkload: 19 行   ✅
    PackageFamily.Name                        19 行   ✅
    PkgExtension.DisplayName                   6 行   ✅
    UupProduct                                 0 行   ❌  ← 卡点
    UupProductPackage                          0 行   ❌
```

**`AIComponentManager` 读的就是 `UupProduct` 表。它在注册表侧被写入了（三个路径都试了），但没有物化到 StateRepository。**

### 推断

**注册表 → StateRepository 的转换发生在"启动/服务阶段"，不是在运行时。**

**证据：** 微软官方 `add-OemPreload.ps1` 只支持**离线镜像**模式
（`-Online` 明确写着 `"ERROR: -Online not yet supported! Coming soon..."`），
也就是说这个机制的设计前提就是"改离线镜像 → 开机时物化"。

### 因此下一步是：**重启**

---

## 三、重启后的验收标准

跑 `post-reboot-check.ps1`，检查：

| 项 | 期望 |
|---|---|
| `UupProduct` 表行数 | **> 0** |
| `AIComponentManager.get_Size` | **> 0** |
| `TextRecognizer.GetReadyState` | **0 (Ready)** |
| `AICapabilities.HasAICapability(0)` | **True** |
| `workloads.json` 是否被还原 | 若被还原则需重做 |

---

## 四、如果重启无效，剩下的路

| 选项 | 说明 | 成本 |
|---|---|---|
| **A** | Ghidra 反编译 `AIComponentMgmt.dll`（184KB），定位 `PE_CreateProductEnumerator` 的读取对象 | 中 |
| **B** | 直接写 StateRepository SQLite 的 `UupProduct` 表 | 低但风险高（可能被服务覆盖） |
| **C** | Hook `EnumerateInstalledProductByName`，让 `AIComponentManager` 看到我们的组件 | 中 |
| **D** | 找 `AIComponentManager` 的另一条读取路径 | 未知 |
| **E** | 转 AmperageKit 的另两套手法（Detour `HardwareRequirements`、patch `NPUDetect.dll`） | 中高 |

**我建议：重启 → 若无效则 A + C 并行。**

---

## 五、回滚方法（全部可逆）

```powershell
# 1) 还原 workloads.json
Copy-Item 'C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\workloads.json.orig-backup' `
          'C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\workloads.json' -Force

# 2) 删注册表项
Remove-Item -Recurse 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\UUPProducts'
Remove-Item -Recurse 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Pinned'
foreach ($p in 'Windows.Workload.ContentExtraction.365.amd64','Windows.Workload.Analysis.365.amd64',
               'Windows.Workload.ImageSearch.365.amd64','Windows.Workload.ContentExtraction.LNL.amd64') {
    Remove-Item -Recurse "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo\DynamicInstalled\$p"
}

# 3) 卸载包
Get-AppxPackage -AllUsers | Where-Object { $_.Name -match '^WindowsWorkload' } | Remove-AppxPackage -AllUsers
Get-AppxProvisionedPackage -Online | Where-Object { $_.DisplayName -match '^WindowsWorkload' } |
    ForEach-Object { Remove-AppxProvisionedPackage -Online -PackageName $_.PackageName }
```

**备份文件**：`C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\workloads.json.orig-backup`

---

## 六、这一轮的脚本清单

| 脚本 | 用途 |
|---|---|
| `deploy-365-workloads.ps1` | 定位 + 装 365 包 + 换 JSON |
| `install-365.ps1` | 安装 14 个 MSIX |
| `provision-365.ps1` | provision 带 accessControl 的包 + AppReadiness |
| `build_min_workloads.py` | 构造最小 workloads.json |
| `check-after-swap.ps1` | 验证 + 注册 UUP + pin |
| `register-dynamic.ps1` | AmperageKit 路径注册 |
| `post-reboot-check.ps1` | **重启后验收** |
| `restore-npu-hive.ps1` | 还原 NPU hive |
