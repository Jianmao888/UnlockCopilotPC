<#
    AI-Workload-Packages.ps1
    ========================
    在 Copilot+ PC 与目标机之间搬运 Windows AI 模型包（WindowsWorkload.*）

    背景（2026-10-12 实测）：
      目标机 i7-1260P / RTX 2050 缺少全部 WindowsWorkload.* 包。
      这些包只经 Copilot+ PC 的 UUP 通道（ms-uup://Product/com.microsoft.windows.workload.*）
      和 OEM 预装下发；公开 Store 搜不到，Windows Update 也不推给非 Copilot+ 设备。

    用法：
      # 【源机 · Copilot+ PC · 管理员】导出
      .\AI-Workload-Packages.ps1 -Mode Export -Destination D:\AIWorkloads

      # 把 D:\AIWorkloads 整个目录拷到目标机，然后
      # 【目标机 · 管理员】安装
      .\AI-Workload-Packages.ps1 -Mode Install -Source D:\AIWorkloads

      # 任意一侧只读检查
      .\AI-Workload-Packages.ps1 -Mode Probe

    说明：
      - Export 用 robocopy /B（备份权限）绕过 WindowsApps 的 ACL，不改源机权限。
      - Install 优先用 Add-AppxPackage -Register，失败则回退 Add-AppxProvisionedPackage。
      - 不修改任何安全设置。回滚：Remove-AppxPackage <包名>。
#>

param(
    [ValidateSet('Probe', 'Export', 'Install')]
    [string]$Mode = 'Probe',
    [string]$Destination,
    [string]$Source,
    [switch]$Force
)

$ErrorActionPreference = 'Continue'

# 依赖顺序：先运行时和管理器，再数据包，最后模型包
$InstallOrder = @(
    'WindowsWorkload.Manager',
    'WindowsWorkload.SessionManager',
    'WindowsWorkload.PSOnnxRuntime',
    'WindowsWorkload.OnnxRuntime',
    'WindowsWorkload.PSTokenizer',
    'WindowsWorkload.WinMLShared',
    'WindowsWorkload.Data.',
    'WindowsWorkload.ScrRegDetection',
    'WindowsWorkload.TextRecognition',
    'WindowsWorkload.SemanticText',
    'WindowsWorkload.QueryProcessor',
    'WindowsWorkload.QueryBlockList'
)

function Write-Head($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }

function Get-WorkloadPackages {
    Get-AppxPackage -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'WindowsWorkload*' }
}

function Show-State {
    $pkgs = Get-WorkloadPackages
    if (-not $pkgs) {
        Write-Host "未安装任何 WindowsWorkload.* 包" -ForegroundColor Yellow
        return
    }
    $pkgs | Select-Object Name, Version, Architecture, Status |
        Sort-Object Name | Format-Table -AutoSize
    Write-Host "共 $($pkgs.Count) 个" -ForegroundColor Green
}

# ---------------------------------------------------------------- Probe
if ($Mode -eq 'Probe') {
    Write-Head '本机 WindowsWorkload 包'
    Show-State
    Write-Head '相关运行时组件'
    Get-AppxPackage -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'AIFabric|CoreAI|Windows\.AI' } |
        Select-Object Name, Version, SignatureKind | Format-Table -AutoSize
    Write-Head 'AI 组件主机服务'
    Get-Service WSAIFabricSvc -ErrorAction SilentlyContinue |
        Select-Object Name, Status, StartType | Format-Table -AutoSize
    return
}

# ---------------------------------------------------------------- Export
if ($Mode -eq 'Export') {
    if (-not $Destination) { throw '需要 -Destination，例如 -Destination D:\AIWorkloads' }
    if (-not (Test-Path $Destination)) { New-Item -ItemType Directory -Path $Destination -Force | Out-Null }

    $pkgs = Get-WorkloadPackages
    if (-not $pkgs) {
        Write-Host '本机没有 WindowsWorkload.* 包。' -ForegroundColor Red
        Write-Host 'Export 必须在已安装这些包的 Copilot+ PC 上运行。' -ForegroundColor Yellow
        return
    }

    Write-Head "导出 $($pkgs.Count) 个包"
    $manifest = @()
    foreach ($p in $pkgs) {
        $dest = Join-Path $Destination $p.PackageFullName
        Write-Host "  $($p.Name)  $($p.Version)  $($p.Architecture)"
        # /B = 备份模式，用 SeBackupPrivilege 绕过 WindowsApps ACL
        & robocopy $p.InstallLocation $dest /E /B /R:0 /W:0 /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -lt 8) {
            $manifest += [PSCustomObject]@{
                Name             = $p.Name
                Version          = $p.Version
                Architecture     = $p.Architecture
                PackageFullName  = $p.PackageFullName
                PackageFamilyName= $p.PackageFamilyName
                Folder           = $p.PackageFullName
            }
        } else {
            Write-Host "    robocopy 失败 (exit=$LASTEXITCODE)" -ForegroundColor Red
        }
    }

    $manifest | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $Destination 'manifest.json') -Encoding UTF8
    Write-Head '完成'
    Write-Host "已导出到: $Destination"
    Write-Host "把整个目录拷贝到目标机，然后运行："
    Write-Host "  .\AI-Workload-Packages.ps1 -Mode Install -Source <该目录>" -ForegroundColor Gray
    Write-Host "`n注意：目标机架构必须与源机一致（都为 x64 最稳）。" -ForegroundColor Yellow
    return
}

# ---------------------------------------------------------------- Install
if ($Mode -eq 'Install') {
    if (-not $Source) { throw '需要 -Source，例如 -Source D:\AIWorkloads' }
    $mf = Join-Path $Source 'manifest.json'
    if (-not (Test-Path $mf)) {
        Write-Host "找不到 $mf" -ForegroundColor Red
        Write-Host "需要先在 Copilot+ PC 上用 -Mode Export 导出。" -ForegroundColor Yellow
        return
    }

    $packages = Get-Content $mf -Raw | ConvertFrom-Json
    $isAdmin = ([Security.Principal.WindowsPrincipal] `
        [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) { Write-Host '警告：未以管理员运行，Add-AppxProvisionedPackage 会失败。' -ForegroundColor Yellow }

    # 按依赖顺序排序
    $sorted = $packages | Sort-Object {
        $n = $_.Name
        $idx = 0
        for ($i = 0; $i -lt $InstallOrder.Count; $i++) {
            if ($n -like "$($InstallOrder[$i])*") { $idx = $i; break }
        }
        $idx
    }

    Write-Head "安装 $($sorted.Count) 个包"
    $ok = 0; $fail = 0
    foreach ($p in $sorted) {
        $dir = Join-Path $Source $p.Folder
        $appxManifest = Join-Path $dir 'AppxManifest.xml'
        if (-not (Test-Path $appxManifest)) {
            Write-Host "  跳过 $($p.Name)：找不到 AppxManifest.xml" -ForegroundColor Yellow
            $fail++; continue
        }
        Write-Host "  → $($p.Name) $($p.Version)"
        try {
            Add-AppxPackage -Register $appxManifest -DisableDevelopmentMode -ErrorAction Stop
            Write-Host "    已注册" -ForegroundColor Green
            $ok++
        } catch {
            Write-Host "    Register 失败: $($_.Exception.Message)" -ForegroundColor DarkYellow
            # 回退：打成 msix 再用 provisioned 安装
            try {
                Add-AppxProvisionedPackage -Online -FolderPath $dir -SkipLicense -ErrorAction Stop | Out-Null
                Write-Host "    已 provisioned 安装" -ForegroundColor Green
                $ok++
            } catch {
                Write-Host "    回退也失败: $($_.Exception.Message)" -ForegroundColor Red
                $fail++
            }
        }
    }

    Write-Head '结果'
    Show-State
    Write-Host "成功 $ok / 失败 $fail"
    if ($fail -gt 0) {
        Write-Host @'

若失败，常见原因：
  1. 架构不匹配（源机 arm64，目标机 x64）—— 必须用同为 x64 的 Copilot+ PC
  2. 缺少依赖框架包 —— 先装 Manager / SessionManager / PSOnnxRuntime
  3. 版本与目标机 AIFabric 不匹配 —— 对照 workloads.json 里的版本号
  4. 未开启开发人员模式 —— 设置 > 系统 > 开发者选项
'@ -ForegroundColor Gray
    }
    return
}
