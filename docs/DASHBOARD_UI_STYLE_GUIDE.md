STYLEKIT_STYLE_REFERENCE
style_name: 数据密集与响应式控制台 (Data Dense & Responsive Utility)
style_slug: data-dense-utility

# Hard Prompt

## 什么时候用
当为群日常分析插件（`astrbot_plugin_qq_group_daily_analysis`）开发 WebUI 控制台（`dashboard/`）及各类监控、链路追踪（Trace Explorer）、上下文透视（Context Funnel）、Token 审计页面时使用。
它是高信息密度管理后台、日志与性能调试界面的最高优先级标准。

## 怎么用
- 在编写 React + Ant Design 5 + Tailwind CSS 代码时严格作为第一准则。
- 遇到布局、组件尺寸、字体选择冲突时，以本规范的“绝对禁止”与“必须遵守”为最高优先级。
- 输出代码前进行严格自检，确认无风格漂移。

---

# Data Dense & Responsive Utility Design System

> 面向群分析与 Agent 链路监控的高密度后台控制台设计系统。在桌面端以极致的信息密度、紧凑表格与毫秒级状态响应优先；在移动端自适应为易点击的卡片堆叠与触控流。

---

## 1. 核心理念与风格定位

### 1.1 风格权衡分析：为什么以“数据密集（Data Dense）”为主？
* **管理面板的核心目标是“效率与排障”**：管理员打开控制台是为了快速定位“哪个群卡住了”、“这趟分析耗时多少毫秒”、“Token 花在哪里”、“Prompt 压缩率如何”。
* **大面积留白与大圆角的危害**：在日志/Trace 排查场景中，过大的 `p-6` 内边距与大字号会导致一屏只能展示 3~5 条记录，排查效率极低。
* **双模融合（桌面数据密集 + 移动端柔和工具响应）**：
  * **桌面端（$\ge 768\text{px}$）**：严格执行 Data Dense，行高紧凑（`py-1.5` / `py-2`），等宽字体展示 ID/时间/数字，全操作行内可见。
  * **移动端（$< 768\text{px}$）**：自动切换为垂直堆叠的紧凑卡片流，触控区域放大至拇指友好尺寸（$\ge 36\text{px}$），操作栏固定于底部或卡片底部。

---

## 2. Token 字典（精确映射与设计规范）

### 2.1 边框与圆角
```
宽度: border (1px 细线)
边框色: border-[#e2e8f0] (暗黑模式: border-[#30363d] / border-slate-700)
圆角: rounded (4px) 至 rounded-md (6px)
绝对禁止: rounded-xl, rounded-2xl, rounded-3xl (移动端除外)
```

### 2.2 阴影与微质感
```
基础: shadow-none 或 shadow-sm
悬停: hover:shadow-sm
聚焦: ring-1 ring-[#3b82f6]
绝对禁止: shadow-lg, shadow-xl, shadow-2xl, 装饰性大光晕
```

### 2.3 交互与动效
```
过渡: transition-colors duration-150
悬停高亮: hover:bg-[#f8fafc] (暗黑模式: hover:bg-[#161b22])
点击反馈: active:scale-[0.98]
绝对禁止: 弹性果冻动画 (bounce/elastic)、大于 250ms 的拖沓过渡
```

### 2.4 字体与排版
```
主字体: font-sans (系统原生无衬线字体)
数据/ID/代码/耗时: font-mono (monospace, 如 ui-monospace, SFMono-Regular, Menlo)
字重: 标题 font-semibold, 表头 font-medium, 正文 font-normal
```

### 2.5 字号阶梯 (严格控高)
```
页面主标题: text-base md:text-lg font-semibold
卡片标题: text-xs md:text-sm font-semibold
表头文字: text-[10px] md:text-xs uppercase tracking-wider text-[#64748b]
正文/表格行: text-xs (12px) md:text-sm (14px)
辅助信息/元数据: text-[10px] (10px) md:text-xs (12px)
```

### 2.6 间距体系 (基于 4px 紧凑递增)
```
微间距: gap-1 (4px), p-1
小间距: gap-2 (8px), p-2, px-2.5 py-1.5
标准卡片: px-3 py-2.5 (12px * 10px)
区块间距: space-y-3 (12px)
容器边距: px-3 py-3 md:px-4 md:py-4
绝对禁止: p-6, p-8, py-10 以上的大间距
```

### 2.7 颜色语义角色 (Color Roles)

| 语义 | 亮色模式 (Light) | 暗黑模式 (Dark) | 典型应用场景 |
| :--- | :--- | :--- | :--- |
| **主背景 (Canvas)** | `bg-[#f8fafc]` (浅灰蓝) | `bg-[#0d1117]` (深黑灰) | 页面整体底色 |
| **容器背景 (Surface)** | `bg-white` | `bg-[#161b22]` | 表格卡片、抽屉面板 |
| **边框 (Border)** | `border-[#e2e8f0]` | `border-[#30363d]` | 分隔线、输入框边框 |
| **正文主色 (Primary Text)**| `text-[#1e293b]` | `text-[#c9d1d9]` | 任务名称、主要指标 |
| **正文辅色 (Muted Text)**  | `text-[#64748b]` | `text-[#8b949e]` | 标签、时间戳、表头 |
| **品牌主色 (Primary Action)**| `bg-[#2563eb]` / `bg-[#2d5b63]` | `bg-[#388bfd]` | 主按钮、选中态 |
| **成功态 (Success)**       | `bg-emerald-50 text-emerald-700 border-emerald-200` | `bg-emerald-950/40 text-emerald-400 border-emerald-800` | 状态 `succeeded`, 耗时正常 |
| **运行态 (Running/Info)**   | `bg-blue-50 text-blue-700 border-blue-200` | `bg-blue-950/40 text-blue-400 border-blue-800` | 状态 `running`, 增量同步中 |
| **警告态 (Warning/Pending)**| `bg-amber-50 text-amber-700 border-amber-200` | `bg-amber-950/40 text-amber-400 border-amber-800` | 状态 `queued`, 接近限额 |
| **错误态 (Error/Failed)**   | `bg-rose-50 text-rose-700 border-rose-200` | `bg-rose-950/40 text-rose-400 border-rose-800` | 状态 `failed`, 接口 429/500 |

---

## 3. [FORBIDDEN] 绝对禁止项

以下模式在代码中**严禁出现**，一旦出现视为严重违规：

1. ❌ **严禁大面积留白与超大内边距**：禁止在数据容器使用 `p-6`、`p-8`、`py-12`。
2. ❌ **严禁使用大圆角**：禁止使用 `rounded-xl`、`rounded-2xl`（除移动端全屏抽屉顶角外）。
3. ❌ **严禁使用装饰性渐变背景**：禁止 `bg-gradient-to-r` 作为主界面铺色（增加视觉杂音并分散注意力）。
4. ❌ **严禁在数据表格中使用大于 `text-sm` 的字体**：数据单元格字号必须保持在 `text-xs` 或 `text-sm`。
5. ❌ **严禁隐藏重要高频操作**：如【重试】、【查看链路】、【中止】等操作必须直接在行内或抽屉顶部呈现，不得二级折叠到无谓的“更多...”下拉菜单中。
6. ❌ **严禁低对比度配色**：所有文字对比度必须符合 WCAG AA 标准（正文 $\ge 4.5:1$）。

---

## 4. [REQUIRED] 必须包含的设计规范

1. ✅ **等宽字体（Monospace）绑定**：所有 `trace_id`、`group_id`、Token 数值、耗时（ms/s）、时间戳、JSON 字段必须带有 `font-mono`。
2. ✅ **紧凑状态胶囊（Status Pills）**：状态标签统一采用 `px-1.5 py-0.5 text-[10px] md:text-xs font-mono rounded border`。
3. ✅ **紧凑操作按钮**：小尺寸按钮规范 `px-2.5 py-1 text-xs rounded font-medium transition-colors`。
4. ✅ **表格紧凑行高**：Table 组件的单元格 padding 保持 `py-1.5 px-2` 至 `py-2 px-3`，支持一屏呈现至少 15 条记录。
5. ✅ **响应式断点平滑回退**：
   * `桌面端 (md:)`：展示多列完整数据表格（含 TraceID、群号、阶段、耗时、Token、操作）。
   * `移动端 (< md)`：隐藏次要列，转换为紧凑型卡片（Card List），操作按钮置于卡片底部。

---

## 5. [COMPARE] 错误 vs 正确对比示例

### 5.1 状态标签 (Status Tag)

* ❌ **错误示例**（大字号、过大内边距、纯装饰）：
  ```html
  <span class="px-4 py-2 text-base rounded-full bg-blue-500 text-white font-bold shadow-lg">
    RUNNING
  </span>
  ```
* ✅ **正确示例**（紧凑、等宽、颜色编码、微边框）：
  ```html
  <span class="inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono font-medium rounded border bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800">
    <span class="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse mr-1"></span>
    RUNNING
  </span>
  ```

### 5.2 统计指标卡片 (KPI Card)

* ❌ **错误示例**（巨大内边距、大阴影、空间浪费）：
  ```html
  <div class="p-8 bg-white rounded-2xl shadow-xl">
    <h2 class="text-2xl text-gray-500">今日花费</h2>
    <p class="text-5xl font-extrabold text-blue-600">124,500</p>
  </div>
  ```
* ✅ **正确示例**（紧凑、数据优先、辅以微标签与等宽数字）：
  ```html
  <div class="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded px-3 py-2.5 flex flex-col justify-between">
    <div class="flex items-center justify-between text-xs text-[#64748b] dark:text-[#8b949e]">
      <span class="font-medium">今日 Token 消耗</span>
      <span class="text-[10px] px-1 bg-[#f8fafc] dark:bg-[#21262d] rounded border border-[#e2e8f0] dark:border-[#30363d]">4 个群</span>
    </div>
    <div class="mt-1.5 flex items-baseline gap-1.5">
      <span class="font-mono font-semibold text-lg md:text-xl text-[#1e293b] dark:text-[#c9d1d9]">124,500</span>
      <span class="text-[10px] text-[#64748b] dark:text-[#8b949e]">Tokens (≈$0.18)</span>
    </div>
  </div>
  ```

---

## 6. [TEMPLATES] 常用界面骨架组件模板

### 6.1 顶部紧凑状态栏 (Header Toolbar)
```tsx
<header className="bg-white dark:bg-[#161b22] border-b border-[#e2e8f0] dark:border-[#30363d] px-3 py-2 flex items-center justify-between gap-2">
  <div className="flex items-center gap-2">
    <span className="font-semibold text-xs md:text-sm text-[#1e293b] dark:text-[#c9d1d9] tracking-tight">
      群分析控制台
    </span>
    <span className="inline-flex items-center px-1.5 py-0.2 text-[10px] font-mono rounded bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800">
      ● 正常
    </span>
  </div>
  <div className="flex items-center gap-1.5">
    <button className="px-2 py-1 text-xs rounded border border-[#e2e8f0] dark:border-[#30363d] bg-white dark:bg-[#21262d] text-[#1e293b] dark:text-[#c9d1d9] hover:bg-[#f8fafc] dark:hover:bg-[#30363d] transition-colors">
      刷新
    </button>
    <button className="px-2.5 py-1 text-xs rounded bg-[#2563eb] text-white hover:bg-blue-700 transition-colors font-medium">
      + 触发分析
    </button>
  </div>
</header>
```

### 6.2 紧凑数据表格骨架 (Data-Dense Table)
```tsx
<div className="bg-white dark:bg-[#161b22] border border-[#e2e8f0] dark:border-[#30363d] rounded overflow-hidden">
  <div className="overflow-x-auto">
    <table className="w-full text-left border-collapse">
      <thead>
        <tr className="border-b border-[#e2e8f0] dark:border-[#30363d] bg-[#f8fafc] dark:bg-[#161b22]/60 text-[10px] md:text-xs uppercase tracking-wider text-[#64748b] dark:text-[#8b949e]">
          <th className="py-2 px-3 font-medium">Trace ID</th>
          <th className="py-2 px-3 font-medium">群组</th>
          <th className="py-2 px-3 font-medium">状态</th>
          <th className="py-2 px-3 font-medium">耗时</th>
          <th className="py-2 px-3 font-medium">Tokens</th>
          <th className="py-2 px-3 font-medium text-right">操作</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-[#e2e8f0] dark:divide-[#30363d] text-xs">
        {/* 单行模板 */}
        <tr className="hover:bg-[#f8fafc] dark:hover:bg-[#21262d] transition-colors">
          <td className="py-1.5 px-3 font-mono text-[#2563eb] dark:text-[#58a6ff]">manual_98231_2105</td>
          <td className="py-1.5 px-3 font-mono text-[#1e293b] dark:text-[#c9d1d9]">系统交流群 (82103)</td>
          <td className="py-1.5 px-3">
            <span className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800">
              SUCCEEDED
            </span>
          </td>
          <td className="py-1.5 px-3 font-mono text-[#64748b] dark:text-[#8b949e]">8.42s</td>
          <td className="py-1.5 px-3 font-mono text-[#64748b] dark:text-[#8b949e]">14,280</td>
          <td className="py-1.5 px-3 text-right">
            <button className="px-2 py-0.5 text-xs text-[#2563eb] dark:text-[#58a6ff] hover:underline font-medium">
              详情
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
```

### 6.3 链路甘特瀑布流抽屉项 (Waterfall Span Row)
```tsx
<div className="py-1.5 px-2 border-b border-[#e2e8f0] dark:border-[#30363d] flex items-center justify-between text-xs hover:bg-[#f8fafc] dark:hover:bg-[#161b22]">
  <div className="flex items-center gap-2 w-1/3 truncate">
    <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
    <span className="font-mono font-medium text-[#1e293b] dark:text-[#c9d1d9]">LLM_TOPICS</span>
  </div>
  <div className="flex-1 px-3">
    <div className="w-full bg-[#e2e8f0] dark:bg-[#30363d] h-2 rounded overflow-hidden">
      <div className="bg-[#2563eb] h-full rounded" style={{ width: '42%' }}></div>
    </div>
  </div>
  <div className="w-20 text-right font-mono text-[#64748b] dark:text-[#8b949e] text-[11px]">
    3,420ms
  </div>
</div>
```

---

## 7. [RESPONSIVE] 响应式适配策略

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 桌面端 (>= 768px): 宽幅数据密集表格 (Dense Table)                       │
│ ┌────────────┬─────────────┬───────────┬──────────┬──────────┬────────┐ │
│ │ Trace ID   │ 群组        │ 状态      │ 耗时     │ Tokens   │ 操作   │ │
│ └────────────┴─────────────┴───────────┴──────────┴──────────┴────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│ 移动端 (< 768px): 紧凑堆叠卡片流 (Stacked Card List)                   │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ manual_98231_2105  [SUCCEEDED]                              8.42s   │ │
│ │ 系统交流群 (82103)                                 14,280 Tokens   │ │
│ │ [查看链路详情]                                        [一键重试]    │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

* **移动端规则**：
  * 在移动端（屏幕宽度 $< 768\text{px}$）自动将表格切换为 `Card` 列表，避免出现水平无休止滚动。
  * 卡片内主次分明：左上 TraceID、右上状态 Badge、次行群名与耗时、底部行内操作按钮。
  * 抽屉（Drawer）在移动端占满屏宽（`width: 100%`），提供顶栏明显的【关闭/返回】按钮。

---

## 8. [CHECKLIST] 交付前自检清单

**在提交前端代码前，必须逐项核对：**

- [ ] **信息密度**：表格单行内边距未超过 `py-2`，没有冗余的大面积留白（无 `p-6`、`p-8`）。
- [ ] **圆角控制**：卡片与表格均使用 `rounded` (4px) 或 `rounded-md` (6px)，没有使用 `rounded-xl`。
- [ ] **字体规范**：所有 ID、群号、时间戳、Token 数、耗时均带有 `font-mono`。
- [ ] **字号控制**：表格内文本保持在 `text-xs` 或 `text-sm`，表头使用 `text-[10px]` 或 `text-xs`。
- [ ] **颜色与状态**：状态标签（Success/Running/Pending/Failed）采用标准的浅底深字加细微边框体系。
- [ ] **暗黑模式**：所有组件均适配了 `dark:` 属性，在深色背景下文本对比度达标。
- [ ] **响应式验证**：在移动端视口下无横向溢出破屏，操作按钮点击区域充足。
