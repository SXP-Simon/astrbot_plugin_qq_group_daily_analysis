# 贡献指南 (Contributing Guide)

感谢你对 **群聊日常分析插件 (`astrbot_plugin_qq_group_daily_analysis`)** 的关注与支持！我们欢迎各种形式的贡献，包括但不限于：提交 Bug 报告、提出新功能建议、改进文档、贡献精美报告模板以及提交代码修复与功能特性。

为了保证代码库的整洁性、可维护性与高工程质量，请在提交代码前仔细阅读本指南。

---

## 目录

1. [开发环境搭建 (Getting Started)](#1-开发环境搭建-getting-started)
2. [代码规范与架构准则 (Code & Architecture Standards)](#2-代码规范与架构准则-code--architecture-standards)
   - [2.1 Python 后端开发规范](#21-python-后端开发规范)
   - [2.2 WebUI 前端开发规范 (FSD + Atomic + MVVM)](#22-webui-前端开发规范-fsd--atomic--mvvm)
3. [报告模板贡献指南 (Templates Contribution)](#3-报告模板贡献指南-templates-contribution)
   - [3.1 模板目录结构](#31-模板目录结构)
   - [3.2 模板变量对照表](#32-模板变量对照表)
   - [3.3 离线调试工具使用](#33-离线调试工具使用)
4. [Commit 提交信息规范 (Conventional Commits)](#4-commit-提交信息规范-conventional-commits)
5. [Pull Request 提交流程](#5-pull-request-提交流程)

---

## 1. 开发环境搭建 (Getting Started)

本项目推荐使用 [uv](https://docs.astral.sh/uv/) 管理 Python 环境，使用 [pnpm](https://pnpm.io/) 管理前端工程。

### 1.1 Python 后端环境
```bash
# 进入插件目录
cd astrbot_plugin_qq_group_daily_analysis

# 安装开发依赖与测试工具
uv venv
uv pip install -e ".[dev]" pytest pytest-asyncio pytest-cov ruff pre-commit

# 安装 git pre-commit 钩子
pre-commit install
```

### 1.2 WebUI 控制台前端环境
```bash
# 进入前端子工程
cd dashboard

# 安装前端依赖
pnpm install

# 启动本地热更新开发模式
pnpm dev
```

---

## 2. 代码规范与架构准则 (Code & Architecture Standards)

### 2.1 Python 后端开发规范

1. **KISS 原则与内联优先 (Inline-First Rule)**：
   * 优先在主函数内直接实现清晰的线性逻辑，除非满足高复用（$\ge 3$ 处重复）或极端复杂（$>50$ 行破坏主流程），否则**严禁过度抽取无意义的辅助函数**。
2. **强制 Google 风格 Docstring**：
   * 所有复杂函数/类必须提供标准 Google 格式文档注释（包含 `Args:`, `Returns:`, `Raises:`）。
3. **路径与平台兼容性**：
   * 必须使用 `pathlib.Path` 处理路径，禁止硬编码 Windows `\` 反斜杠或绝对路径；
   * 确保兼容 Linux、macOS、Windows 及 Arm64/x86 架构。
4. **日志与注释语言**：
   * 代码内部所有注释、Log 输出与异常提示必须使用清晰的 **中文**。
5. **静态类型检查与类型体操准则 (Static Type & Type Gymnastics Standards)**：
   * 本项目统一使用 **Pyright / Pylance** 进行静态类型分析与语法校验，规则配置文件为项目根目录的 [`pyrightconfig.json`](pyrightconfig.json)；
   * **类型检查模式与环境对齐**：采用严格生产标准的 `"typeCheckingMode": "standard"`，统一设置 `"pythonVersion": "3.12"`，严格对齐 AstrBot 依赖环境；
   * **严格模块导入与重写门禁**：开启 `"reportMissingImports": "error"`, `"reportIncompatibleMethodOverride": "error"`, `"reportFunctionMemberAccess": "error"`, `"reportUntypedFunctionDecorator": "error"`, `"reportUntypedBaseClass": "error"`；
   * **严禁滥用 `Any` (Zero `Any` Abuse Policy)**：
     - **接口协议化 (`Protocol`)**：跨模块、跨平台的动态处理器一律使用 `typing.Protocol` 与 `@runtime_checkable` 声明契约方法（如 `TemplatePreviewHandler`），严禁使用 `list[Any]`；
     - **结构化字典 (`TypedDict`)**：包含固定键值的数据结构（如统计指标、活跃度、请求荷载）一律使用 `TypedDict` 进行强类型建模，替代 `dict[str, Any]`；
     - **可选依赖与动态调度**：Telegram、Discord 等按需加载的可选依赖，统一使用 `if TYPE_CHECKING:` 导入静态类型；动态调用必须使用 `inspect.isawaitable` 或安全收窄守卫；
   * 提交前必须在插件根目录下运行 Pyright 检查，确保 **0 错误、0 警告**：
     ```bash
     npx pyright
     ```
6. **一键格式化、自动修复 Lint 与单元测试**：
   * 强烈推荐使用一键格式化与自动修复指令（自动消除未使用的 import、调整 import 顺序及代码风格），提交前保证静态类型检查与测试全部通过：
     ```bash
     uv run ruff format . ; uv run ruff check . --fix
     npx pyright
     uv run pytest tests/
     ```

---

### 2.2 WebUI 前端开发规范 (FSD + Atomic + MVVM)

前端 `dashboard/` 严格遵循现代前端工程的最佳实践，构建为自包含的单 Bundle 控制台：

```
dashboard/src/
├── shared/       # [Atoms 原子组件 / 基础通信库 / formatters]
├── entities/     # [领域实体: task, trace, group, metric, report]
├── features/     # [交互行为: trigger-task, filter-traces, cancel-task]
├── widgets/      # [Organisms 复合微件: TraceTable, TraceDrawer, ActiveTaskBoard]
├── pages/        # [页面组合与 MVVM ViewModel: use*ViewModel]
└── app/          # [根容器与全局上下文配置]
```

1. **MVVM 状态解耦**：
   * **ViewModel (`use*ViewModel.ts`)**：集中封装网络请求、防抖、排序、衍生计算及缓存失效；
   * **View (`*Page.tsx`)**：仅作为纯声明式 UI，禁止在 JSX 组件中内联 API 请求或复杂业务算法。
2. **零 `any` 策略 (Zero `any` Policy)**：
   * 全量开启 `@typescript-eslint/no-explicit-any: 'error'`；
   * 外部未定型数据一律使用 `unknown` 并配合类型守卫；
   * 宿主 Bridge 通信在 `shared/api/bridge.ts` 中维护强类型定义。
3. **冷数据缓存与精准失效**：
   * 仅对 `status !== "running"` 的已完成历史记录进行 LRU 内存缓存；
   * 依托 SSE 实时事件在任务状态流转时主动淘汰相关缓存，确保数据 100% 同步。
4. **构建输出规范**：
   * Vite 配置固定产物输出为 `pages/daily-analysis/assets/index.js`，避免动态哈希造成 Git 历史膨胀。
5. **前端静态检查命令**：
   ```bash
   pnpm lint        # 必须 0 警告 0 错误
   pnpm typecheck   # TypeScript 严格类型编译
   pnpm build       # 打包输出单 Bundle
   ```

---

## 3. 报告模板贡献指南 (Templates Contribution)

如果你想为插件贡献精美的新视觉主题模板，欢迎提交 PR！

### 3.1 模板目录结构
在 `src/infrastructure/reporting/templates/` 下新建你的主题目录（如 `my_theme/`）：

```text
src/infrastructure/reporting/templates/your_theme_name/
├── image_template.html      # 图片报告主模板 (必填)
├── activity_chart.html      # 活跃度图表组件 (必填)
├── topic_item.html          # 话题列表项组件 (必填)
├── user_title_item.html     # 用户称号项组件 (必填)
└── quote_item.html          # 金句项组件 (必填)
```

### 3.2 模板变量对照表

#### 主模板 (`image_template.html`)
| 变量名 | 说明 | 示例 |
|---|---|---|
| `current_date` | 当前日期 | 2026年08月25日 |
| `current_datetime` | 当前时间戳 | 2026-08-25 22:00:00 |
| `message_count` | 消息总数 | 1,420 |
| `participant_count` | 参与人数 | 48 |
| `total_characters` | 总字符数 | 28,450 |
| `emoji_count` | 表情数量 | 312 |
| `most_active_period`| 最活跃时段 | 21:00 - 22:00 |
| `hourly_chart_html` | 渲染后的活跃度图表组件 HTML | - |
| `topics_html` | 渲染后的热门话题组件 HTML | - |
| `titles_html` | 渲染后的用户称号组件 HTML | - |
| `quotes_html` | 渲染后的金句组件 HTML | - |
| `total_tokens` | 本次分析消耗的 Token 总量 | 14,280 |

#### 组件子模板 (`*_item.html`)
* `activity_chart.html`: 注入 `chart_data` (包含 `hour`, `count`, `percentage` 的数组)；
* `topic_item.html`: 注入 `topics` (包含 `index`, `topic`, `contributors`, `detail`)；
* `user_title_item.html`: 注入 `titles` (包含 `name`, `title`, `mbti`, `reason`, `avatar_data`)；
* `quote_item.html`: 注入 `quotes` (包含 `content`, `sender`, `reason`, `avatar_url`)。

### 3.3 离线调试工具使用

插件内置了独立的离线模板渲染调试脚本，**无需启动 AstrBot 或连接真实 LLM** 即可瞬间预览 HTML 视觉效果：

```bash
# 渲染指定模板并输出到本地 HTML
uv run scripts/debug_render.py -t your_theme_name -o debug_output.html

# 查看帮助
uv run scripts/debug_render.py -h
```
在浏览器或 VSCode Live Server 中打开生成的 `debug_output.html` 即可实时热调 CSS 样式！

---

## 4. Commit 提交信息规范 (Conventional Commits)

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范，推荐采用**中文**清晰阐述改动场景与成效。

### 格式要求
```text
<type>(<scope>): <简要总结>

[可选正文：说明场景、背景、核心改动与成效]
```

### Type 类型枚举
* `feat`: 新增功能特性（如增加新平台适配、WebUI 新增图表组件等）；
* `fix`: 修复缺陷或 Bug；
* `refactor`: 重构代码（不改变外部行为，如分层重构、架构优化）；
* `perf`: 性能优化（如缓存机制、并发提速）；
* `docs`: 文档变更（如补充说明、修正错别字）；
* `test`: 新增或修改单元测试；
* `chore`: 构建配置、依赖更新、代码格式化与工作流调整。

---

## 5. Pull Request 提交流程

1. **Fork 本仓库** 到个人 GitHub 账号；
2. 从 `main` 分支切出特性分支（如 `feat/my-new-template` 或 `fix/onebot-retry`）；
3. 本地编写代码，并运行全套质量检查流水线（需保证 0 错误、0 警告）：
   ```bash
   # 1. 自动格式化并修复 Lint 问题
   uv run ruff format . ; uv run ruff check . --fix

   # 2. 静态类型检查
   npx pyright

   # 3. 运行全量单元测试
   uv run pytest tests/

   # 4. WebUI 前端静态检查与打包（若改动了 dashboard/ 源码）
   cd dashboard && pnpm lint && pnpm typecheck && pnpm build
   ```
4. 提交清晰规范的 Commit 并推送到你的 Remote 分支；
5. 在 GitHub 上发起 Pull Request，在 Description 中简要说明改动意图及测试验证结论；
6. 经过 CI 流水线自动化验证并通过 Maintainer Review 后即可合并入主分支！
