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
uv venv --python 3.12
uv pip install -r requirements-dev.txt

# 安装 git pre-commit 钩子 (务必同时安装 pre-commit 与 commit-msg 门禁)
pip install pre-commit
pre-commit install --hook-type pre-commit --hook-type commit-msg

# 或使用 Lefthook (二选一)
# npm install -g @evilmartians/lefthook && lefthook install
```

### 本地提交与完整检查分工

Lefthook 的 `pre-commit` 只检查暂存的 Python 文件（Ruff 格式与 lint）和 `dashboard/src/` 下的 JS/TS 文件（Oxlint 与 Oxfmt）。检查不自动修改或暂存文件；提交信息检查仍然保留。前端样式、配置和文档也做暂存文件格式检查；生成类型、锁文件、构建产物不交给格式化器。不会在提交时运行全量前端流水线。

每次原子提交无需重新跑全量测试和构建。开发时按影响范围运行定向测试；准备 PR 或完成一组功能修改时，在插件根目录执行相关的完整检查：

```bash
npx lefthook run check-frontend  # 全量 lint、类型检查、测试和构建
npx lefthook run check-python   # Ruff、Pyright 和完整 Python 测试
npx lefthook run check-contract # OpenAPI 一致性与生成类型检查（会更新类型文件）
```

这些任务是手动入口，不绑定 `pre-push`，也不是 CI 调用入口。CI 独立执行完整验证，不使用本地检查缓存。修改 API 后显式导出 OpenAPI 并生成类型；修改正式前端后，在 PR 前构建并提交 `pages/` 产物。CI 仍检查契约及构建产物与源码的一致性。

同一份代码已验证通过后，`git add`、拆分原子提交、修改提交说明或纯文档调整不要求重跑 pytest / Vitest。记录运行过的命令和覆盖范围；代码、测试、依赖、检查配置或运行环境发生相关变化后，重新运行受影响的检查。定向测试通过不代表全量测试通过，CI 不使用本地结果跳过验证。

手动入口已拆分为 `lint`、`typecheck`、`test`（前端另有 `build`），默认顺序执行，任一步失败就停止。已经运行过完整 pytest 或 Vitest 时，只补缺少的步骤：

```bash
# pytest 已通过，只补后端静态检查
npx lefthook run check-python --command lint --command typecheck
# 只运行完整后端测试
npx lefthook run check-python --command test
# Vitest 已通过，只补前端静态检查与构建
npx lefthook run check-frontend --command lint --command typecheck --command build
```

开发中直接运行 `uv run pytest tests/test_xxx.py` 等受影响用例；排查失败可用 `uv run pytest --lf tests/`，但这不是完整回归的替代。全量测试只需在相关改动完成后通过一次，不要在同一工作树上依次执行全量 pytest 和包含它的完整检查入口。

Oxlint / Oxfmt 配置、依赖或构建配置变化时，请运行完整前端检查。只改 CSS 等样式也需要在浏览器检查并重新构建。Lefthook 与 Python 的 pre-commit 框架选择一种安装，避免重复挂钩；使用后者时仍按同样要求执行完整检查。

| 日常场景 | 补充验证 |
| --- | --- |
| 单个业务函数或组件 | 相关测试；改动完成后补齐所属前端或后端的完整检查 |
| 删除、移动文件或调整公共接口 | 类型检查及受影响调用方测试，不能仅依靠暂存文件 lint |
| API / Schema 修改 | 契约检查、生成类型、前后端相关测试 |
| 依赖、测试配置、构建配置修改 | 重新执行相关完整验证，旧结果不再直接适用 |
| 纯样式修改 | 浏览器检查及构建；纯说明文档修改通常无需业务测试 |
| 部分暂存、拆分提交 | 工作树测试通过不等于每个中间提交都独立通过；确保每个提交自洽，不把未提交的修复当作验证依据 |

快速钩子只检查暂存路径对应的文件，不负责推断跨文件影响。手动完整检查没有自动“结果缓存”；选择 `--command` 时需确认省略步骤已有适用于当前代码的有效结果。

### 检查工具与解释器

Python 基线统一为 3.12。`requirements-tools.txt` 固定 Ruff 和 Pyright 的版本，Lefthook、pre-commit 和 CI 都通过 `scripts/check_python.py` 读取它，升级时只需修改这一处。工具通过 uv 的隔离缓存执行，不更新 AstrBot 的工具依赖；首次执行需要下载，后续复用缓存。

Pyright 使用运行检查脚本的 Python 解释器查找依赖，不再混用硬编码的 `site-packages`。嵌入 AstrBot 开发时，`uv run python ...` 使用宿主环境；独立检出时，先安装开发依赖，再用 `.venv/bin/python scripts/check_python.py typecheck`（Windows 为 `.venv/Scripts/python.exe`）。IDE 也应选择同一解释器。`extraPaths` 仅保留插件及嵌入开发时的 AstrBot 源码目录，支持跳转到宿主源码。

Ruff 保留现有测试目录豁免，并启用 `force-exclude`，目录扫描和暂存文件检查使用相同范围；这不影响 pytest 执行测试。旧枚举及泛型语法暂不强制改写，避免工具迁移改变运行时类型行为。引号由 formatter 管理，现代化语法检查统一交给 Ruff `UP`，不再重复运行 pyupgrade。

前端使用 Node.js 20.19+（20.x）或 22.12+，Oxlint 与 Oxfmt 固定版本并提交 pnpm 锁文件。`pnpm lint` 检查代码，`pnpm lint:fix` 修复可自动修复的问题；`pnpm format` 统一格式，`pnpm format:check` 只读检查。类型检查仍使用 `tsc`，行为测试仍使用 Vitest。已有 ESLint 推荐规则按职责映射到 Oxlint，语法和类型检查交给 TypeScript、格式交给 Oxfmt，不自动启用新一代 React Compiler 规则。

VS Code 可安装 `oxc.oxc-vscode` 扩展；仓库已为 JS/TS/React/CSS 配置保存时格式化，JSON 的自动换行设置保持不变。编辑器选择的 Python 环境也应安装 `requirements-tools.txt` 中固定的版本。

首次格式化与业务改动分开审阅；生成的 API 类型和构建产物由各自生成器维护。未合入的 `design-preview/` 原型暂不参与正式前端门禁。开发 mock 源码仍参与 lint、格式、类型及测试检查。

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
     uv run python scripts/check_python.py typecheck
     ```
6. **DDD 领域驱动设计与领域类型优先 (DDD & Domain Types First)**：
   * **领域层 (`src/domain/`)**：纯业务核心，不依赖具体外部框架与基础设施；
     - `entities/`：专职存放具有生命周期与持久化状态的聚合根（如 `IncrementalBatch`, `IncrementalState`）；
     - `value_objects/`：存放所有不可变值对象（如 `SummaryTopic`, `UserTitle`, `GoldenQuote`, `QualityReview`, `GroupStatistics`, `UnifiedMessage` 等），严禁设立模糊的 `models/` 目录；
     - `repositories/`：定义仓储与外部能力的纯抽象接口（如 `IAnalysisProvider`, `IConfigProvider`）；
     - `services/`：跨实体的纯领域计算规则（如 `IncrementalMergeService`, `StatisticsService`）。
   * **插件内部严禁不必要的反射 (Zero Unnecessary Internal Reflection)**：
     - 插件内部业务链路（`domain/`, `application/`, `infrastructure/` 内部各模块）必须 100% 依赖领域实体、值对象、强类型 DTO 与 Protocol 契约；
     - **严禁**在插件内部模块间使用 `getattr`/`hasattr`/`setattr` 或传递模糊的 `object`/`dict`/`Any`；所有属性与方法调用必须在静态分析期确定且支持 IDE F12 追踪。
   * **应用服务层 (`src/application/services/`)**：编排核心用例，杜绝上帝类（如将增量分析、断点恢复拆分至独立用例服务）；
   * **基础设施层 (`src/infrastructure/`)**：具体技术实现（适配器、渲染器、LLM 分析器、配置迁移器、持久化仓储等）。
7. **防腐层 (ACL) 规范与 AstrBot F12 直达开发体验 (Disciplined ACL & Seamless DX)**：
   * **只做“必要的反射”**：反射仅允许出现在基础设施层（如 `infrastructure/platform/`, `infrastructure/webui/`）与 AstrBot 宿主框架交互的防腐边界处，用于兼容 AstrBot 跨版本 API 变动、单测 Mock 桩及框架未初始化场景；
   * **兼顾运行时防腐与开发期 F12 直达**：**严禁因为使用了 `getattr` 防腐就放弃静态类型**。必须在 `if TYPE_CHECKING:` 下引入 AstrBot 官方核心类型（如 `Context`, `AstrBotConfigManager`, `PlatformManager`, `ProviderManager`, `PersonaManager` 等），并在调用处为局部变量显式声明强类型：
     ```python
     if TYPE_CHECKING:
         from astrbot.core.astrbot_config_mgr import AstrBotConfigManager

     # 运行时防腐隔离 + 开发期 F12 源码直达：
     acm: AstrBotConfigManager | None = getattr(self._context, "astrbot_config_mgr", None)
     if acm is not None and hasattr(acm, "get_conf"):
         conf = acm.get_conf(umo)  # 开发者按 F12 即可无缝跳转至 AstrBot 源码定义
     ```
   * 这一实践在保证插件运行期弹性解耦与容错的同时，实现了插件与 AstrBot 底层交互时 100% 强类型智能提示与源码直达跳转。
8. **一键格式化、自动修复 Lint 与单元测试**：
   * 强烈推荐使用一键格式化与自动修复指令（自动消除未使用的 import、调整 import 顺序及代码风格），准备后端 PR 时确认以下检查已通过；同一份代码已有通过结果时不要重复执行：
     ```bash
     uv run python scripts/check_python.py format . ; uv run python scripts/check_python.py lint . --fix
     uv run python scripts/check_python.py typecheck
     uv run pytest tests/
     ```

#### 2.1.1 任务生命周期状态机

任务状态表达持久化结果，`TaskEvent` 表达调用方请求的生命周期事件。新增转移必须更新领域白名单 `src/domain/services/task_state_machine.py`，并补充状态机与持久化并发测试；调用方不能直接写入目标状态。

| 当前状态 | 事件 | 目标状态 | 说明 |
|---|---|---|---|
| `RUNNING` | `SUCCEED` | `SUCCEEDED` | 正常完成 |
| `RUNNING` | `WARN` | `WARNING` | 带有可恢复问题或警告完成 |
| `RUNNING` | `FAIL` / `TIMEOUT` | `FAILED` | 执行失败或超时 |
| `RUNNING` | `CANCEL` / `ABORT` | `ABORTED` | 主动取消或异常回收 |
| `RUNNING` | `SKIP` | `SKIPPED` | 跳过任务 |

- 新 Trace 由 `TraceContext` 直接以 `RUNNING` 创建；目前 `PENDING` 是保留状态，状态机不允许从中转移。
- `SUCCEEDED`、`WARNING`、`FAILED`、`ABORTED`、`SKIPPED` 均为终态。只有白名单中明确列出的相同结果事件重放可以幂等通过，其他事件必须拒绝。
- `COMPLETED` 与 `CANCELLED` 是兼容旧记录的终态，新流程分别使用 `SUCCEEDED` 与 `ABORTED`。
- 正常生命周期更新通过 `TaskLifecycleService` 发出事件，由 SQLite 仓储按预期旧状态执行 CAS；快照保存不得覆盖已有生命周期状态。生命周期服务未装配时，`TraceContext.finish()` 保留兼容仓储路径，该路径仍须执行相同白名单校验和 CAS。
- `TraceSQLiteStore.reconcile_crashed_traces_on_startup()` 是受限的批量崩溃回收入口：只能将仍为 `RUNNING` 的历史记录收敛到 `ABORTED`，并按旧状态及可用的 `boot_id` 条件更新。当前启动恢复编排使用 `CrashRecoveryService` 和 `TaskLifecycleService`；普通业务流程不得使用直接 SQL 更新状态。

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
   * 全量开启 `typescript/no-explicit-any: 'error'`；
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

如果你想为插件贡献精美的新视觉主题模板，欢迎提交 PR！完整规范请参考 [`docs/REPORT_TEMPLATE_GUIDE.md`](docs/REPORT_TEMPLATE_GUIDE.md)。

### 3.1 模板目录结构（完整 7 件套）
在 `src/infrastructure/reporting/templates/` 下新建你的主题目录（如 `my_theme/`）：

```text
src/infrastructure/reporting/templates/your_theme_name/
├── image_template.html      # 图片报告主模板 (必选其一)
├── html_template.html       # 独立网页报告主模板 (必选其一)
├── activity_chart.html      # 活跃度图表组件 (必填)
├── topic_item.html          # 话题列表项组件 (必填)
├── user_title_item.html     # 用户称号/画像项组件 (必填)
├── quote_item.html          # 金句项组件 (必填)
├── chat_quality_item.html   # 群聊质量多维锐评组件 (必填)
├── shared_styles.html       # 可选：共享 CSS 样式片段
├── inline_assets.html       # 可选：内联 SVG / 装饰资产片段
└── template.json            # 可选：主题元数据 {"name": "中文显示名", "desc": "主题介绍"}
```
> **提示**：只需提供 `image_template.html` 或 `html_template.html` 任一即可被识别，缺失的子模块组件会自动向内置默认 `scrapbook`（手账）模板优雅兜底。

### 3.2 模板变量对照表

#### 主模板 (`image_template.html` / `html_template.html`)
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
| `chat_quality_html`| 渲染后的群聊质量多维锐评组件 HTML | - |
| `total_tokens` | 本次分析消耗的 Token 总量 | 14,280 |

#### 组件子模板 (`*_item.html`)
* `activity_chart.html`: 注入 `chart_data` (包含 `hour`, `count`, `percentage` 的数组)；
* `topic_item.html`: 注入 `topics` (包含 `index`, `topic`, `contributors`, `detail`)；
* `user_title_item.html`: 注入 `titles` (包含 `name`, `title`, `mbti`, `reason`, `avatar_data`, `profile_badge` 等)；
* `quote_item.html`: 注入 `quotes` (包含 `content`, `sender`, `reason`, `avatar_url`)；
* `chat_quality_item.html`: 注入 `chat_quality` (包含 `title`, `subtitle`, `summary`, `dimensions` 等)。

### 3.3 离线调试工具使用

插件内置了独立的离线模板渲染调试脚本，**无需启动 AstrBot 或连接真实 LLM** 即可瞬间预览 HTML 视觉效果并验证 MBTI/SBTI/ACGTI 映射：

```bash
# 渲染指定模板并输出到本地 HTML
uv run scripts/debug_render.py -t your_theme_name -o debug_output.html

# 指定人格卡片模式渲染 (支持 mbti | sbti | acgti)
uv run scripts/debug_render.py -t your_theme_name -o debug_output.html -m acgti

# 指定报告语言渲染（多语言模板改排版时逐个看）
uv run scripts/debug_render.py -t HatsuneMiku -f html_template.html -o out.html -l ja

# 一次渲染全部语言，产出 out.auto.html / out.zh-Hans.html / out.zh-Hant.html / out.en.html / out.ja.html
uv run scripts/debug_render.py -t HatsuneMiku -f html_template.html -o out.html --all-languages

# 查看「报告语言 auto」是怎么判的：逐条消息的票、占比、简繁字形/用词分数与命中的词
uv run scripts/debug_render.py --detect "我在用应用程式" "我查一下资讯" "软体更新完了"
uv run scripts/debug_render.py --detect-file messages.txt   # 一行一条消息

# 跑语言判定 golden 用例（与 pytest 共用 tests/data/language_cases.json）
uv run scripts/debug_render.py --cases tests/data/language_cases.json

# 查看全部调试参数
uv run scripts/debug_render.py -h
```
在浏览器或 VSCode Live Server 中打开生成的 `debug_output.html` 即可实时热调 CSS 样式！

> 语言也可以走环境变量（老写法仍兼容）：`DEBUG_REPORT_LANGUAGE=en`；命令行 `-l/--language` 优先。
> 同一份 golden 用例在单测里也会跑：`pytest tests/test_report_language.py -k golden`。

---

## 4. Commit 提交信息规范 (Conventional Commits)

本项目配置了自动化提交门禁脚本（`scripts/verify-commit.js`），在本地 `commit-msg` 阶段与 GitHub Actions CI 中严格校验提交信息格式。

### 4.1 格式要求
```text
<type>(<scope>): <简要总结 (Header)>

问题: 说明本次改动解决的具体痛点、缺陷根因或业务背景 (Body 第 1 点)
解决措施: 详细阐述核心实现方案、关键算法、架构分层与边界处理 (Body 第 2 点)
效果: 总结改动带来的实际成效、测试覆盖与稳定性提升 (Body 第 3 点)
```
> **要求**：
> 1. Header 简要总结必须简洁明了，建议使用中文；
> 2. 正文 Body 推荐采用 **STAR 三段式结构**（`问题:` / `解决措施:` / `效果:` 或 `背景:` / `方案:` / `成效:`），总字符数需 $\ge 40$ 字符。

### 4.2 Type 类型枚举
* `feat`: 新增功能特性；
* `fix`: 修复缺陷或 Bug；
* `refactor`: 重构代码（不改变外部行为，如分层重构、架构优化）；
* `perf`: 性能优化（如缓存机制、并发提速）；
* `docs`: 文档变更（如补充说明、修正错别字）；
* `test`: 新增或修改单元测试；
* `ci`: 持续集成与工作流脚本配置；
* `build`: 前端或工程打包构建（如 `build(dashboard)`）；
* `chore`: 依赖更新、代码格式化与琐碎配置调整。

### 4.3 Scope 作用域分类指南

为了保证 Git 提交历史的可溯源性与原子性，Scope 必须精准反映改动所属的架构层级或业务子域：

| 分类 | 推荐合法 Scope 示例 | 适用改动路径 / 说明 |
| :--- | :--- | :--- |
| **🏛️ 后端 DDD 分层** | `domain` / `app` / `infra` | `src/domain/`, `src/application/`, `src/infrastructure/` |
| **🌐 后端 WebUI 路由** | `infra/webui` / `infra/routes` / `infra/api` | `src/infrastructure/webui/` (Python 路由适配层) |
| **🎯 后端业务子域** | `analysis` / `comic` / `reporting` / `platform` / `scheduler` / `config` | 对应各业务领域服务与适配器实现 |
| **🎨 前端 Dashboard** | `dashboard` / `webui/pages` / `webui/widgets` / `webui/features` / `webui/entities` / `webui/shared` | `dashboard/` 源码及 FSD 架构分层 |
| **📦 前端静态产物** | `build(dashboard)` / `build(webui)` | `pages/daily-analysis/` (Vite 打包产物) |
| **🛠️ 工程与 CI** | `ci/github-actions` / `ci/workflow` / `ci/scripts` / `ci/lefthook` | `.github/workflows/`, `scripts/`, `lefthook.yml` |
| **🧪 单元测试** | `test/unit` / `test/e2e` / `test/webui` / `test/infra` | `tests/` 测试文件与 Mock 桩 |
| **📖 文档与其他** | `docs` / `docs/arch` / `core` / `deps` | `README.md`, `CONTRIBUTING.md`, `metadata.yaml` |

> **⚠️ 门禁拦截规则**：
> 1. **拒绝冗余 Scope**：禁止提交 `ci(ci)`、`test(test)`、`docs(docs)` 等 Type 与 Scope 完全相同的无意义格式，请使用细分子域（如 `ci/workflow`、`test/unit`）。
> 2. **解耦前后端 WebUI**：后端 Python WebUI 路由改动请使用 `infra/webui`，前端 React 控制台改动请使用 `dashboard` 或 `webui/*`。
> 3. **原子化提交**：单次 Commit 尽量聚焦于单一模块，避免跨领域混合提交。

---

## 5. Pull Request 提交流程

1. **Fork 本仓库** 到个人 GitHub 账号；
2. 从 `main` 分支切出特性分支（如 `feat/my-new-template` 或 `fix/onebot-retry`）；
3. 开发时执行定向检查，准备 PR 时补齐相关完整验证（已通过且未受后续改动影响的检查无需重跑）：
   ```bash
   # 1. 自动格式化并修复 Lint 问题
   uv run python scripts/check_python.py format . ; uv run python scripts/check_python.py lint . --fix

   # 2. 静态类型检查
   uv run python scripts/check_python.py typecheck

   # 3. 运行全量单元测试
   uv run pytest tests/

   # 4. WebUI 前端静态检查与打包（若改动了 dashboard/ 源码）
   cd dashboard && pnpm format:check && pnpm lint && pnpm typecheck && pnpm test && pnpm build:no-typecheck
   ```
4. 提交清晰规范的 Commit 并推送到你的 Remote 分支；
5. 在 GitHub 上发起 Pull Request，在 Description 中简要说明改动意图及测试验证结论；
6. 经过 CI 流水线自动化验证并通过 Maintainer Review 后即可合并入主分支！
