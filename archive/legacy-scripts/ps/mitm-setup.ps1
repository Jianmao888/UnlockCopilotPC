# mitm-setup.ps1 —— 需要管理员
# 安装机器级 CA + 设置机器级 WinHTTP 代理，让 SYSTEM 服务的 WU 流量也走本地 MITM。
param([string]$CaCrt, [int]$Port = 8899)

$ErrorActionPreference = 'Continue'
Write-Output "[setup] 安装机器级 CA: $CaCrt"
certutil -f -addstore Root $CaCrt 2>&1 | Select-Object -Last 3

Write-Output "[setup] 设置 WinHTTP 代理 -> 127.0.0.1:$Port"
netsh winhttp set proxy "127.0.0.1:$Port" 2>&1 | Select-Object -Last 3

Write-Output "[setup] 当前 WinHTTP 代理:"
netsh winhttp show proxy 2>&1 | Select-Object -Last 4
Write-Output "[setup] 完成"
