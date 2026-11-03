# WebUI 架构与设计规范 (WebUI Architecture Specification)

本文档阐述 `astrbot_plugin_qq_group_daily_analysis` 插件内嵌 WebUI 控制台（`dashboard/`）的整体架构设计、分层约束、组件化解耦准则与实现标准。

---

## 1. 架构理念 (Core Philosophy)

控制台前端全面拥抱 **Feature-Sliced Design (FSD)**、**Atomic Design (原子设计)** 与 **MVVM (Model-View-ViewModel)** 架构，追求高内聚、低耦合、强类型、极致可维护性与高信息密度体验。

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              App (Root & Global Context)                               │
│                   App.tsx | 主题上下文 (Theme/SSE) | 导航与布局骨架                       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              Pages (Views & ViewModels)                                │
│   ┌───────────────┬────────────────┬─────────────────┬───────────────┬─────────────┐   │
│   │ OverviewPage  │ ContextInsight │   ConfigPage    │   LogsPage    │ ReportsPage │   │
│   │(useOverviewVM)│ (useInsightVM) │ (useConfigVM)   │ (useLogsVM)   │(useReportsVM│   │
│   └───────────────┴────────────────┴─────────────────┴───────────────┴─────────────┘   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Widgets (Organisms)                                    │
│   HeaderBar | ActiveTaskBoard | TraceTable | TraceDrawer | AnalysisTimelinePicker      │
│       OverviewTrendCharts | FieldRenderer | TemplateListRenderer | ReportPreviewModal   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             Features (Action Slices)                                   │
│           trigger-task         filter-traces          cancel-task         filter-logs  │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               Entities (Domain Models)                                 │
│          task        trace        group        metric        report       config       │
│      (models, api clients, and atomic UI slices like SpanHeader, LlmAttemptsTable)     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                           Shared (Atoms, API Bridge, Lib)                              │
│              MetricCard | StatusTag | bridge.ts | formatters.ts | useTheme.ts          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 分层规范与职责 (Layer Responsibilities)

### 2.1 `shared/`（基础共享层）
* 包含与业务完全解耦的通用基建：
  * **原子 UI (Atoms)**：`StatusTag.tsx`、`MetricCard.tsx` 等通用展示组件。
  * **通信桥梁 (Bridge)**：`bridge.ts` 负责与 AstrBot 宿主面板安全通信与事件监听。
  * **工具库 (Lib)**：`formatters.ts`（时间/Token/数字格式化）、`useTheme.ts`（明暗模式响应）。

### 2.2 `entities/`（领域实体层）
* 按领域划分独立切片（`task`, `trace`, `group`, `metric`, `report`, `config`, `log`）。
* 每个实体切片包含三个标准子层：
  1. `model/types.ts`：纯 TypeScript 领域模型与枚举定义。
  2. `api/`：强类型的轻量数据获取客户端。
  3. `ui/`：该实体专属的**原子与分子组件 (Atoms & Molecules)**，并通过 `ui/index.ts` 统一导出。

#### 实体 UI 解耦与防膨胀约束（Atomic UI Guidelines）
* **严禁单文件巨石组件**：单个 UI 组件文件原则上控制在 200 行以内，严禁将所有子逻辑内联堆砌在单一主组件中。
* **以 `entities/trace/ui` 为标准范例**：
  * `SpanTimeline.tsx`（调度编排器，仅负责时间线流与步进动画，约 150 行）。
  * `SpanHeader.tsx`（阶段标题、SLA 耗时基线警告、微型进度条与折叠手柄）。
  * `SpanAlerts.tsx`（阶段执行异常、子任务错误列表与无产出提示横幅）。
  * `LlmAttemptsTable.tsx`（大模型调用与降级重试表格，负责 Provider 去重与错误展示）。
  * `RenderAttemptsTable.tsx`（图片渲染降级策略表格）。
  * `StageMetricsBadges.tsx`（各阶段专属指标药丸徽章）。
  * `PromptsInspector.tsx`（结构化 Prompt 与产物检视卡片）。
  * `SpanPayloadViewer.tsx`（底层数据快照与诊断信息）。

### 2.3 `features/`（功能切片层）
* 承载由用户主动发起的独立交互行为或业务操作：
  * `trigger-task/`：手动触发群分析与漫画生成对话框。
  * `filter-traces/`：Trace 列表的多维度复合筛选栏。
  * `cancel-task/`：二次确认中止运行中任务。
  * `resume-task/`：断点续跑与失败阶段重试。
  * `filter-logs/`：日志级别与关键词流式过滤。

### 2.4 `widgets/`（复合微件层）
* 将多个实体和功能有机组合为自包含的业务组件（Organisms）：
  * `ActiveTaskBoard.tsx`：活跃任务看板与实时步进计时器。
  * `TraceDrawer.tsx`：任务执行详情全屏/半屏抽屉（包含 Summary、SpanTimeline、TraceLogViewer）。
  * `AnalysisTimelinePicker.tsx`：全景时间线选择器与状态节点可视化。
  * `OverviewTrendCharts.tsx`：时序指标图表与 Token 消耗趋势。
  * `FieldRenderer.tsx` & `TemplateListRenderer.tsx`：动态配置表单渲染器（支持 Provider/Persona 自动点选与模板列表）。

### 2.5 `pages/`（页面与视图模型层）
* 全面实施 **MVVM 模式**：
  * **ViewModel (`use*ViewModel.ts`)**：负责状态机管理、远程接口轮询、防抖搜索、数据衍生计算与错误处理。
  * **View (`*Page.tsx`)**：纯 JSX 声明式视图，仅接收 ViewModel 输出的属性与回调函数，严禁在 View 内部直接编写异步网络请求或复杂状态衍生逻辑。

### 2.6 `app/`（应用根层）
* 负责 Ant Design 5 动态主题算法配置、明暗色彩自适应注入、Tab 路由布局切换与全局警告提示容器。

---

## 3. 任务与链路生命周期状态模型 (Status & Lifecycle Contract)

前端对任务与 Span 的状态判定严格遵循以下契约，禁止模糊掩盖：

| 状态标识 | 语义 | 视觉规范 | 业务判定标准 |
| :--- | :--- | :--- | :--- |
| `running` | 运行中 | 蓝色胶囊 / 旋转指示器 | 任务/阶段正在执行中，秒级步进更新耗时。 |
| `succeeded` | 完全成功 | 绿色胶囊 / 勾选图标 | 所有已开启的子任务均成功产出，且报告正常分发。 |
| `warning` / `partial_success` | 部分成功 / 警告 | 琥珀橙色胶囊 / 感叹号 | 至少 1 个子任务成功并允许发送报告，但存在部分子任务失败或重试耗尽。 |
| `failed` / `error` | 执行失败 / 中断 | 红色胶囊 / 叉号图标 | 开启的 LLM 模块全部失败导致任务熔断中断，或发生未捕获致命异常。 |
| `aborted` | 已中止 | 灰色胶囊 | 用户手动点击中止或系统重载取消。 |

---

## 4. UI 视觉规范与排版准则 (Data-Dense Visual Standards)

1. **去衬线体与现代等宽栈**：
   * 所有代码、Prompt、Token 数量、TraceId、Provider 标识一律采用现代无衬线等宽字体栈：
     `'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`
   * 严禁使用系统默认衬线字体（如 Courier New）。
2. **结构化卡片与清晰边界 (Crisp Hierarchy)**：
   * 任何子模块（如提示词检视器、重试表格、产物明细）必须具备明确的容器边框（`border-[#e2e8f0]` / `border-[#30363d]`）与浅色顶栏（`bg-[#f8fafc]` / `bg-[#21262d]`）。
   * 严禁纯白无边界扁平堆叠，确保在桌面端和深色模式下层次分明。
3. **信息去重原则**：
   * 当 Provider 名称中已包含 Model 标识时，自动去重，避免出现 `deepseek/xxx (xxx)` 的重复冗余信息。

---

## 5. TypeScript 严格类型与质量基线 (Quality Rules)

1. **严禁使用 `any` 类型**：
   * 所有跨 iframe 通信、网络请求响应、第三方组件回调均使用强类型声明。
   * 对于不确定结构的数据，使用 `unknown` 并配合类型保护（Type Guard）或类型收敛。
2. **接口命名规范**：
   * 实体模型接口统一命名为 `*Record` / `*Item` / `*Summary` / `*Detail`。
   * API 响应统一包装为泛型 `ApiResponse<T>`。
3. **自动化准入基线**：
   * 每次提交前必须确保 `pnpm lint`（ESLint **0 error / 0 warning**）与 `pnpm run build`（TypeScript 编译与 Vite 打包）全部通过。

## 6. 数据管理文件边界

`plugin-data/partitions` 返回插件专属分区的实际路径、文件数、字节数和操作能力。文件列表支持分页搜索；内容接口仅按分区内相对路径读取，单文件上限 32 MiB。创建不覆盖同名文件；替换、重命名和删除必须携带读取时的 SHA256 修订号，冲突返回 409。

模板源码可创建和编辑，字体及固定清单内的素材支持上传替换；报告、备份和派生缓存只支持查看、下载及单项删除。字体仍从插件 data/typst/fonts 加载，资源优先使用 data/typst/resources。数据库、内部状态和编译任务目录不提供直接写入。宿主全局 io_temp_img_* 没有插件归属，不能通过本插件清理。头像缓存通过 DiskCache API 清理，不删除仍在使用的数据库文件。

数据管理保留“存储空间概览”入口，将原先六项“清空”操作改为按分区进入文件列表。可搜索相对路径，预览图片及隔离 HTML，下载原件，逐项删除，维护模板源码及上传字体/素材。字体与素材分区的“按模板下载”复用配置中心组件；自定义模板分区可直接安装完整模板包。覆盖、重命名和删除在详情中进行，必须先读取原文件。


### 业务存档与多选管理

“数据管理 → 分析存档与头像”展示当前插件作用域内的分析历史 KV 及平台头像缓存键。业务 KV 位于宿主共享存储，不重复计入插件文件目录占用。增量批次和快照保留原有结构化详情，另提供“管理”入口以导出完整 JSON、修订或删除。历史和批次允许导入为新记录；阶段快照由分析任务创建，修订只更新产物，不能改变身份、创建时间或有效期。头像缓存仅支持查询、预览、导出及删除后按需重取。

`plugin-data/records`、`records/detail`、`records/mutate` 使用对应仓储和插件 KV 接口，不直接改写 SQLite 文件。业务修订通过 JSON 内容版本拒绝覆盖，且与 daily / incremental / final 群任务互斥。删除最新历史版本会修复每日索引；导入缺失版本会补齐每日索引。单条导入上限 4 MiB。

文件列表的 `extensions` 参数按扩展名先筛选再分页，支持逗号分隔的 JPG / PNG 组合。`files/delete-many` 只接受显式选择的相对路径和列表修订号，每批最多 200 个，逐项返回成功与失败，不使用模糊路径或递归清空。管理页切换筛选条件会清空已有选择，避免误删隐藏项；可独立筛选 HTML、JPG、PNG、Typst（.typ）、SVG、JSON 和字体类型。业务存档、头像、增量和快照列表也提供多选删除，并保留失败项供检查。
