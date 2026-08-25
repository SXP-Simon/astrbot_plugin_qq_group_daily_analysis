# WebUI 架构与设计规范 (WebUI Architecture Specification)

本文档阐述 `astrbot_plugin_qq_group_daily_analysis` 插件内嵌 WebUI 控制台的架构设计与实现准则。

---

## 1. 架构理念 (Core Philosophy)

控制台前端全面拥抱 **Feature-Sliced Design (FSD)**、**Atomic Design (原子设计)** 与 **MVVM (Model-View-ViewModel)** 架构，追求高内聚、低耦合、强类型与极致性能。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          App (Root & Global Context)                        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Pages (Views & ViewModels)                          │
│   ┌────────────────┬────────────────┬─────────────────┬─────────────────┐   │
│   │  OverviewPage  │   TracesPage   │ ContextInsight  │   ReportsPage   │   │
│   │ (useOverviewVM)│ (useTracesVM)  │ (useInsightVM)  │ (useReportsVM)  │   │
│   └────────────────┴────────────────┴─────────────────┴─────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Widgets (Organisms)                             │
│   HeaderBar | ActiveTaskBoard | TraceTable | TraceDrawer | ContextFunnel    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Features (Action Slices)                            │
│           trigger-task         filter-traces          cancel-task           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Entities (Domain Models)                          │
│              task        trace        group        metric        report     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Shared (Atoms, API Bridge, Lib)                       │
│           MetricCard | StatusTag | SectionHeader | bridge | formatters      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 分层规范与职责 (Layer Responsibilities)

1. **`shared/`（基础共享层）**：
   * 包含与业务解耦的基础组件（Atoms）、全局通信桥梁（`bridge.ts`）与通用工具函数库（`formatters.ts`、`useTheme.ts`）。
2. **`entities/`（领域实体层）**：
   * 按业务领域划分切片（Task, Trace, Group, Metric, Report）。
   * 每个实体切片包含 `model/types.ts`（领域类型）和 `api/`（轻量数据客户端），以及专属的原子 UI（如 `TaskStageBadge.tsx`、`SpanTimeline.tsx`）。
3. **`features/`（功能切片层）**：
   * 承载完整的用户交互行为（如手动触发分析模态框、多字段复合筛选条、二次确认中止任务按钮）。
4. **`widgets/`（复合微件层）**：
   * 将多个实体和功能有机组合为自包含的业务组件（如集成秒级计时器的 `ActiveTaskBoard`、支持服务端排序与分页的 `TraceTable`、集成瀑布流与调用栈的 `TraceDrawer`）。
5. **`pages/`（页面与视图模型层）**：
   * 落地 **MVVM 模式**：
     * **ViewModel** 负责状态响应、远程数据拉取、防抖、排序、衍生计算。
     * **View** 仅作为纯 JSX 声明式接收 ViewModel 输出。
6. **`app/`（应用根层）**：
   * 负责 Ant Design 全局主题算法（明亮/暗黑自适应）、Tab 路由布局、以及 SSE 全局事件流中继分发。

---

## 3. TypeScript 严格类型准则 (Type Safety Rules)

1. **严禁无理由使用 `any` 类型**：
   * 所有跨 Iframe 通信、网络请求响应、第三方组件回调均使用强类型声明。
   * 对于不确定结构的数据（如扩展字典、第三方透传 Payload），使用 `unknown` 并配合类型收敛。
2. **接口命名规范**：
   * 实体模型接口统一命名为 `*Record` / `*Item` / `*Summary`。
   * API 响应统一包装为泛型 `ApiResponse<T>`。
