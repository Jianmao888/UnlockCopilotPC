<#
    AI-Components-Acquire.ps1
    ========================
    目标：让 Windows 交付 WindowsWorkload.* 组件包
          （Click to Do「单击执行」与 自然语言搜索 共同缺的就是这些）

    背景（本机实测 2026-10-12）：
      HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsAI\LastConfiguration
        HardwareCompatibility      = 0   <- 系统判定"硬件不兼容"
        AttemptedInstallCount      = 0   <- 因此从未尝试下载
        MaxInstallAttemptsAllowed  = 5
        AllowedInRegion            = 1   <- 地区已允许
        MeetsAdditionalDriverRequirements = 1
      组件分发通道：UUP，产品 ID 形如 ms-uup://Product/com.microsoft.windows.workload.*

    用法（管理员 PowerShell）：
      .\AI-Components-Acquire.ps1 -Action Status    # 只读，查看当前状态
      .\AI-Components-Acquire.ps1 -Action Backup    # 备份当前状态
      .\AI-Components-Acquire.ps1 -Action Enable    # 备份 + 设 HardwareCompatibility=1
      .\AI-Components-Acquire.ps1 -Action Scan      # 触发 Windows Update 扫描
      .\AI-Components-Acquire.ps1 -Action Check     # 看包有没有下来
      .\AI-Components-Acquire.ps1 -Action Restore   # 从备份还原

    只修改一个 DWORD，且原始值保存到 JSON。不做其他任何系统修改。
#>

param(
    [ValidateSet('Status', 'Backup', 'Enable', 'Scan', 'Check', 'Restore')]
    [string]$Action = 'Status',
    [string]$BackupPath = (Join-Path $PSScriptRoot 'windowsai-state-before.json')
)

$ErrorActionPreference = 'Continue'
$KeyPath = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsAI\LastConfiguration'

function Show-State {
    if (-not (Test-Path $KeyPath)) { Write-Host "键不存在: $KeyPath" -ForegroundColor Red; return }
    Get-ItemProperty $KeyPath | Select-Object `
        HardwareCompatibility, ITManaged, AllowedInRegion, PolicyConfigured, PolicyEnabled,
        FTDisabledState, MeetsAdditionalDriverRequirements, LastOperationKind,
        AttemptedInstallCount, MaxInstallAttemptsAllowed, LastBuild, LastKnownLCUVersion |
        Format-List
}

function Show-Packages {
    $wl = Get-AppxPackage -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'WindowsWorkload' }
    if ($wl) {
        Write-Host "已安装的 WindowsWorkload 包:" -ForegroundColor Green
        $wl | Select-Object Name, Version, Architecture, Status | Sort-Object Name | Format-Table -AutoSize
        Write-Host "共 $($wl.Count) 个" -ForegroundColor Green
    } else {
        Write-Host "未安装任何 WindowsWorkload 包（与调查一致）" -ForegroundColor Yellow
    }
}

switch ($Action) {

    'Status' {
        Write-Host "`n=== WindowsAI 配置状态 ===" -ForegroundColor Cyan
        Show-State
        Write-Host "=== 组件包状态 ===" -ForegroundColor Cyan
        Show-Packages
        Write-Host "`n=== 相关服务 ===" -ForegroundColor Cyan
        Get-Service WSAIFabricSvc -ErrorAction SilentlyContinue |
            Select-Object Name, Status, StartType | Format-Table -AutoSize
    }

    'Backup' {
        if (-not (Test-Path $KeyPath)) { Write-Host "键不存在，无法备份" -ForegroundColor Red; break }
        $state = Get-ItemProperty $KeyPath
        $obj = [ordered]@{ backedUpAt = (Get-Date).ToString('s'); keyPath = $KeyPath; values = [ordered]@{} }
        foreach ($p in $state.PSObject.Properties) {
            if ($p.Name -notmatch '^PS') { $obj.values[$p.Name] = $p.Value }
        }
        $obj | ConvertTo-Json -Depth 4 | Set-Content -Path $BackupPath -Encoding UTF8
        Write-Host "已备份到: $BackupPath" -ForegroundColor Green
        Write-Host "HardwareCompatibility 原值 = $($state.HardwareCompatibility)"
    }

    'Enable' {
        if (-not (Test-Path $BackupPath)) {
            Write-Host "未找到备份，先执行 -Action Backup" -ForegroundColor Yellow
            & $PSCommandPath -Action Backup -BackupPath $BackupPath
        }
        Write-Host "`n设置 HardwareCompatibility = 1 ..." -ForegroundColor Cyan
        Set-ItemProperty -Path $KeyPath -Name 'HardwareCompatibility' -Value 1 -Type DWord
        Write-Host "完成。当前状态:" -ForegroundColor Green
        Show-State
        Write-Host @'

下一步：
  1. 运行  .\AI-Components-Acquire.ps1 -Action Scan   触发 WU 扫描
  2. 等 5-15 分钟，运行  -Action Check   看包是否出现
  3. 若 AttemptedInstallCount 仍为 0 或 HardwareCompatibility 被写回 0，
     说明这个键是"评估结果记录"而非"开关"，需要换用 AIComponentManager API。
  4. 无论结果如何都可用  -Action Restore  还原
'@ -ForegroundColor Gray
    }

    'Scan' {
        Write-Host "触发 Windows Update 扫描..." -ForegroundColor Cyan
        try {
            $session = New-Object -ComObject Microsoft.Update.Session
            $searcher = $session.CreateUpdateSearcher()
            $result = $searcher.Search("IsInstalled=0")
            Write-Host "找到 $($result.Updates.Count) 个可用更新" -ForegroundColor Green
            foreach ($u in $result.Updates) {
                Write-Host "  - $($u.Title)"
            }
        } catch {
            Write-Host "COM 搜索失败: $($_.Exception.Message)" -ForegroundColor Yellow
            Write-Host "改用 UsoClient StartScan ..."
        }
        if (Test-Path "$env:SystemRoot\System32\UsoClient.exe") {
            Start-Process -FilePath "$env:SystemRoot\System32\UsoClient.exe" -ArgumentList 'StartScan' -NoNewWindow -ErrorAction SilentlyContinue
            Write-Host "已发出 UsoClient StartScan" -ForegroundColor Green
        }
    }

    'Check' {
        Write-Host "`n=== 配置状态（对比 HardwareCompatibility 是否被写回）===" -ForegroundColor Cyan
        Show-State
        Write-Host "=== 组件包 ===" -ForegroundColor Cyan
        Show-Packages
        Write-Host "`n=== 磁盘上是否出现新包 ===" -ForegroundColor Cyan
        Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like '*WindowsWorkload*' } | Select-Object -ExpandProperty Name
    }

    'Restore' {
        if (-not (Test-Path $BackupPath)) { Write-Host "找不到备份文件: $BackupPath" -ForegroundColor Red; break }
        $obj = Get-Content $BackupPath -Raw | ConvertFrom-Json
        Write-Host "从 $BackupPath 还原..." -ForegroundColor Cyan
        foreach ($p in $obj.values.PSObject.Properties) {
            Set-ItemProperty -Path $KeyPath -Name $p.Name -Value $p.Value
            Write-Host "  $($p.Name) = $($p.Value)"
        }
        Write-Host "还原完成。当前状态:" -ForegroundColor Green
        Show-State
    }
}
