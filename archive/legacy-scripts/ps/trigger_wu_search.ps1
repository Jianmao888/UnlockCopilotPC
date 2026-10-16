# trigger_wu_search.ps1
# 强制一次真正的联网 WU 同步（不用缓存），让 WU 代理在本进程内发出 SOAP。
$ErrorActionPreference = 'Continue'

Write-Output "[wu] 创建 Update.Session ..."
$s = New-Object -ComObject Microsoft.Update.Session
$q = $s.CreateUpdateSearcher()
$q.Online = $true

foreach ($sel in @(2, 3)) {
    $q.ServerSelection = $sel
    foreach ($crit in @(
        "IsInstalled=0",
        "IsInstalled=0 and Type='Software'",
        "IsInstalled=0 and IsHidden=0"
    )) {
        try {
            Write-Output "[wu] ServerSelection=$sel  Search('$crit') ..."
            $r = $q.Search($crit)
            Write-Output "[wu]   -> $($r.Updates.Count) 条"
        } catch {
            Write-Output "[wu]   失败: $($_.Exception.Message.Split([Environment]::NewLine)[0])"
        }
    }
}

# 查一次"隐藏/可选"更新，通常需要联网
try {
    $q.ServerSelection = 2
    Write-Output "[wu] 查询可选更新 ..."
    $r = $q.Search("IsInstalled=0 and BrowseOnly=1")
    Write-Output "[wu]   -> $($r.Updates.Count) 条"
} catch {
    Write-Output "[wu]   失败: $($_.Exception.Message.Split([Environment]::NewLine)[0])"
}

Write-Output "[wu] 等待尾部流量 10 秒..."
Start-Sleep -Seconds 10
Write-Output "[wu] 退出"
