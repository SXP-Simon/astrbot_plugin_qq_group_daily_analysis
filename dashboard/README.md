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

## 5. 本地开发与调试体验 (Developer Experience)

本项目支持两种本地开发调试模式，提供极速热更新（HMR）：

### 5.1 独立开发模式 (Standalone Mock Mode - 推荐)
无需启动 AstrBot 后端，前端直接拥有全套模拟数据与实时 SSE 进度流：
```bash
cd dashboard
pnpm dev
```
* 打开 `http://localhost:5175`，页面将自动激活 Mock 适配器并加载全套大盘、链路、任务与日志；
* 页面右下角提供 **开发工具箱 (DevToolbar)**，可一键切换亮暗主题、切换 Proxy/Mock 模式或注入模拟 SSE 任务流。

### 5.2 代理直连模式 (Proxy Mode)
若 AstrBot 后端正在运行（`localhost:6185`），前端开发服务器通过反向代理直接对接真实后端与 SQLite：
* 在页面右下角工具箱中切换至 **Proxy 直连后端 (:6185)**，或在 URL 中添加 `?devMode=proxy`；
* 享受 Vite 秒级热更新，无需重新打包或进入 AstrBot 网页手动点击。

### 5.3 生产构建
```bash
# 生产环境编译 (自动打包为单 Bundle 输出至 ../pages/daily-analysis/)
pnpm build
```

---

## 6. 前端自动化测试与契约体系 (Automated Tests & Contracts)

### 6.1 OpenAPI 契约与类型自动同步
前端 `src/entities/*/model/types.ts` 中的所有实体类型直接由 `src/shared/api/generated/schema.d.ts` 派生，实现 100% 强类型保护：
```bash
# 1. 导出后端最新 OpenAPI 3.1 规范
python ../scripts/export_openapi.py

# 2. 自动生成前端强类型 schema.d.ts
pnpm generate:types
```

### 6.2 自动化测试矩阵 (Vitest + React Testing Library)
项目内置 8 个测试套件，全面覆盖通信网桥、Mock 路由分发、格式化工具库、原子组件、业务小部件以及全景页面冒烟测试：
```bash
pnpm test          # 运行全套自动化测试
pnpm test:watch    # 开启 TDD 监听模式
```

### 6.3 MSW (Mock Service Worker) 零成本复用
在 `src/mocks/mswHandlers.ts` 中提供了标准 MSW Handler 适配器 `createMswHandlerDefinitions()`，可将内部 Mock Handlers 0 成本接入 MSW 的 `http.get` / `http.post`，方便后续编写 Playwright 端到端测试。

---

## 7. 质量门禁与发布流程 (Quality Gates & Release)

### 7.1 本地 Git 提交门禁 (Lefthook)
在每次 `git commit` 时，Lefthook 将自动触发全套前端门禁，任何失败均会阻止提交：
1. **类型检查**：`pnpm typecheck`（严格 0 报错）
2. **代码规范**：`pnpm lint`（ESLint 严格检查）
3. **自动化测试**：`pnpm test`（28 项单测与冒烟测试 100% 通过）
4. **生产构建**：`pnpm build`（打包为单 Bundle 同步生成至 `../pages/daily-analysis/`）
5. **提交信息规范**：`verify-commit.js`（原子化 Scope + 中文三点论门禁）

### 7.2 新版本发布流程
与原本发布流程保持完全一致且更加自动化：
* 日常开发提交时，Lefthook 门禁会自动执行 `pnpm build` 将最新的控制台静态页面更新至 `pages/daily-analysis/assets/`；
* 插件发布新版本（例如修改 `metadata.yaml` 与版本号）时，直接提交代码并打 Tag 即可，无需额外手动构建打包前端。

