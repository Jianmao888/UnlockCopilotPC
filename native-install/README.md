# 当前安装入口与历史探针

现行调用链是 `tools/run_install.py` → `Invoke-Install.ps1` → `InstallRunner.cs`，失败判据在 `Assert-DeploymentResult.ps1`。先按根目录 `docs/06` 取得和组装固定产品内容。

- `--validate-only`：普通文件核对，不加载部署 DLL/Frida。
- `--plan-only` 或未指定操作：管理员原版规划，不调用 Install。
- `--install`：明确实际部署。新运行名，一次一个。

这些入口验证固定 RUM CAB、引擎和载荷，仍不是跨 Windows 版本通用安装器。权限窄化插件地址只能用于匹配文件。

其他下载/整理工具和 `ocrprobe` 是历史研究材料，部分保留作者目录与代理，不能直接当重装恢复步骤。现行下载/组装改用根目录 `tools/acquire/`、`tools/extract-product-metadata.py`、`tools/prepare-product.py`。
