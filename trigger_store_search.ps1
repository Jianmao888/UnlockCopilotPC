# trigger_store_search.ps1
# 通过 WinRT 触发 InstallService.dll 的 ProductScanner，让它发出 SOAP 请求。
# 只调用公开 API 做"搜索更新"，不修改任何系统状态。

$ErrorActionPreference = 'Continue'

function Wait-Async($op) {
    $n = 0
    while ($op.Status -eq 0 -and $n -lt 120) {   # 0 = Started
        Start-Sleep -Milliseconds 250
        $n++
    }
    return $op.Status
}

Write-Output "[trigger] 解析类型..."
$t = [Windows.ApplicationModel.Store.Preview.InstallControl.AppInstallManager, Windows.ApplicationModel.Store.Preview, ContentType=WindowsRuntime]
Write-Output "[trigger] 类型 = $($t.FullName)"

Write-Output "[trigger] 创建实例..."
$mgr = New-Object Windows.ApplicationModel.Store.Preview.InstallControl.AppInstallManager
Write-Output "[trigger] 实例 OK"

try {
    Write-Output "[trigger] SearchForAllUpdatesAsync() ..."
    $op = $mgr.SearchForAllUpdatesAsync()
    Write-Output "[trigger]   状态 = $(Wait-Async $op)"
} catch {
    Write-Output "[trigger]   SearchForAllUpdatesAsync 失败: $($_.Exception.Message)"
}

foreach ($productId in @('9nbhcs1lx4r0', '9wzdncrfjbmp')) {
    try {
        Write-Output "[trigger] SearchForUpdatesAsync($productId, '0010') ..."
        $op = $mgr.SearchForUpdatesAsync($productId, '0010')
        Write-Output "[trigger]   状态 = $(Wait-Async $op)"
    } catch {
        Write-Output "[trigger]   失败: $($_.Exception.Message)"
    }
}

try {
    Write-Output "[trigger] GetIsApplicableAsync ..."
    $op = $mgr.GetIsApplicableAsync('9nbhcs1lx4r0', '0010')
    Write-Output "[trigger]   状态 = $(Wait-Async $op)"
} catch {
    Write-Output "[trigger]   失败: $($_.Exception.Message)"
}

try {
    Write-Output "[trigger] AppInstallItems ..."
    $items = $mgr.AppInstallItems
    Write-Output "[trigger]   数量 = $($items.Count)"
} catch {
    Write-Output "[trigger]   失败: $($_.Exception.Message)"
}

Write-Output "[trigger] 等待尾部流量 8 秒..."
Start-Sleep -Seconds 8
Write-Output "[trigger] 退出"
