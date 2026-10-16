# mitm-restore.ps1 —— 需要管理员
# 复位 WinHTTP 代理 + 移除机器级 CA
$ErrorActionPreference = 'Continue'

Write-Output "[restore] 复位 WinHTTP 代理"
netsh winhttp reset proxy 2>&1 | Select-Object -Last 3

Write-Output "[restore] 移除机器级 CA (DSH WU Capture CA)"
$certs = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -match 'DSH WU Capture' }
foreach ($c in $certs) {
    Write-Output "  删除 $($c.Thumbprint)"
    certutil -delstore Root $c.Thumbprint 2>&1 | Select-Object -Last 2
}
if (-not $certs) { Write-Output "  未找到该 CA（已清理）" }

Write-Output "[restore] 当前 WinHTTP 代理:"
netsh winhttp show proxy 2>&1 | Select-Object -Last 4
Write-Output "[restore] 完成"
