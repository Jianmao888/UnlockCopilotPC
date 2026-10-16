# 在非 Copilot+ PC 上启用 Windows AI 能力（Xiaomi Book Pro 16 2022 / i7-1260P / 无 NPU）

本仓库记录这条路上的**方法、证据、可复现步骤与回滚方案**。两条主线：
**① Windows AI 工作负载（产品登记）** ② **Windows Studio Effects（门禁已突破，效果待解）**

## 现在能用的（实测）

| 能力 | 状态 |
|---|---|
| **OCR / 文本识别** | ✅ 可用（`ContentExtraction.LNL`，9 条产品关系） |
| **语义搜索** | ✅ 可用（`Analysis.LNL`，20 条产品关系） |
| 图像搜索 / SettingsModel | 已登记（执行能力待验证） |
| **Windows Studio 效果入口** | ✅ 设置页 + 快速设置都有入口 |
| Windows Studio 效果「生效」 | ❌ 开启后相机不可用（根因已定位，见 03） |

## 文档地图

| 文档 | 用途 |
|---|---|
| [docs/00-现状快照与断点续传.md](docs/00-现状快照与断点续传.md) | **先看这个**：当前成果、系统坏了如何恢复、待办 |
| [docs/01-AI组件-获取与安装-防错流程.md](docs/01-AI组件-获取与安装-防错流程.md) | **照做即可**：7 条铁律 + 9 步流程 + 故障诊断 + 可直接复制的安装脚本 |
| [docs/02-AI组件-产品与载荷清单.md](docs/02-AI组件-产品与载荷清单.md) | 58 包 / 11 产品明细、系统改动清单、能力边界 |
| [docs/03-WSE-WindowsStudioEffects-攻坚记录.md](docs/03-WSE-WindowsStudioEffects-攻坚记录.md) | WSE 架构（INF 实证）、门禁突破步骤、当前卡点、下一步路线 |
| [docs/05-回滚与灾难恢复.md](docs/05-回滚与灾难恢复.md) | 全部改动的回滚命令 + 急救 + 从零重建 |
| [docs/90-存档/](docs/90-存档/) | 早期阶段性记录（备查，不再是操作依据） |
| [docs/91-REA接入/](docs/91-REA接入/) | DSH 接入 REA/Ghidra 的调研报告（独立话题） |

## 关键资产

```
ai-products\      11 个可直接安装的产品包（metadata + 载荷 + install.ps1 + INVENTORY.md）
native-install\   安装工具链（Frida 降权插件 + 部署会话安装 + 产品打包脚本）
wse\              Studio Effects 攻坚包与脚本
dumps\            StateRepository 快照（验证登记必须带 -wal，见 05）
```

## 三条最重要的经验（踩坑换来的）

1. **验证 StateRepository 必须带 `-wal`**：只复制 `.srd` 会读到旧快照，把成功误判为失败（本次最大代价）。
2. **安装工作负载产品**：载荷放**内容目录根层**、文件名严格等于 RUM 的 `PayloadName`、版本精确匹配；
   要触发产品登记必须**先卸该产品自己的包**再装（否则引擎空转）。
3. **WSE 门禁可伪造，算力不可伪造**：软件设备能凭空创建（入口出现），但效果执行需要 Intel NPU；
   绕过方式只有"换 CPU 后端"或"自实现效果源"。

## 复现前提

Windows 11 22H2+(22621) 以上 · x64 · 管理员权限 · 外网（本环境经代理 `127.0.0.1:7890`）
