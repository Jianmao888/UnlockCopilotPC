# archive（历史探索脚本与数据）

这里是**探索阶段（2026-10-12 ~ 10-14）的原始脚本与数据**，已按类型归档。
**它们不是操作依据**——当前可用的工具在 `native-install\tools\`，流程在 `docs\01`、WSE 在 `docs\03`。

## 结构

```
legacy-scripts\ps\   根目录遗留的 PowerShell 脚本（55 个）
legacy-scripts\cmd\  遗留的命令行批处理（10 个）
legacy-scripts\py\   遗留的 Python 探针/工具（141 个）
legacy-data\xml\     WU 元数据/目录实验的 XML 与响应（33 个）
legacy-data\logs\    那一阶段的运行日志（13 个）
legacy-data\misc\    ETW 抓取、补丁前快照等（3 个）
```

## 已被取代（不要再用）

| 归档内容 | 现在用什么 |
|---|---|
| `srd*.py` / `srd-probe*` / 各种 `.srd` 副本 | `tools/inspect-uup-products.py`（只读事务/SQLite backup；见 docs/01 的 WAL 一致性说明） |
| `frida_*.py`（早期 WinRT 就绪态探针） | 安装用 `native-install/tools/`；模型执行/Click to Do 另见 docs/04，二者不可互换 |
| `fetch_all_ai_payloads.py` / `fetch_legacy_payloads.py` | `native-install\tools\auto-fetch-missing.py`、`prepare-new-products2.py` |
| `wu_*.py` / `wu-*.ps1`（WU 元数据侦察） | `native-install\tools\metaA-*.py`、`find-product-metadata.py` |
| `register_uup_products.py` / `write-uup-rows*.ps1`（手写 SRD 行） | ❌ **已弃用**：产品登记必须走部署会话（见 docs/01），不要手改 StateRepository |
| `organize_packages.py` | `native-install\tools\organise-products.py` |
| `hook_npudetect*.py`、`probe-npudetect.ps1`、`fix-npu-type.ps1` | NPU 检测相关结论已写入 docs/03；后续不再需要 |

## 仍有参考价值的

- `oneocr_*.py`（oneocr/OpenVINO CPU 路径验证）、`ensure_ready_probe.py`、`probe_statics.py`、`probe_mgr.py`（WinRT statics 探针）
- `ghidra_decompile*.py`、`vtable_probe.py`（反编译与 vtable 探测）
- `ms_store_download.py`（Store 下载）
- `capture_soap.py` / `capture_wu.py` / `mitm_wu.py`（WU 协议抓取）

需要复现早期结论时再翻这里的脚本；日常操作请只看 `docs\`。
