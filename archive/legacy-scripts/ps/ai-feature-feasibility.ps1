<#
    AI 功能可行性诊断（只读）
    =========================
    在普通 PowerShell（不是 DSH 沙箱）中运行：

        powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ai-feature-feasibility.ps1

    本脚本只读取状态，不修改注册表、不安装包、不启动任何 AI 功能。
    输出末尾会给出「缺口清单」，用于决定下一步。

    部分项目需要管理员权限才能完整读取（会标注）。
#>

$ErrorActionPreference = 'Continue'

function Section($title) {
    Write-Host ''
    Write-Host ('=' * 62) -ForegroundColor DarkGray
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host ('=' * 62) -ForegroundColor DarkGray
}

function Try-It($label, [scriptblock]$action) {
    try { & $action } catch { Write-Host "  [$label] 查询失败: $($_.Exception.Message)" -ForegroundColor DarkYellow }
}

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# ---------------------------------------------------------------- 0
Section '0. 系统与构建'
$cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction SilentlyContinue
$os = [PSCustomObject]@{
    DisplayVersion = $cv.DisplayVersion
    Build          = "$($cv.CurrentBuild).$($cv.UBR)"
    Architecture   = $env:PROCESSOR_ARCHITECTURE
    Admin          = $isAdmin
}
$os | Format-List

# ---------------------------------------------------------------- 1
Section '1. AI 外壳组件（CoreAI / ClickToDo / AIContext）'
Write-Host '  这是「外壳」。报告称本机已包含，用于确认。' -ForegroundColor DarkGray
Try-It 'Appx' {
    $shell = Get-AppxPackage | Where-Object { $_.Name -match 'CoreAI|ClickToDo|AIContextService' }
    if ($shell) { $shell | Select-Object Name, Version, Architecture, Status | Format-Table -AutoSize }
    else { Write-Host '  (未找到)' -ForegroundColor Yellow }
}

# ---------------------------------------------------------------- 2
Section '2. 模型包 WindowsWorkload.*  ← 你的主要缺口'
Write-Host '  无平台后缀的通用包（TextRecognition.1 / ScrRegDetection.1 /' -ForegroundColor DarkGray
Write-Host '  SemanticText.1 / PSOnnxRuntime）是本次要找的目标。' -ForegroundColor DarkGray
Try-It 'Appx' {
    $wl = Get-AppxPackage | Where-Object { $_.Name -match 'WindowsWorkload|AIFabric|^Microsoft\.Windows\.AI' }
    if ($wl) { $wl | Select-Object Name, Version, Architecture, Status | Format-Table -AutoSize }
    else { Write-Host '  (未找到 —— 与报告一致：模型包缺失)' -ForegroundColor Yellow }
}

if ($isAdmin) {
    Try-It 'AllUsers' {
        Write-Host '  -- 所有用户 --' -ForegroundColor DarkGray
        $all = Get-AppxPackage -AllUsers | Where-Object { $_.Name -match 'WindowsWorkload' }
        if ($all) { $all | Select-Object Name, Version, PackageUserInformation | Format-Table -AutoSize }
        else { Write-Host '  (所有用户均未找到)' -ForegroundColor Yellow }
    }
} else {
    Write-Host '  提示: 以管理员运行可检查所有用户的安装清单。' -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------- 3
Section '3. 磁盘上的包实体（WindowsApps）'
Try-It 'FS' {
    $found = Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'WindowsWorkload|AIFabric|CoreAI' } |
        Select-Object -ExpandProperty Name
    if ($found) { $found } else { Write-Host '  (未找到 — 可能无权限，属正常)' -ForegroundColor Yellow }
}

# ---------------------------------------------------------------- 4
Section '4. Recall 前置条件：TPM 2.0'
Try-It 'TPM' { Get-Tpm | Select-Object TpmPresent, TpmReady, TpmVersion, Manufacturer | Format-List }

# ---------------------------------------------------------------- 5
Section '5. Recall 前置条件：设备加密 / BitLocker'
Try-It 'manage-bde' {
    $bde = manage-bde -status C: 2>&1 | Select-String -Pattern 'Conversion Status|Protection Status|Percentage Encrypted'
    if ($bde) { $bde } else { Write-Host '  (无输出)' }
}
Try-It 'WMI' {
    Get-CimInstance -Namespace root\cimv2\security\microsoftvolumeencryption `
        -ClassName Win32_EncryptableVolume -ErrorAction Stop |
        Select-Object DriveLetter, ProtectionStatus | Format-Table -AutoSize
}

# ---------------------------------------------------------------- 6
Section '6. Recall 前置条件：Windows Hello ESS'
$winbio = Join-Path $env:SystemRoot 'System32\winbioext.dll'
Write-Host "  winbioext.dll 存在: $(Test-Path $winbio)"
Write-Host '  真正的 ESS 判定需要调用 WinBioIsESSCapable；' -ForegroundColor DarkGray
Write-Host '  可在「设置 > 账户 > 登录选项 > 面部/指纹」查看是否有「增强登录安全」。' -ForegroundColor DarkGray

# ---------------------------------------------------------------- 7
Section '7. Studio Effects 前置条件：摄像头与 WSE'
Try-It 'Camera' {
    $cam = Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue
    if ($cam) { $cam | Select-Object FriendlyName, Status, InstanceId | Format-Table -AutoSize }
    else { Write-Host '  (未找到摄像头)' -ForegroundColor Yellow }
}
Try-It 'WSE' {
    $wse = Get-PnpDevice -ErrorAction SilentlyContinue |
        Where-Object { $_.FriendlyName -match 'Studio|WSE|Windows Studio' }
    if ($wse) { $wse | Select-Object FriendlyName, Status | Format-Table -AutoSize }
    else { Write-Host '  (未找到 WSE 相关设备 —— 与报告一致)' -ForegroundColor Yellow }
}

# ---------------------------------------------------------------- 8
Section '8. HCF 状态键'
$hcf = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\WorkloadManager\HCF\Status'
if (Test-Path $hcf) {
    Get-ItemProperty $hcf | Format-List
} else {
    Write-Host '  不存在（与报告一致：HCF 组件未部署）' -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 9
Section '9. Recall 可选组件状态'
if ($isAdmin) {
    Try-It 'DISM' {
        Get-WindowsOptionalFeature -Online -FeatureName Recall -ErrorAction Stop |
            Select-Object FeatureName, State | Format-List
    }
} else {
    Write-Host '  需要管理员权限。' -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------- 10
Section '10. GPU（决定是否可能走官方 Phi Silica GPU 路径）'
Try-It 'GPU' {
    Get-CimInstance Win32_VideoController -ErrorAction Stop |
        Select-Object Name, DriverVersion, @{n='VRAM_GB';e={ if ($_.AdapterRAM) { [math]::Round($_.AdapterRAM/1GB,1) } }} |
        Format-Table -AutoSize
}

# ---------------------------------------------------------------- 汇总
Section '缺口清单汇总'
Write-Host @'
  对照下表决定下一步：

  [外壳 CoreAI]      有 -> 说明壳在，只缺模型
  [模型包 Workload]  无 -> 阶段1 目标：获取微软签名的通用包
  [TPM 2.0]          无 -> Recall 基本出局
  [设备加密]         无 -> Recall 基本出局（需先能开 BitLocker）
  [Hello ESS]        无 -> Recall 基本出局
  [WSE 设备]         无 -> Studio Effects 无法用「装包」解决

  下一步（详见对话中的计划）：
    阶段1  获取 WindowsWorkload.* 通用包 + PSOnnxRuntime，校验签名/架构/版本
    阶段2  只装包、不修改任何状态，重跑探针看 GetReadyState 是否改善
    阶段3  仅当阶段2无改善，才干预「平台->包」的解析映射
           方向：让 NPU 探测返回「未知」，而不是伪造一台 NPU

  本脚本不修改任何系统状态。
'@ -ForegroundColor Gray
