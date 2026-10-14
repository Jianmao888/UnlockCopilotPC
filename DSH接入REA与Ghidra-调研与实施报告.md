# 让 DSH 使用 REA 并驱动本机 Ghidra —— 调研与实施报告

- 目标：让 DSH（DeepSeek Harness，本机 Web GUI `http://127.0.0.1:19387`）能够调用 REA（Reverse Engineer Anything，`rea-agents`），并且由 REA 直接驱动本机已安装的 Ghidra 做原生二进制分析。
- 状态：**已在本机实施并端到端实测通过**（不是纸面方案）。当前运行中的 GUI 已能直接调用 `mcp__rea__*` 工具，实测完成了「打开 PE → 全量分析 → 取伪代码」全链路。
- 日期：2026-10-14

---

## 1. 结论（先看这一段）

1. DSH 自带 MCP 客户端插件 `@deepseek-ai/dsh-mcp-client`，任何「本地 stdio MCP 服务器」都能被注册成本会话的原生工具（命名为 `mcp__<serverName>__<tool>`）。DSH 本身**不需要**改代码。
2. REA 6.4.0 就是这样一个 MCP 服务器：命令是 `node <rea-agents>/scripts/rea.mjs mcp`，共暴露 **170 个 MCP 工具 / 6 个 prompt**。
3. REA 内置 Ghidra provider：只要设置 `GHIDRA_INSTALL_DIR`（Ghidra 12.1.x 解压目录），REA 就会用 `support\analyzeHeadless.bat` 起 Ghidra 无界面分析。**不需要**打开 Ghidra GUI，也**不需要**装任何 Ghidra 插件（不是 GhidraMCP 那种桥）。
4. 接入点不是改 profile（桌面 profile 被 Electron 应用独占管理，CLI 会拒绝启动/导出），而是 DSH 的**机器级用户补丁层** `~/.dsh/cordis.patch.yml`，用 `- insert:` 追加一条 MCP 服务器条目。写入后**应用热加载**，无需重启（上游文档建议重启，本机实测热加载即生效）。
5. 实测结果：`AIComponentMgmt.dll`（PE x86-64，SHA-256 `e18b734e…b8133b1`）经 DSH → REA → Ghidra 12.1.4 分析得到 8 个段、**860 个函数**、**384 个字符串**，并能取回 Ghidra 反编译伪代码。上游 provider 明确记录为 `ghidra 12.1.4`，证据 ID `ev_6cf5513bc8b5c59d52510ede930ddad5da6f7e1930e0c8b13cb1cb024abc654d`。
6. 上游新版本已把 DSH 当**一等客户端**：REA main / 6.5.0 的 `rea setup --client dsh` 会自动写入与本文手工配置**完全一致**的条目（见第 11 节）。当前 6.4.0 没有 `dsh`，所以是本报告手工接入。

---

## 2. 原理链路

```
DSH 桌面应用（Electron，profile=desktop）
  └─ 补丁层顺序: bundle 层 → profile 的 cordis.patch.yml → ~/.dsh/cordis.patch.yml（本机层） → --patch 覆盖层
       └─ 本机层中 `- insert:` 一条 dsh-mcp-client 行
            └─ MCP stdio 子进程: node.exe rea-agents\scripts\rea.mjs mcp
                 └─ REA provider（env REA_ANALYSIS_PROVIDER=ghidra）
                      └─ Ghidra support\analyzeHeadless.bat（-readOnly -deleteProject，JAVA_HOME=JDK 21）
                           └─ 结果以 Evidence 形式原路返回，模型侧看到的是 mcp__rea__<tool>
```

关键源码依据（本地已安装包，非猜测）：

| 事实 | 依据 |
| --- | --- |
| 工具名形如 `mcp__<serverName>__<tool>`，字段为 `serverName`/`transport`/`command`/`args`/`env`/`cwd`/`toolCallTimeoutMs`/`failOnStartupError`/`reconnect.*` | `~/.dsh/profiles/node_modules/@deepseek-ai/dsh-mcp-client/README.md` |
| 机器级补丁层路径 `$DSH_HOME/cordis.patch.yml`，且**优先级高于** profile 自身层 | `@deepseek-ai/dsh/lib/profile-boot-*.js`：`homePatchPath()` 及其注释「applied over every profile's own layer」 |
| 补丁文件名常量 `cordis.patch.yml` | `@deepseek-ai/dsh-app-boot/lib/index.js:314` |
| 新增条目必须包在 `- insert:` 列表里（裸 `- id:` 不是插入语义） | `app.asar` → `/dsh/node_modules/@deepseek-ai/dsh-agent-preset/skills/cordis-plugin-development/templates/mcp/cordis.patch.yml`，同目录 `references/mcp-bundle.md` |
| 桌面 profile 由应用独占，CLI 不能 boot/dump | 实跑 `dsh --profile desktop --dump-config` → `error: profile "desktop" is managed exclusively by the Electron application` |
| REA 的 MCP 子命令与注册命令行 | `rea-agents/dist/mcpDoctor.js`（`[dispatcherPath, "mcp"]`）；`rea doctor --json` 中已对齐的 Codex 条目：`["C:\\Program Files\\nodejs\\node.exe", "…\\rea-agents\\scripts\\rea.mjs", "mcp"]` |

---

## 3. 本机环境事实

| 组件 | 版本 / 路径 |
| --- | --- |
| DSH 桌面应用 | `DeepSeek Harness.exe` 0.2.0-rc.2；GUI `http://127.0.0.1:19387` |
| DSH 插件目录 | `C:\Users\jianm\.dsh\profiles\node_modules\@deepseek-ai\` |
| MCP 桥插件 | `@deepseek-ai/dsh-mcp-client` 0.1.5-rc.2 |
| REA | `rea-agents` **6.4.0**（本次已全局安装）→ `C:\Users\jianm\AppData\Roaming\npm\node_modules\rea-agents\scripts\rea.mjs` |
| Node.js | `C:\Program Files\nodejs\node.exe` v24.19.0（REA 要求 22.19+/24.11+/26+，满足） |
| Ghidra | `C:\Users\jianm\Downloads\ghidra_12.1.4_PUBLIC_20260921\ghidra_12.1.4_PUBLIC`（12.1.4，`application.java.min=21`） |
| JDK | `C:\Program Files\Java\jdk-21.0.12`（64 位完整 JDK 21，Ghidra 要求 21+） |
| 备注 | 系统 PATH 上的 `java` 是 25.0.4；显式给 `JAVA_HOME` 指定 21 可避免版本歧义。本机存在**两份完整 Ghidra 12.1.4**（另一份在 `%LOCALAPPDATA%\Programs\ghidra_12.1.4_PUBLIC`），见第 12 节 |

`rea doctor` 里 **Ghidra provider inspection 的 9 项全部通过**（注意：doctor 整体 `healthy:false`，因为 IDA 未配置、若干客户端注册未对齐——那是别的问题，与本链路无关）：

| 检查项 | 结果 |
| --- | --- |
| ghidra / ghidra-platform / ghidra-architecture | healthy（win32 / x64） |
| ghidra-installation / ghidra-version | healthy（`Ghidra\application.properties`，12.1.4） |
| ghidra-headless | healthy（`support\analyzeHeadless.bat`） |
| ghidra-native_decompiler | healthy（`decompile.exe` 报告 pe x86_64，与主机匹配） |
| ghidra-java | healthy（21.0.12；64-bit；JDK） |
| ghidra-native_authority | healthy（Windows 原生 Job Object + 私有 DACL + 防重解析句柄；仅本地 NTFS） |

---

## 4. 已实施的具体改动

### 4.1 安装 REA 到稳定路径

`npx` 缓存目录（`…\npm-cache\_npx\<hash>\…`）会被 npm 清理，把 MCP 服务器指过去不可靠，因此全局安装：

```powershell
npm install --global rea-agents@6.4.0
```

### 4.2 写入机器级用户补丁层（最终版本）

新建 `C:\Users\jianm\.dsh\cordis.patch.yml`（此前不存在）：

```yaml
- insert:
    - id: mcp-rea
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: rea
        transport: stdio
        command: 'C:\Program Files\nodejs\node.exe'
        args:
          - 'C:\Users\jianm\AppData\Roaming\npm\node_modules\rea-agents\scripts\rea.mjs'
          - 'mcp'
        env:
          REA_ANALYSIS_PROVIDER: 'ghidra'
          GHIDRA_INSTALL_DIR: 'C:\Users\jianm\Downloads\ghidra_12.1.4_PUBLIC_20260921\ghidra_12.1.4_PUBLIC'
          JAVA_HOME: 'C:\Program Files\Java\jdk-21.0.12'
          REA_GHIDRA_STARTUP_TIMEOUT_MS: '600000'
        toolCallTimeoutMs: 600000
        failOnStartupError: false
```

四个容易踩的点：

1. **必须用 `- insert:` 包裹**。DSH 自带模板就是这个形状；裸写 `- id: …` 不会被当作插入。
2. **放在 home 层而不是 desktop profile 里**。`~/.dsh/profiles/desktop/` 由应用自己管理（设置界面写入），手工改可能被后续设置写入覆盖；home 层是官方注释明确写的「machine-local preferences that apply to every profile」，并且优先级更高，对所有 profile（含 desktop/web/headless）都生效。
3. **超时是两条独立的限制，必须一起放宽**：
   - REA 侧 `REA_GHIDRA_STARTUP_TIMEOUT_MS`：**默认 330000 ms（330 秒）**（`dist\config\ghidraStartupTimeout.js`），管的是「导入 + 自动分析 + 桥接就绪」的总预算；
   - MCP 客户端侧 `toolCallTimeoutMs`：DSH 默认 60000 ms，而上游 SDK 自身默认也是 60 秒——**上游实测 Windows 冷启动 overlay 用了约 163 秒**，也就是说只放宽一边没用。
   本机两者统一设成 **600000 ms（10 分钟）**，给大目标留余量。
4. **`REA_ANALYSIS_PROVIDER: ghidra` 是显式钉住 provider**。REA 的 `auto` **不是** Hopper→Ghidra→IDA 的优先级顺序：它会在「可用且支持该目标」的 provider 里选唯一一个，**若同时有 2 个及以上就直接报 `ambiguous` 错误**。本机目前只有 Ghidra 可用，auto 也会落到 Ghidra，但显式指定最稳（CLI 等价写法 `--provider ghidra`，MCP 等价写法 `open_binary(provider_id: "ghidra")`）。

写好即生效：本会话工具列表随即出现 `mcp__rea__*`，DSH 也声明了 MCP 资源服务器 `rea`。

### 4.3 工作区内的可复用副本

- 配置副本：`.research/rea-dsh/cordis.patch.yml`（与线上文件一致）
- 一键脚本：`.research/rea-dsh/setup-dsh-rea.ps1`（检查环境 → 全局装 REA → 写 home 补丁 → 校验）

---

## 5. 验证证据（全部为实测，非推断）

### 5.1 REA 自身能驱动 Ghidra

不经过 DSH，直接用 CLI 跑一个 Windows 系统 DLL：

```powershell
$env:GHIDRA_INSTALL_DIR = "C:\Users\jianm\Downloads\ghidra_12.1.4_PUBLIC_20260921\ghidra_12.1.4_PUBLIC"
node "$env:APPDATA\npm\node_modules\rea-agents\scripts\rea.mjs" analyze C:\Windows\System32\version.dll --provider ghidra --format json
```

结果（`.research/rea-dsh/analyze-ghidra.json`）：`upstream provider = ghidra 12.1.4`，`format=pe`，`architecture=x86_64`，`process_launch=official-headless-script-v1`。

### 5.2 REA 的 MCP stdio 服务可用

用文件重定向喂入 `initialize` + `notifications/initialized` + `tools/list`：

- 响应 1：`{"protocolVersion":"2025-06-18", "serverInfo":{"name":"rea","version":"6.4.0"}, …}`
- 响应 2：`tools` 数组完整返回（原始输出 1.9 MB，`.research/rea-dsh/mcp-out.jsonl`）

### 5.3 在运行中的 GUI 里真正调用（决定性证据）

| 步骤 | 工具 | 结果 |
| --- | --- | --- |
| 注册可见性 | `list_mcp_resources(server="rea")` | `{"resources":[]}` —— 服务器已连上（REA 本身不暴露 MCP resources，符合其 capabilities） |
| 打开目标 | `mcp__rea__open_binary(path=…\ghidra-out\AIComponentMgmt.dll, provider_id=ghidra)` | `pe / executable / x86_64 / sha256=e18b734e…b8133b1` |
| 全量分析 | `mcp__rea__binary_overview` | 8 段、**860 函数**、**384 字符串**，`analysis_profile.upstream.provider = ghidra 12.1.4`；证据 `ev_6cf5513b…c654d` |
| 名称检索 | `mcp__rea__search_procedures("Main")` | 命中 `__scrt_dllmain_after_initialize_c @0x180002354` 等；证据 `ev_c7c0fa03…136a` |
| 取伪代码 | `mcp__rea__procedure_pseudo_code("0x180002354")` | 返回 Ghidra 反编译 C 代码（含 Ghidra 的「Library Function – Single Match」注释块）；证据 `ev_50febe39…942c` |

也就是说：**在这个 GUI 的对话里，直接叫模型去 `open_binary` / `analyze_function` / `procedure_pseudo_code`，它就会用本机 Ghidra 出结果。**

---

## 6. 其他可选接法（备选，未采用）

| 方案 | 做法 | 评价 |
| --- | --- | --- |
| A. 官方 setup（REA 6.5.0+） | `npm i -g rea-agents@latest` → `rea setup --client dsh` | 上游原生支持，自动写同一个 home 补丁文件并保留注释；**注意它不会帮你注入 `GHIDRA_INSTALL_DIR`/`JAVA_HOME`**，需要你自己设环境变量或事后补 env（见第 11 节） |
| B. 自建 profile（CLI） | `dsh --profile <name> --from-default-profile web` 初始化 → `dsh plugin --profile <name> add @deepseek-ai/dsh-mcp-client` → 在该 profile 的 `cordis.patch.yml` 加同样的 insert | 完全走 CLI，可版本化；但服务的是另一个 DSH 实例，不是当前桌面 GUI |
| C. 配置型 bundle + `plugin_manager` | 按 DSH 自带技能 `cordis-plugin-development` 的做法，建一个只含 `package.json` + `cordis.patch.yml` 的配置型 bundle，用 `plugin_manager` 安装 | DSH 文档推荐的「正规」做法，便于分发/多机复用；但本机是否暴露 `plugin_manager` 界面/工具尚未核实（见第 10 节），当前方案不依赖它 |
| D. 纯 CLI 调 REA | 不进 DSH，直接 `rea analyze` / `rea function` / `rea decompile` | 最省事，但丢掉 DSH 的对话与 Evidence 编排能力 |

---

## 7. 限制与风险（务必知悉）

### 7.1 Windows + Ghidra 是官方标注的 P0 / 只读边界

上游 `docs/windows-ghidra-p0.md` 与 REA 每次返回的 limitations 都写明：

- **状态**：experimental Windows x64、**只读 P0 边界**；不代表与 macOS/Linux 功能对等，Ghidra GUI 状态、注释、其他架构/格式、Hopper 专有操作都不可用。
- **支持范围**：Windows **10+ x64**；**固定本地 NTFS**，且**不允许重解析点**——UNC、SUBST、挂载文件夹、ADS、其他文件系统、可变路径都会被拒绝；目标必须是**原生非托管 x86 / x86-64 PE（EXE/DLL）**，或带显式入口的裸 NMOS 6502 镜像；**Ghidra 仅 12.1.x**（本机 12.1.4 已验证）；**64 位完整 JDK 21+**。
- **托管程序集走另一条路**：.NET/CLI 不要指望 Ghidra，用 REA 的 `inspect_managed_artifact` / `inspect_managed_members`（免执行的静态路径）。
- **Windows 上禁止数据库改动**：`annotate_native_function` / `set_address_name(s)` 在 Windows 上 `available: false`（`unsupported_host`，原因「Windows Ghidra P0 does not admit database mutation」）。PE load-image attestation 也是 unsupported；NativeAOT 目标在 Windows 上 `read_bytes` / `search_strings` 读不到 rehydrated 内容。
- **免 GUI、不改你的工程**：REA 只调 `support\analyzeHeadless.bat`，用临时工程 + 隔离的 home/cache/config/temp，传 `-readOnly -deleteProject`，**从不打开你已有的 Ghidra 工程**。Python/PyGhidra 不是前置条件。
- **临时目录与残留**：运行目录形如 `%LOCALAPPDATA%\Temp\rea-ghidra-<hash>`（内含临时工程、隔离 home/config/cache、以及**不可变目标快照**）。正常关闭会清理；但上游明确声明「**突然杀死宿主可以留下私有运行文件，崩溃时的事务化删除不做承诺**」——所以看到残留属预期行为，确认没有 REA/Ghidra 进程占用后再清。
- **函数体边界**：`no_return_repair: disabled-windows-p0`，配合 `function_boundary_observations: ghidra-terminal-call-limitations-v1`，意味着 Windows 上「无返回函数」修复被关闭，函数体可能被截断——结论里要保留这条不确定性。

### 7.2 「沙箱里跑 REA 会把 Java 误判为缺失」这个坑

如果在 DSH 的**受限沙箱**（如 `workspace-write`）里执行 REA 的 CLI，会看到：

```
ghidra-java  ok=false  classification=missing_dependency
detail: C:\Program Files\Java\jdk-21.0.12\bin\java.exe
```

这不是 Java 的问题，而是沙箱限制：Node 用管道 stdio 拉起子进程会 `spawn EPERM`（本机实测复现，见 `.research/java_probe.cjs`）。把同一命令放到非受限执行（或把文件策略设为 `danger-full-access`）后，`ghidra-java` 立刻 healthy。

实践含义：**别用受限沙箱去跑 `rea` 命令**；而通过 DSH MCP 桥起的 REA 子进程由应用进程派生，不受该限制——第 5.3 节已证明。

### 7.3 其他

- **token 开销**：170 个工具的描述与 input schema 会进入每次请求。上游提供两个开关，可加进同一条 `env`：`REA_MCP_INPUT_SCHEMA_PROFILE: compact`（压缩输入 schema）、`REA_MCP_OUTPUT_SCHEMA_PROFILE: off`（对端 stdio 读取器扛不住完整帧时用）。不需要时也可以直接给该条目加 `disabled: true`。
- **更新**：`rea update`（npm 全局安装时）；6.4.0 与上游 main 有漂移——**没有 `dsh` 客户端、没有 `GHIDRA_INSTALL_DIR` 的 PATH 自动发现（所以该变量是必需的）、没有 `REA_GHIDRA_DISABLED_ANALYZERS`**。照抄 main 的文档在 6.4.0 上会误导。
- **`rea setup` 不识别 DSH（6.4.0）**：它支持 claude_code / claude_desktop / codex / cursor / gemini_cli / windsurf / devin / opencode / antigravity / copilot_cli / commandcode / qwen_code / vscode / grok_build / omp / pi / hermes / grok_bot 等；**没有通用客户端 id**，因此只能手工注册（或升级到 6.5.0+ 用 `--client dsh`）。
- **技能文件**：`rea doctor` 报 `skill:identity` 偏旧（已装 version 37）。需要时可 `rea setup --skill --dry-run` 预览后 `rea setup --skill --yes` 刷新 `~/.agents/skills` 下的 REA 技能。
- 系统 PATH 上的 `java` 是 25；Ghidra 声明 `application.java.min=21`（本构建 `max` 未设），为稳妥起见配置里显式钉住 JDK 21。另外 REA 会主动清掉子进程里的 `_JAVA_OPTIONS`/`JAVA_TOOL_OPTIONS`/`JDK_JAVA_OPTIONS`/`GHIDRA_JAVA_OPTIONS`，避免外部干扰。

---

## 8. 回滚 / 调整

| 目的 | 操作 |
| --- | --- |
| 暂时关掉 | 在 `~/.dsh/cordis.patch.yml` 的该条目上加 `disabled: true` |
| 完全移除 | 删除 `C:\Users\jianm\.dsh\cordis.patch.yml`（该文件此前不存在，删除即回到原状） |
| 换 Ghidra 版本/路径 | 改该文件的 `GHIDRA_INSTALL_DIR` |
| 卸载 REA | `npm uninstall --global rea-agents` |
| 换 MCP 服务器名 | 改 `serverName`（工具名会变成 `mcp__<新名>__*`） |

---

## 9. 建议的日常用法

在 DSH 里直接说人话即可，例如：

- 「用 rea 打开 `…\AIComponentMgmt.dll`，列出引用了 `UUPProducts` 的函数并给伪代码」
- 「用 rea 分析 `C:\Windows\System32\version.dll` 的导出，并和上次的快照比对」

模型侧会落到 `mcp__rea__open_binary` → `mcp__rea__search_strings` → `mcp__rea__analyze_function` 这套工具上；结论应带 Evidence ID，且要区分「观测 / 推断 / 未知」。

若做长期项目：先把目标 `open_binary` 一次（Ghidra 分析只做一遍，之后调用走会话缓存），阶段性用 `export_evidence_bundle` 落盘，最后 `close_binary(snapshot_path=…)` 保存分析快照。注意 Windows 上分析是**临时导入**，`close_binary` 后数据库即删。

---

## 10. 待确认项（不阻塞使用）

1. `plugin_manager` 的具体宿主：DSH 自带文档建议用「配置型 bundle + `plugin_manager`」安装 MCP 集成。本机是否暴露该界面/工具**尚未核实**；当前 home 层方案不依赖它，且已被第 5 节证明可用。
2. 桌面应用的热加载边界：本次写入/修改 home 层后**当前会话即时生效**已实测两次；「是否所有后续新会话都自动带上」从层叠规则看是必然（每次 boot 都读该文件），但未逐一穷举验证；上游文档的建议是「改完重启 Harness」，按此操作也一定生效。

---

## 11. 上游已有原生 DSH 支持（REA 6.5.0+）

上游 main 的 `docs/client-configuration.md` 有专门的 **DeepSeek Harness** 一节，明确：

- DSH 通过 Cordis YAML 补丁序列注册 MCP，而不是 `mcpServers` 对象；
- `rea setup --client dsh` 会**追加（或替换）** `$DSH_HOME/cordis.patch.yml`（`DSH_HOME` 未设时为 `~/.dsh/cordis.patch.yml`）里的 REA 条目，**保留无关补丁与注释**；
- `rea doctor --client dsh` 校验同一个条目 id；`rea uninstall` 通过扫描受支持客户端来移除它；
- 注释里点明：**home 补丁对所有 profile 生效，所以写一次即可，不需要按 profile 改**——这正是本报告第 4 节的做法；
- 它写入的条目形如：

```yaml
- insert:
    - id: rea-mcp
      name: "@deepseek-ai/dsh-mcp-client"
      config:
        serverName: rea
        transport: stdio
        command: /absolute/path/to/node
        args: ["/absolute/path/to/rea/scripts/rea.mjs", mcp]
```

与本报告手工写的条目**结构完全一致**（只是我们把 `id` 写成 `mcp-rea`、并额外补了 provider env 与超时）。两点补充：

1. `rea setup --client dsh` **不会**注入 Ghidra/Java 配置——它只读取并保留**已存在**的 REA 条目 env（`dist\application\ClientRegistrationEnvironment.js`）。所以要保证 `GHIDRA_INSTALL_DIR`/`JAVA_HOME` 在用户环境里，或事后手工补进条目 env。
2. 上游文档写「Restart Harness after setup」；本机实测热加载也生效，重启更保险。

**建议**：等 6.5.0 正式发到 npm 后，`npm i -g rea-agents@latest && rea setup --client dsh`，再按需补 env，即可用官方命令替代本文的手工步骤（届时 `rea doctor --client dsh` 也能直接体检）。

---

## 12. 顺带发现（不在本次目标内，但值得处理）

1. **Codex 的 REA 注册指向 npx 缓存，很脆**：`C:\Users\jianm\.codex\config.toml:94-101` 用的是 `…\npm-cache\_npx\dea9475797100b20\node_modules\rea-agents\scripts\rea.mjs`。`_npx` 目录会被 npm 清理，将来一次 `npx rea-agents@latest` 也可能把它换成别的版本——建议改指全局安装路径 `…\AppData\Roaming\npm\node_modules\rea-agents\scripts\rea.mjs`。
2. **两个客户端钉了两份不同的 Ghidra**：Codex 的 env 用 `%LOCALAPPDATA%\Programs\ghidra_12.1.4_PUBLIC`，DSH 和本次 doctor 验证用 `Downloads\ghidra_12.1.4_PUBLIC_20260921\ghidra_12.1.4_PUBLIC`。两份都是完整的 12.1.4（properties + `decompile.exe` 均已核对），今天都能用，但会各自漂移；建议统一成一个规范路径。
3. **`rea doctor` 整体并不 healthy**（`healthy:false`、`environment_healthy:false`）：IDA 未配置，claude_code / copilot_cli / opencode / vscode 四个检测到的客户端注册未对齐。只有 **Ghidra provider inspection 那一组是 9/9 全绿**——这两个结论不要混为一谈。

---

## 附：产物与证据文件

| 文件 | 说明 |
| --- | --- |
| `C:\Users\jianm\.dsh\cordis.patch.yml` | 实际生效的接入配置（本次新建，最终版见 4.2） |
| `.research/rea-dsh/cordis.patch.yml` | 同内容的可版本化副本 |
| `.research/rea-dsh/setup-dsh-rea.ps1` | 一键安装/写入/校验脚本 |
| `.research/rea-dsh/rea-ghidra-side.md` | REA + Ghidra 上游限制、env 变量、provider 选择、官方注册形状的调研（含引用） |
| `.research/rea-dsh/upstream/` | 保存的上游文档原文（windows-ghidra-p0、installation、mcp-contracts、client-configuration 等） |
| `.research/rea-dsh/doctor-unsandboxed.json` | `rea doctor --json`（非受限执行，Ghidra 组全绿） |
| `.research/rea-dsh/analyze-ghidra.json` | CLI 侧 `analyze version.dll --provider ghidra` 的完整 Evidence |
| `.research/rea-dsh/mcp-out.jsonl` / `mcp-req.jsonl` | MCP stdio 握手与 `tools/list` 原始报文 |
| `.research/rea-dsh/dump-web-with-rea.yml` | 含 home 补丁的 profile 组合结果（证明 insert 生效） |
| `.research/rea-dsh/dsh-mcp-template/` | 从 `app.asar` 提取的 DSH 官方 MCP 模板与说明 |
| `.research/rea-dsh/java_probe.cjs` | 复现「沙箱内 Node 管道 spawn EPERM」的最小脚本 |
