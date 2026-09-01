# QQ 群日常分析插件 - WebUI 控制台 (Dashboard)

本项目是 `astrbot_plugin_qq_group_daily_analysis` 的内嵌管理控制台前端工程，采用 **React 18 + TypeScript + Ant Design 5 + ECharts + Vite** 构建，完全遵循 **Feature-Sliced Design (FSD)**、**Atomic Design (原子设计)** 与 **MVVM (Model-View-ViewModel)** 现代前端架构范式。

---

## 1. 架构设计与分层规范 (Architecture & FSD Layers)

严格执行自底向上的六层单向依赖规范（下层不得反向依赖上层）：

```
dashboard/src/
├── 1. shared/                      # [基础共享层]
│   ├── api/bridge.ts               # 强类型 Iframe Bridge 通信与 SSE 订阅 (0 any)
│   ├── lib/                        # 纯工具库 (formatters.ts, useTheme.ts)
│   └── ui/                         # 【Atoms 原子组件】
│       ├── MetricCard.tsx          #   - 数据密集型 KPI 指标卡片
│       ├── StatusTag.tsx           #   - 统一状态指示器 (SUCCEEDED, FAILED...)
│       └── SectionHeader.tsx       #   - 统一区块标题头
│
├── 2. entities/                    # [领域实体层]
│   ├── task/                       # 活跃任务实体 (types / api / ui / TaskStageBadge)
│   ├── trace/                      # 链路实体 (types / api / ui / SpanTimeline 分子组件)
│   ├── group/                      # 群组实体 (types / api)
│   ├── metric/                     # 统计大盘实体 (types / api)
│   └── report/                     # 历史产物实体 (types / api)
│
├── 3. features/                    # [用户交互功能切片层]
│   ├── trigger-task/               # 手动触发分析 (ViewModel 校验 + TriggerModal UI)
│   ├── filter-traces/              # 多维筛选器 (【Molecules 分子组件】RangePicker + 群选择 + 状态)
│   └── cancel-task/                # 中止任务操作 (二次确认气泡 + CancelButton)
│
├── 4. widgets/                     # [复合微件层 / Organisms]
│   ├── header-bar/HeaderBar.tsx    # 顶部品牌导航与暗黑主题同步微件
│   ├── active-task-board/          # 活跃任务看板微件 (集成实时 Duration 计时器)
│   ├── trace-table/TraceTable.tsx  # 数据密集型链路表格微件 (服务端分页 + 排序)
│   ├── trace-drawer/TraceDrawer.tsx# 链路详情抽屉微件 (瀑布流甘特图 + 调用栈)
│   ├── context-funnel-widget/      # 上下文演进漏斗微件 (消息清洗漏斗与留存分析)
│   └── token-chart-widget/         # Token 消耗占比 ECharts 微件
│
├── 5. pages/                       # [页面与组合视图层] (MVVM 模式落地)
│   ├── overview/                   # useOverviewViewModel (VM) + OverviewPage (V)
│   ├── traces/                     # useTracesViewModel (VM) + TracesPage (V)
│   ├── context-insight/            # useContextInsightViewModel (VM) + ContextInsightPage (V)
│   └── reports/                    # useReportsViewModel (VM) + ReportsPage (V)
│
└── 6. app/                         # [应用根层]
    ├── App.tsx                     # 全局 Antd ConfigProvider、Tab 导航与 SSE 调度总线
    └── main.tsx                    # React 18 入口挂载
```

---

## 2. 核心设计范式 (Design Patterns)

### 2.1 MVVM 模式 (Model-View-ViewModel)
* **Model (数据与实体层)**：定义在 `src/entities/*/model/types.ts` 与 `src/entities/*/api/` 中，负责声明数据结构以及与后端 REST 接口交互。
* **ViewModel (视图逻辑与状态管理)**：通过自定义 Hooks 实现（如 `useTracesViewModel.ts`、`useOverviewViewModel.ts`），集中封装：
  * 数据远程请求与错误捕获；
  * 本地 UI 状态（搜索防抖、筛选条件、排序、分页）；
  * 衍生计算逻辑（时间格式化、百分比换算、秒级时长自增计时器）；
  * 暴露操作方法给 View 层。
* **View (纯声明式渲染组件)**：`src/pages/*/ui/` 中的页面组件不直接包含任何底层 API 调用，只接收 ViewModel 的数据和回调，保持界面逻辑高度纯净。

### 2.2 Atomic Design 组件粒度管理
* **Atoms (原子)**：`StatusTag`、`MetricCard`、`TaskStageBadge`、`SectionHeader`。
* **Molecules (分子)**：`TraceFilterBar`（复合筛选条）、`SpanTimeline`（阶段进度条与时间轴组合）、`CancelTaskButton`。
* **Organisms / Widgets (微件)**：`TraceTable`、`ActiveTaskBoard`、`ContextFunnelWidget`、`TokenChartWidget`、`TraceDrawer`。

### 2.3 UI 视觉与文案设计规范 (Zero-Emoji & Pure-Icon Policy)
* **全站严禁使用 Unicode Emoji 作为 UI 视觉元素**：
  * 所有页面标题、描述卡片、按钮前缀图标、时间轴标记一律使用 `@ant-design/icons` 提供的矢量矢量图标（如 `<BarChartOutlined />`、`<FolderOpenOutlined />`、`<ClockCircleOutlined />`、`<DatabaseOutlined />` 等）；
  * 杜绝跨平台/跨操作系统因系统 Emoji 渲染差异导致的对齐错位、彩色割裂或样式不一致。
* **文案清晰直观、小白友好（杜绝中英混杂与技术黑话）**：
  * **禁止中英混杂括号**：界面文案严禁出现 `中文 (English)` 的冗余双语后缀（如禁止出现 `话题 (Topics)`、`群组 (Group)`、`调用栈 (Stack Trace)` 等）；
  * **通俗化表达**：用用户熟悉的自然概念替代晦涩的后端内部黑话（如使用 `任务编号` 代替 `Trace ID`，使用 `模型消耗` 代替 `Tokens`，使用 `各阶段耗时明细` 代替 `Span Waterfall`）。

---

## 3. 严格的 TypeScript 类型规范 (Zero `any` Policy)

本项目全面禁止无意义的 `any` 类型：
1. **宿主 Bridge 通信**：在 `shared/api/bridge.ts` 中声明了完整的 `AstrBotPluginPageBridge`、`AstrBotContext` 与泛型 `ApiResponse<T>` 接口；
2. **未知数据兜底**：使用 `unknown` 代替 `any`，并在消费处通过 `instanceof` 或类型守卫进行类型收敛；
3. **第三方组件参数**：精确使用 Ant Design 导出的 `TablePaginationConfig`、`FilterValue`、`SorterResult` 等强类型。

---

## 4. 实时响应与数据流 (Data Flow & SSE Lifecycle)

1. **暗黑模式自适应**：
   * 通过 `useTheme` Hook 监听 AstrBot 宿主传入的 `isDark` 环境变量，自动在 Antd 的 `theme.darkAlgorithm` 和 `theme.defaultAlgorithm` 间无缝平滑切换。
2. **SSE (Server-Sent Events) 实时响应**：
   * 应用挂载时通过 `subscribeSSE` 连接后端的 `/events/stream` 实时事件管道；
   * 当后端任务状态发生变化（如任务创建、阶段流转、任务超时或完成）时，自动触发各 ViewModel 的局部静默刷新，无需手动轮询。

---

## 5. 开发与构建命令

```bash
# 进入前端工作目录
cd dashboard

# 依赖安装
pnpm install

# 本地热更新开发 (需在 AstrBot 运行环境下访问页面或直接调试)
pnpm dev

# 生产环境编译 (自动打包为单 Bundle 输出至 ../pages/daily-analysis/)
pnpm build
```
