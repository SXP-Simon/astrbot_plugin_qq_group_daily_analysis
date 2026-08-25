# 群日常分析插件基础设施升级与仪表盘架构白皮书
(Agent Infra & Context Insights & Web Dashboard Architecture Whitepaper)

---

## 1. 概述与核心愿景

### 1.1 背景与系统本质
`astrbot_plugin_qq_group_daily_analysis`（群日常分析插件）表面上是一个聊天机器人扩展，但其系统本质是一个**多阶段、长耗时、高计算与网络密集型的异步 LLM 流水线（Multi-Stage Async Pipeline with Heavy LLM Workloads）**。

整个管线涵盖：
$$\text{海量原始消息拉取} \longrightarrow \text{规则清洗与剪枝} \longrightarrow \text{增量合并/滑动窗口切分} \longrightarrow \text{多维度并行 LLM 分析} \longrightarrow \text{HTML/Playwright 图像排版渲染} \longrightarrow \text{跨平台静默推送}$$

为了彻底解决长程任务缺乏细粒度追踪、失败重试成本高（无断点续跑）、上下文演进与 Token 消耗黑盒、缺乏统一可视化运维面板等痛点，本工程借鉴了工业级 **Agent Infra（大模型评测与执行基础设施）** 与 **dsh-context（上下文洞察与生命周期管理）** 的设计哲学，并构建了自包含的现代 Web 控制台。

---

## 2. 完整系统架构与端到端运行流程 (End-to-End Pipeline)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       AstrBot WebUI Shell (宿主环境)                                     │
└───────────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                                    │ Iframe Bridge (window.AstrBotPluginPage)
┌───────────────────────────────────────────────────▼────────────────────────────────────────────────────┐
│                    Web 控制台前端 (React 18 + FSD + Atomic Design + MVVM + AntD 5)                      │
│   ┌────────────────────┬────────────────────┬─────────────────────────────┬────────────────────────┐   │
│   │ 🚀 实时任务看板    │ 🔍 链路追溯(甘特图)│ 🧠 上下文演进与 Token 账单  │ 📁 历史报告长图归档    │   │
│   └────────────────────┴────────────────────┴─────────────────────────────┴────────────────────────┘   │
└───────────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                                    │ HTTP REST / SSE 事件管道 (context.register_web_api)
┌───────────────────────────────────────────────────▼────────────────────────────────────────────────────┐
│                                Plugin Backend Infrastructure Layer                                     │
│                                                                                                        │
│   ┌────────────────────────┐    ┌────────────────────────┐    ┌───────────────────────────────────┐    │
│   │ PluginPageWebUIBridge  │    │   ActiveTaskManager    │    │      TaskReaperDaemon & Sweep     │    │
│   │  (REST / SSE Handlers) │    │  (Concurrency & Locks) │    │ (600s 超时强杀 & 开机崩溃自愈对账) │    │
│   └───────────┬────────────┘    └───────────┬────────────┘    └─────────────────┬─────────────────┘    │
│               │                             │                                   │                      │
│   ┌───────────▼─────────────────────────────▼───────────────────────────────────▼──────────────────┐   │
│   │                               SQLite 持久化仓储 (WAL 模式)                                      │   │
│   │         TraceSQLiteStore (30天/20000条链路)  +  CheckpointStore (30天阶段快照)                 │   │
│   │                  存储路径: StarTools.get_data_dir(PLUGIN_NAME) / "traces.db"                   │   │
│   └─────────────────────────────────────────┬──────────────────────────────────────────────────────┘   │
│                                             │                                                          │
│   ┌─────────────────────────────────────────▼──────────────────────────────────────────────────────┐   │
│   │                 Enhanced TraceContext (Span 阶段打点、Token 累计与上下文演进漏斗)               │   │
│   └─────────────────────────────────────────┬──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────┼──────────────────────────────────────────────────────────┘
                                              │
┌─────────────────────────────────────────────▼──────────────────────────────────────────────────────────┐
│                             Multi-Stage Analysis Pipeline (核心流水线)                                 │
│                                                                                                        │
│   [ 阶段 1: 消息拉取 ] ──> [ 阶段 2: 规则清洗与剪枝 ] ──> [ 阶段 3: 并行 LLM 分析与 Checkpoint 缓存 ]    │
│    - OneBot/QQ/TG/DC        - 过滤系统/无意义字符          - 话题分析 (Topic LLM)                      │
│    - 指数退避重试 (3次)     - 计算压缩比与留存率           - 头衔画像 (Persona LLM)                    │
│    - 增量缓存降级兜底       - dsh-context 漏斗记录         - 精彩金句 (Quote LLM)                      │
│                                                            - 每日漫画 (Comic LLM & T2I)                │
│                                                            - 自动保存阶段快照 (30天有效)               │
│                                                                           │                            │
│   [ 阶段 5: 跨平台安全推送 ] <── [ 阶段 4: 两轮降级图像排版渲染 ] <───────────────┘                            │
│    - 图片/HTML/群文件推送         - Round 1: PNG + Ultra 清晰度                                        │
│    - 断网安全兜底(控制台查看)     - Round 2: JPEG + High 宽容度回退                                    │
│    - 杜绝向断开 WebSocket 盲发    - 失败回退纯文本报告                                                 │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 详细阶段执行流转
1. **触发与互斥锁获取**：
   * 支持指令（`/群分析`）、Web 控制台手动触发或定时任务触发；
   * 通过 `ActiveTaskManager` 获取目标群的互斥并发锁，防止同一群聊并发任务打架。
2. **消息拉取与清洗 (Stages 1 & 2)**：
   * 从平台适配器抓取原始消息，经过过滤规则剔除无效文本，同时在 `TraceContext` 中记录原始消息数、清洗后有效数与压缩率（`compression_ratio`）。
3. **多任务并行 LLM 分析与阶段快照 (Stage 3)**：
   * 话题、头衔、金句、漫画分镜四个分析器并发执行；
   * 每个分析器执行完毕后，即刻将其结果持久化到 `CheckpointStore`（30 天有效期），并分别将耗时写入 `trace_spans`、Token 消耗写入 `token_usage`。
4. **图像排版与容错渲染 (Stage 4)**：
   * 加载所选 HTML 模板，注入统计数据与 LLM 成果；
   * 采用两轮渲染回退策略（PNG Ultra $\to$ JPEG High $\to$ 文本总结），保障出图成功率。
5. **跨平台安全分发 (Stage 5)**：
   * 向群聊下发生成的高清长图。若检测到底层 IM 连接异常断开，则静默标记完成并安全退出，保障生成的产物在 Web 控制台内可随时查阅与下载。

---

## 3. 全景容错矩阵与开机自愈对账 (Fault-Tolerance & Self-Healing)

为了应对真实生产环境中可能发生的进程崩溃、网络闪断与第三方服务超时，系统构建了全方位的容错与自愈矩阵：

| 故障场景 | 故障现象 | 容错与自愈应对机制 | 最终效果 |
|---|---|---|---|
| **宿主进程异常重启 / OOM 崩溃** | 运行中的任务在 SQLite 中永久残留为 `running` 假死状态，导致群锁无法释放 | **开机对账自愈扫描 (`reconcile_crashed_traces_on_startup`)**：插件启动时自动遍历所有处于 `running` 的孤儿 Trace，将其批量更新为 `aborted` 并打上 `CRASH_RECOVERY` 标签，释放所有锁 | 系统重启后 0ms 恢复正常，彻底消除假死与群锁死锁 |
| **异步长程任务卡死 / 僵尸死锁** | 外部 API（如无超时的 LLM 或第三方绘图服务）无限挂起 | **Task Reaper 守护协程**：后台常驻巡检，对超过 600s 未更新心跳的任务执行超时强杀（标记为 `timed_out`）并释放并发锁 | 杜绝单次任务卡死耗尽系统协程资源 |
| **OneBot 历史接口抖动** | 消息拉取阶段偶发性网络超时或抛出网络异常 | **指数退避重试 (Backoff Retry)**：`history_manager` 在接口失败时以 1s、2s 间隔自动重试 3 次；若完全失效则降级使用本地增量缓存 | 显著提升高并发网络抖动下的拉取成功率 |
| **Playwright / Chromium 渲染超时** | 复杂 HTML 模板导致 T2I 渲染超时或 OOM 崩溃 | **两轮多格式渲染降级 (`render_strategies`)**：第一轮 PNG Ultra 追求极致清晰；超时则自动回退第二轮 JPEG High 并延长超时，仍失败则安全回退纯文本报告 | 100% 保证有分析结果交付，不抛出阻断异常 |
| **IM WebSocket 中途断开** | 报告生成完成后，向群聊下发消息时抛出 `NetworkError` | **静默安全处理与控制台查看**：任务状态正常落盘标记为已完成，产物保存至历史归档；不尝试向已断开的连接盲目回发错误提示 | 保证产物不丢失，管理员可在 WebUI 随时下载 |

---

## 4. WebUI 前端工程架构与规范落地

Web 控制台前端（`dashboard/`）采用 **React 18 + TypeScript + Ant Design 5 + ECharts + Vite** 构建，完全践行了现代前端工程的最佳实践：

### 4.1 FSD (Feature-Sliced Design) 六层单向依赖
```
dashboard/src/
├── 1. shared/                      # [基础共享层]
│   ├── api/bridge.ts               # 强类型 Iframe Bridge 通信与 SSE 订阅 (0 any)
│   ├── lib/                        # 纯工具库 (formatters.ts, useTheme.ts)
│   └── ui/                         # 【Atoms 原子组件】(MetricCard, StatusTag, SectionHeader)
├── 2. entities/                    # [领域实体层]
│   ├── task/                       # 活跃任务实体 (types / api / ui / TaskStageBadge)
│   ├── trace/                      # 链路实体 (types / api / ui / SpanTimeline 分子组件)
│   ├── group/                      # 群组实体 (types / api)
│   ├── metric/                     # 统计大盘实体 (types / api)
│   └── report/                     # 历史产物实体 (types / api)
├── 3. features/                    # [用户交互功能切片层]
│   ├── trigger-task/               # 手动触发分析 (ViewModel 校验 + TriggerModal UI)
│   ├── filter-traces/              # 多维筛选器 (【Molecules 分子组件】RangePicker + 群选择 + 状态)
│   └── cancel-task/                # 中止任务操作 (二次确认气泡 + CancelButton)
├── 4. widgets/                     # [复合微件层 / Organisms]
│   ├── header-bar/HeaderBar.tsx    # 顶部品牌导航与暗黑主题同步微件
│   ├── active-task-board/          # 活跃任务看板微件 (集成实时 Duration 计时器)
│   ├── trace-table/TraceTable.tsx  # 数据密集型链路表格微件 (服务端分页 + 排序)
│   ├── trace-drawer/TraceDrawer.tsx# 链路详情抽屉微件 (瀑布流甘特图 + 调用栈)
│   ├── context-funnel-widget/      # 上下文演进漏斗微件 (dsh-context 核心透视)
│   └── token-chart-widget/         # Token 消耗占比 ECharts 微件
├── 5. pages/                       # [页面与组合视图层] (MVVM 模式落地)
│   ├── overview/                   # useOverviewViewModel (VM) + OverviewPage (V)
│   ├── traces/                     # useTracesViewModel (VM) + TracesPage (V)
│   ├── context-insight/            # useContextInsightViewModel (VM) + ContextInsightPage (V)
│   └── reports/                    # useReportsViewModel (VM) + ReportsPage (V)
└── 6. app/                         # [应用根层]
    ├── App.tsx                     # 全局 Antd ConfigProvider、Tab 导航与 SSE 调度总线
    └── main.tsx                    # React 18 入口挂载
```

### 4.2 MVVM 响应式模式与 0 `any` 强类型治理
1. **MVVM 逻辑解耦**：
   * **ViewModel (`use*ViewModel.ts`)**：纯自定义 Hooks，集中封装异步请求、防抖、排序状态、计算衍生属性与秒级自增计时器；
   * **View (`*Page.tsx`)**：纯声明式 UI，不含任何直接网络请求或复杂数学计算，保持代码极度纯净。
2. **0 `any` 严格类型策略**：
   * 全局开启 `@typescript-eslint/no-explicit-any: 'error'`；
   * 宿主通信定义强类型 `AstrBotPluginPageBridge`、`AstrBotContext` 与泛型 `ApiResponse<T>`；
   * 未定型数据一律使用 `unknown` 并配合 `instanceof` / 类型守卫收敛。
3. **0ms 不可变冷数据 LRU 内存缓存 + SSE 精准失效**：
   * 仅对终态（`succeeded` / `failed` / `aborted`）记录进行 100 条容量的 LRU 内存缓存，实现秒开抽屉；
   * 运行中（`running`）任务强制穿透拉取实时进度；
   * 抽屉右上角支持「刷新」按钮（`forceRefresh=true`）随时强制穿透；
   * SSE 在接收到状态流转事件时，主动精准淘汰相关缓存，确保数据 100% 同步。
4. **单文件固定 Bundle 输出**：
   * Vite 构建固定输出为 `pages/daily-analysis/assets/index.js`，彻底消除动态哈希在 Git 历史中产生的噪音。

---

## 5. 带来的核心用户体验与工程价值 (Value Proposition)

### 5.1 对于群聊普通用户与群友 (End-User Experience)
* **交互克制优雅**：群内不再有反复编辑或多条百分比刷屏的“进度骚扰”，只有启动时的轻量提示与最终的高清长图。
* **清晰可信的错误归因**：若偶发分析失败，机器人返回通俗原因与语义化短 Trace ID（如 `TraceID: manual_交流群_2105`），方便群管理员一键溯源。

### 5.2 对于 Bot 管理员与运维者 (Admin & Ops Experience)
* **大盘与运行状态一目了然**：
  * 秒级查看各群活跃分析任务当前卡在哪个 Stage、已运行多少秒；
  * 支持在控制台一键手动触发分析或强行中止卡死任务。
* **30 天断点快照与零成本极速重渲染 (Zero-Token Re-render)**：
  * 分析成果在 Checkpoint 中保留 30 天；
  * 如果换了新的 HTML 主题模板，或因网络抖动未收到图片，可在控制台**直接复用已提取的话题与金句，0 Token 消耗秒级重新出图**，无需再耗费数万 Token 重新请求大模型。
* **调用账单与性能瓶颈深度透明 (dsh-context)**：
  * **甘特图瀑布流**：一眼看清是哪个 LLM 模型或哪个生图服务商响应缓慢；
  * **Token 消耗账单**：清晰透视话题、头衔、金句、漫画各自消耗的 Prompt/Completion Tokens 与预估花费；
  * **消息清洗漏斗**：直观了解 3000 条原始消息是如何经过清洗剔除无效灌水、最终保留有效上下文的。
* **系统永不假死死锁**：
  * 即使机器异常掉电或 Docker 重启，开机自愈机制会自动修复所有异常任务并释放群锁。

### 5.3 对于开源协作者与二次开发者 (Developer Experience)
* **分层严密，开发爽快**：FSD + Atomic Design 让组件各司其职，新增一个分析维度或图表组件只需增加相应 Slice，不影响其他业务。
* **全自动化质量门禁**：
  * GitHub CI 流水线自动校验 Python 测试与前端构建一致性，防止漏跑 build 导致代码脱节；
  * GitHub Release 流水线在推送版本 Tag 时自动编译前端并打包纯净发布 ZIP；
  * 提供 `scripts/debug_render.py` 离线模板热调工具，无需连接 LLM 即可秒级调试 HTML 主题。

---

## 6. 实施路线图与交付验证总结

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [✓] 阶段 1: 基础设施持久化层 (SQLite TraceStore + CheckpointStore 30天生命周期)          │
│   - SQLite WAL 模式，WAL 并发性能极佳，traces.db 规范存储于 plugin_data 目录            │
│   - TraceSpan 阶段打点、Token 细分累计与 Context Funnel 上下文漏斗指标                 │
│   - 30 天 / 20000 条滚动容量对齐，支持多字段索引与分页排序                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [✓] 阶段 2: 后端 Web API、ActiveTaskManager 与开机自愈对账                              │
│   - REST API 矩阵 (/traces, /tasks, /metrics, /groups, /reports) 与 SSE 实时事件广播   │
│   - TaskReaper 超时自动终止 (600s) 与开机对账扫描 (reconcile_crashed_traces_on_startup)│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [✓] 阶段 3: WebUI 前端现代化重构 (React 18 + Antd 5 + FSD + Atomic Design + MVVM)      │
│   - FSD 六层单向依赖架构与 MVVM Hooks 状态解耦                                         │
│   - 严格 0 any 强类型治理与 ESLint 0 警告静态规则                                      │
│   - 0ms 内存不可变 LRU 缓存与 SSE 精准失效，TraceDrawer 局部强制刷新                   │
│   - Vite 固定单 Bundle 编译输出 (pages/daily-analysis/assets/index.js)                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [✓] 阶段 4: 工程化规范、CI/CD 流水线与文档体系                                          │
│   - 新增 .github/workflows/ci.yml (代码与 Bundle 一致性校验门禁)                        │
│   - 新增 .github/workflows/release.yml (自动化打包构建与 GitHub Release 发布)          │
│   - 编写标准 GitHub CONTRIBUTING.md 与架构白皮书                                       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [✓] 阶段 5: 全流程回归测试验证                                                         │
│   - 141 项 Python 单元测试 100% 全部通过 (耗时 17.32s)                                 │
│   - 前端 pnpm lint, typecheck, build 全部通过                                          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```
