# 群分析插件 LLM 工具开发指南与架构规范 (LLM Tool Engineering Guide)

> **文档性质**：工程技术规格书（Engineering Architecture Spec）  
> **适用模块**：`astrbot_plugin_qq_group_daily_analysis`  
> **依赖环境**：AstrBot Framework (Agent Tooling Pipeline / Function Calling)

---

## 1. 概述与工具交付范围矩阵 (Scope Matrix)

本文档制定 `astrbot_plugin_qq_group_daily_analysis` 接入 AstrBot 大模型函数调用（Function Calling）生态的完整技术规格。

在进入具体实现前，首先以矩阵形式明确本工程规划的**工具范围与架构边界**，确保任何开发者均能在 3 秒内识别开发目标与分工：

### 1.1 工具交付矩阵 (Tool Scope Matrix)

| 工具标识 (Tool Identifier) | 中文命名与功能定位 | 交互模式与耗时 | 交付状态 | 架构决策与职责边界 (First Principles) |
| :--- | :--- | :--- | :--- | :--- |
| **`group_daily_analysis_get_report`** | **读取群分析报告**<br>只读查询指定/当前群的历史日报、话题总结、群友称号、金句与统计指标 | **同步直出 (RPC)**<br>耗时 < 50ms | **【核心交付·优先落地】<br>(In-Scope)** | **轻量幂等只读通道**：纯读本地持久化快照（SQLite Checkpoint / AstrBot KV），零远端网络 I/O，无并发副作用，安全无害。 |
| **`group_daily_analysis_trigger`** | **按需触发群分析**<br>用户明确要求“重新分析”、“更新日报”、“提取最近金句”时按需执行分析流水线 | **异步受理 (Async Task)**<br>响应 < 500ms<br>后台约 1 分钟左右 | **【核心交付·严格门禁】<br>(In-Scope)** | **重型状态变更任务**：严禁同步阻塞！采用“异步提交即确认”模式；受严格管理员鉴权与群分析锁保护；执行模块做配置交集过滤与独立 Checkpoint 隔离，默认静默执行不扰民。 |

---

## 2. 交互阻力、反直觉陷阱与 AstrBot 原生机制剖析 (Bad Taste vs Good Taste)

在设计上述两个工具时，存在若干极具迷惑性但严重破坏用户体验与工程稳定性的“坏味道（Bad Taste）”。本节结合 AstrBot 框架底层机制进行深度剖析。

### 2.1 陷阱一：强行要求大模型或用户传 `group_id`（体验灾难）

#### ❌ Bad Taste（反直觉设计）
将工具入参定义为 `group_id: str`（必填），并在 Docstring 中要求 LLM 提取纯数字群号。
- **物理现实断层**：在群聊会话中，LLM 的上下文仅包含群友聊天内容，**大模型根本不知道当前群号是多少**（除非系统提示词硬编码注入）。
- **反问风暴**：
  - 群友随口问：“今天群里有什么好玩的金句吗？”
  - LLM 发现 `group_id` 必填，当即反问：“好的，请告诉我您的群号是多少？”（体验瞬间崩塌：群友心想“你不是就在群里吗？！”）。
  - 或者 LLM 产生幻觉，随机编造一个 `123456` 传参导致查询失败。
- **记忆负担**：在私聊场景中，真实人类用户无法记忆长达 9~10 位的数字 QQ 群号，用户脑海中只记得群名（如“原神开荒组”、“开发交流群”）。

####  Good Taste（对齐 AstrBot 官方核心哲学）
查阅 AstrBot 官方内置工具（`astrbot/core/tools/message_tools.py` 中的 `send_message_to_user`），官方对于目标会话参数的设计准则是：
> `"session: Optional. Leave empty for the current session. Use 'platform_id:message_type:session_id' to target another session."`

**设计准则：【默认留空即为当前会话 (Default to Current Session)】**！
- 工具入参统一设计为完全可选的标识：`group: str = ""`。
- **群聊内 0 门槛**：LLM 留空 `group`，工具内部自动调用 `event.get_group_id()` 秒级提取当前群号。大模型无需反问，用户无需报群号。
- **私聊支持群名模糊推断**：私聊中支持传入群名（如 `"开发交流群"`），工具底层利用本地已有元数据进行轻量模糊匹配。

---

### 2.2 陷阱二：即时触发时的同步阻塞超时与 IM 远端拉取陷阱

#### ❌ Bad Taste（同步阻塞 + 盲目拉取）
让 `trigger` 工具在被调用时直接 `await execute_daily_analysis()`，同步拉取数千条消息并等待大模型分析完成后才返回文本。
- **HTTP 30s 熔断崩溃**：全量分析包含拉取、清洗、3 次并发模型提取与排版，耗时 **约 1 分钟左右**。而大模型对话请求通常具备 **30 秒硬超时**，极易导致对话当场 504 报错。
- **远端拉取数据失真与游标稀释**：OneBot 远端接口拉取时若直接拿最新的 500 条消息，若白天群聊活跃（数千条），早上的重要内容全被冲淡；且高频翻页会触发平台封号风控。
- **普通用户刷 Token 漏洞**：若未加权限校验，普通群友随意一句话触发分析，会瞬间消耗管理员高额的大模型 API 配额。

####  Good Taste（异步受理 + 存储分层感知 + 严格鉴权）
- **异步提交即确认（Fire-and-Forget）**：工具在 500ms 内向后台提交任务，向 LLM 返回任务受理凭证（Trace ID），规避对话超时。
- **存储分层感知（Storage-Aware）**：
  - 本地优先（QQ 官方 / Telegram / 已有清洗 Checkpoint）：直接读本地数据库或快照；
  - OneBot 远端拉取：必须采用“时间窗口回溯锚定”与频控保护。
- **严格权限与群锁拦截**：仅管理员可触发，遇到运行中任务立即防重入拦截。

---

## 3. 跨 IM 平台真实存储全景与消息获取物理现实 (Storage Architecture & IM Realities)

在进行 LLM 工具设计与历史消息拉取时，必须深刻认清 AstrBot 框架核心与不同协议栈之间的真实底层存储拓扑：**消息并非存在 KV 中，各平台的存储与漫游机制呈现截然不同的物理链路**。

### 3.1 跨 IM 平台底层存储与处理机制全景矩阵

| 平台 / 协议栈 | 真实消息来源与底层存储引擎 | 入库幂等与容错机制 (Ingestion Idempotency) | 消息提取算法与拉取物理特性 |
| :--- | :--- | :--- | :--- |
| **QQ 官方机器人**<br>(`qq_official`,<br>`qq_official_webhook`) | **AstrBot 核心本地 SQLite**<br>通过 `context.message_history_manager`<br>持久化于本地数据库 `message_history` 表 | **两阶段预占与 LRU 确认防线**：<br>1. In-flight 预占（`_reserve_event_id` 集合拦截瞬时并发重复）；<br>2. 提交归档至 4096 容量 LRU 缓存（`_seen_event_ids`）；<br>3. 适配 `max_messages=10000` 兼容降级写入。 | **纯本地高并发读取 (< 50ms)**：<br>适配器直接基于 `timestamp BETWEEN start AND end` 进行分页闭区间扫描；出库维护 `seen_message_ids` 实施二次去重；零网络请求、零风控。 |
| **Telegram**<br>(`telegram`) | **AstrBot 核心本地 SQLite**<br>通过 `context.message_history_manager`<br>事件驱动流入本地 SQLite | **事件驱动入库 + 出库去重**：<br>消息流入时经 `MessageProcessingService` 统一解析写入；出库读取时通过 `seen_message_ids` 进行内存幂等去重。 | **本地 SQLite 闭区间扫描 (< 50ms)**：<br>优先直读本地库，避免直接向 Telegram 远端大跨度翻页触发官方苛刻的 `FloodWait` 封禁；出库支持按时间闭区间过滤。 |
| **OneBot v11**<br>(NapCat / LLOneBot / Lagrange) | **远端 IM 客户端动态漫游**<br>通过 `get_group_msg_history` 接口调用 | **依赖协议端与本地消息指纹**：<br>由适配器驱动解析 `message_seq` 与 `message_id`，出库维护集合去重重叠分页。 | **正统算法：时间窗口锚定与连续分页拼接**<br>(Time-bounded Window Pagination)：<br>1. 逆向探测：以 `message_seq` 回溯探测时间戳直至进入 `[T_start, T_end]`；<br>2. 精准采集：锁定锚点后分页拼接真实时段消息，超出下限立即停机；<br>3. 频控保护：翻页加 100~200ms 间隔与最大深度熔断，防闲聊刷屏稀释旧消息。 |

### 3.2 对 LLM 工具调用的核心启示

1. **QQ 官方与 Telegram 无网络超时风险**：
   因为它们直接由 AstrBot 核心的本地 SQLite 引擎托管，执行 `fetch_messages` 实际上是执行带索引的本地 SQL 查询，耗时通常 `< 50ms`，数据保真度极高且不受远端网络抖动影响。
2. **OneBot 远端拉取必须防范消息冲刷稀释**：
   在群聊活跃（单日数千条）的情况下，绝不能无脑拉取最新 500 条（否则早上的核心话题直接丢失）。必须采用上述“时间窗口回溯探测 + 分页拼接”算法，才能还原出真实、未经稀释的旧时段群聊全貌。
3. **读写严格解耦**：
   无论哪个平台，持久化入库与深度全量分析流水线始终保持严密解耦，确保工具端调用具有确定性、幂等性与极高的执行速度。

---

## 4. 工具一技术规格：读取群分析报告 (`group_daily_analysis_get_report`)

### 4.1 接口契约与 Docstring / Few-Shot

AstrBot 底层使用 `docstring_parser` 自动将 Docstring 解析为 OpenAI Tool Schema。为了确保模型精准理解并根除反问群号的问题，必须严格遵循以下 Docstring 规范：

```python
@filter.llm_tool("group_daily_analysis_get_report")
async def get_daily_report(
    self,
    event: AstrMessageEvent,
    report_section: str = "全部",
    date_range: str = "",
    group: str = "",
) -> str:
    """查询指定群聊的历史日常分析报告、话题总结与金句统计归档。

    【触发准则 (Trigger Rule)】
    - 仅当用户明确询问群聊总结、群日报、历史讨论话题、群友称号画像、群金句、发言活跃度等已有分析记录时调用。
    - 【重要交互原则】在群聊环境中查询时，大模型切勿反问用户群号，直接留空 group 参数发起查询！
    - 【负向禁令】严禁用于普通闲聊、询问当前即时消息、实时天气或要求重新生成/更新报告的操作；若用户要求重新分析请调用 trigger 工具。

    【参数规范 (Arguments)】:
    Args:
        report_section (string): 需要检索的报告模块，必须严格为以下枚举项或组合：'全部'（默认）、'话题'、'用户称号'、'金句'、'聊天质量分析'。多选使用逗号分隔，例如 '话题,金句'。
        date_range (string): 报告查询日期。格式规范：留空或 '最新'（获取最新一份）；单日 'YYYY-MM-DD'（如 '2026-10-02'）；相对日期如 '今天'、'昨天'；范围 'YYYY-MM-DD~YYYY-MM-DD'（如 '2026-10-01~2026-10-03'，最大跨度30天）。
        group (string): 目标群聊标识。默认留空（群聊场景下务必留空，系统将自动定位当前群）。仅在私聊或明确要求跨群查询时，填写数字群号（如 '680787260'）或群名称关键字（如 '开发交流群'）。

    【调用示范 (Few-Shot)】:
    - 群友在群里：“今天群里聊了些啥？” -> report_section="全部", date_range="", group=""
    - 群友在群里：“看看昨天的群金句和精彩语录” -> report_section="金句", date_range="昨天", group=""
    - 群友在群里：“前天群里有人聊买车吗？” -> report_section="话题", date_range="前天", group=""
    - 群友在群里：“国庆前三天群里讨论了什么话题？” -> report_section="话题", date_range="2026-10-01~2026-10-03", group=""
    - 用户在私聊：“帮我看看开发交流群昨天的日报” -> report_section="全部", date_range="昨天", group="开发交流群"
    - 用户在私聊：“查一下群 680787260 最新报告” -> report_section="全部", date_range="", group="680787260"
    """
```

### 4.2 智能群目标解析器 (Smart Target Resolver 4 级漏斗)

将模糊的 `group` 参数转化为物理确定的 `target_group_id`：
1. **留空推断**：`group` 为空时直读 `event.get_group_id()`。若处于私聊且为空，返回引导文本：
   `"[提示] 当前处于私聊会话中，请指明您想查询的群聊名称或群号（例如：“帮我看看开发交流群昨天的日报”）。"`
2. **纯数字提取**：剥离 UMO 前缀，若全为数字则直取。
3. **本地元数据模糊匹配（群名）**：文本入参查询 `traces.db`：
   ```sql
   SELECT group_id, group_name FROM analysis_traces
   WHERE group_name LIKE ? AND group_name != '' AND group_name != '未知群'
   GROUP BY group_id ORDER BY started_at DESC LIMIT 5;
   ```
   - **唯一命中**：绑定群号，在返回顶部标注 `【已为您定位群聊：xxx (123456)】`；
   - **多群歧义**：返回候选列表让 LLM 向用户追问确认；
   - **无匹配**：返回友好未找到提示并建议提供纯数字群号。
4. **白名单校验**：`ConfigManager.is_group_allowed(target_group_id)` 鉴权拦截。

### 4.3 双轨存储检索与同日去重 (Retrieval & Deduplication)
- **优先轨 (CheckpointStore)**：读取 `stage_checkpoints` 中 `stage_name = 'llm_analysis'`，同日多次分析**按 `date_str` 分组取 `MAX(created_at)`**，永远只向 LLM 呈现当天最新一份报告。
- **降级轨 (HistoryManager)**：Checkpoint 清理后，自动回退读取 AstrBot KV 中的轻量摘要。
- **邻近自愈探测**：目标日缺失时探测 ±1 天，命中时附带时间戳自愈标注。
- **字段投影与截断**：按请求模块裁剪无关字段，输出限制在 **40,000 字符以内**（防止极极端长跨度检索溢出上下文，默认充裕覆盖 30 天完整报告细节）。

---

## 5. 工具二技术规格：按需触发群分析 (`group_daily_analysis_trigger`)

### 5.1 接口契约与 Docstring / Few-Shot

```python
@filter.llm_tool("group_daily_analysis_trigger")
async def trigger_daily_analysis(
    self,
    event: AstrMessageEvent,
    analysis_sections: str = "全部",
    days: int = 1,
    group: str = "",
    render_to_chat: bool = True,
) -> str:
    """按需触发群聊聊天记录分析与报告生成流水线（默认在分析完成后自动渲染长图并发送至群聊）。

    【触发准则 (Trigger Rule)】
    - 仅当用户明确要求“重新分析”、“更新日报”、“提取最新群聊金句/话题”等主动执行计算的意图时调用。
    - 【重要交互原则】普通查询历史事实请严格调用 get_report 工具，严禁随意触发本工具！在群聊中触发时 group 必须留空。
    - 【交互提示】本工具在后台异步执行，默认（render_to_chat=True）会在计算完成后自动将精美长图发送到群里。受理成功后请明确告知用户分析已启动、长图稍后会自动发群，切勿虚构假分析结果。若用户明确要求“静默更新/后台计算不发群”，可将 render_to_chat 设为 False。
    - 【负向禁令】严禁用于闲聊、单纯询问已有数据；仅管理员具备触发权限。

    【参数规范 (Arguments)】:
    Args:
        analysis_sections (string): 本次需要执行的分析模块：'全部'（默认）、'话题'、'用户称号'、'金句'、'聊天质量分析'。多选逗号分隔。
        days (integer): 分析回溯天数，默认 1（当天或最近24小时），最大允许 7。
        group (string): 目标群聊标识。默认留空（自动定位当前群聊）。私聊中可填数字群号或群名称。
        render_to_chat (boolean): 是否在分析完成后自动渲染并向群聊发送长图报告。默认为 True。仅当用户明确要求静默入库时设为 False。

    【调用示范 (Few-Shot)】:
    - 管理员在群里：“重新分析一下今天的群聊” -> analysis_sections="全部", days=1, group="", render_to_chat=True
    - 管理员在群里：“帮我提取一下今天群里的金句” -> analysis_sections="金句", days=1, group="", render_to_chat=True
    - 管理员在群里：“静默更新一下日报数据库，不要发图” -> analysis_sections="全部", days=1, group="", render_to_chat=False
    - 管理员在私聊：“更新一下开发交流群的日报” -> analysis_sections="全部", days=1, group="开发交流群", render_to_chat=True
    """
```

### 5.2 触发工具的核心执行链路与 8 大 Corner Cases 处理规范

#### 1. 严格权限鉴权 (Permission Gatekeeper)
- 调用者必须满足：**发送者为 AstrBot 管理员**（配置项 `admin_users` 或 `check_admin_permission`）或**当前群的群主/管理员**。
- 若非管理员触发，立即拦截并返回标准文案：
  ```text
  [权限不足] 即时触发群分析属于高资源消耗操作，仅群管理员或 Bot 管理员可调用。普通群成员请直接询问历史报告（如：“今天群里聊了什么”）。
  ```

#### 2. 并发安全与群排他锁机制 (Concurrency & Group Lock)
- 检查 `self.analysis_service.is_group_running(target_group_id, "daily")`：
- 若该群已有定时任务或分析正在运行，**严禁重入**，立即返回：
  ```text
  [任务冲突] 群聊 {group_name} 当前已有分析任务正在执行中，请勿重复触发，稍后分析完成后可直接查询结果。
  ```

#### 3. 异步任务受理模式 (Async Fire-and-Forget)
- 为了规避对话端 **HTTP 30s 硬超时**，工具**绝不执行同步 `await`**，而是在入队后向 `asyncio.create_task` 派发后台任务，并在 **500ms 内向 LLM 返回任务受理回执**：
  ```text
  [任务已成功受理]
  - 目标群聊：{group_name} ({target_group_id})
  - 任务编号：{trace_id}
  - 执行模块：{effective_sections}
  - 预计耗时：约 1 分钟左右
  【系统指令】后台流水线正在执行，分析完成后将自动渲染并直接将报告长图发送至本群。请明确告知用户任务已启动、长图稍后会自动发群，切勿猜测或输出虚构的分析结果。
  ```

#### 4. 配置交集过滤 (Config Intersection Filter)
- `实际执行模块 = 请求模块 ∩ 插件全局配置已启用模块`。
- 若用户请求了 `"话题,聊天质量分析"`，但配置中 `chat_quality_analysis_enabled == False`，则流水线只跑话题分析，并在回执中标注：
  `"聊天质量分析未执行（该模块在插件配置中已关闭）"`。

#### 5. Checkpoint 隔离持久化 (Checkpoint Stage Isolation)
- 若请求为全量模块且 `days == 1`：归档为标准 `llm_analysis` Checkpoint，供日后查询。
- 若为部分轻量模块（如仅提取金句）：写入专属阶段 `AnalysisStage.ON_DEMAND_ANALYSIS`，**严禁污染或覆盖当天的完整全量日报快照**！

#### 6. 报告自动派发与静默入库分流 (Dispatch vs Silent Execution)
- 依据用户的自然期待，**默认行为 (`render_to_chat=True`) 为自动渲染长图发群**：
  - 后台异步协程在 `execute_daily_analysis` 计算成功后，自动调用 `report_dispatcher.dispatch(group_id, analysis_result, platform_id)`，将排版精美的图片报告直接推送到群聊；
  - 若调用方显式指定 `render_to_chat=False`（如“静默更新数据库”），则只执行分析、数据入库与 Trace 审计，不向群内推图。分析产物静默落库后，用户可随时通过 `group_daily_analysis_get_report` 查询。

#### 7. 消息量不足秒级熔断 (Message Threshold Guard)
- 针对 QQ 官方/Telegram 等本地库，若检测到该群自上次分析以来的有效消息数 `< 20` 条，直接秒级拒绝：
  ```text
  [跳过] 当前群聊自上次归档以来新增有效发言不足 20 条，无法提炼有价值的话题，建议产生更多讨论后再试。
  ```

#### 8. 孤儿回收与生命周期管理 (Task Reaper Integration)
- 后台派发的 Task 必须在启动时注册到 `ActiveTaskManager`（`register_task`），绑定孤儿任务回收器，确保在 Bot 关机或重载时能优雅回收。

---

## 6. 核心落地文件清单

| 文件路径 | 变更类型 | 核心职责 |
| :--- | :--- | :--- |
| `src/application/services/report_query_service.py` | **新建** | 封装报告**查询**完整用例：目标群 4 级漏斗解析、弹性日期清洗与 30 天熔断、Checkpoint 与 KV 双轨检索、同日去重、字段投影与 4000 字符截断。 |
| `src/application/services/analysis_trigger_service.py` | **新建** | 封装报告**触发**完整用例：管理员权限鉴权、群分析锁排他检查、配置交集计算、异步任务派发、ON_DEMAND Checkpoint 隔离写入、静默模式控制。 |
| `main.py` | **修改** | 声明并挂载两个 LLM 工具：<br>1. `@filter.llm_tool("group_daily_analysis_get_report")`<br>2. `@filter.llm_tool("group_daily_analysis_trigger")` |
| `tests/test_llm_tools.py` | **新建** | 单元测试套件：覆盖查询工具漏斗回退与投影截断、触发工具权限拦截、群锁并发拦截、异步受理回执格式验证。 |

---

## 7. 验收与质量门禁 (Checklist)

1. [ ] **Docstring 完整性**：符合 Google Docstring 规范，两个工具经过 AstrBot `docstring_parser` 解析无异常。
2. [ ] **群聊免反问验证**：在群聊环境下，LLM 发起调用时 `group=""`，能够直接从 `event.get_group_id()` 提取当前群，无任何向用户的多余反问。
3. [ ] **群名模糊匹配验证**：在私聊环境下，测试传入 `"交流群"` 能够正确命中本地数据库中的完整群名并返回标注；重名时返回歧义列表。
4. [ ] **触发工具安全隔离验证**：非管理员调用 `trigger` 被秒级拒绝；同一群并发调用 `trigger` 被群锁拦截。
5. [ ] **防超时验证**：`trigger` 调用在 500ms 内返回受理回执，后台任务独立执行，对话无 504/Timeout 现象。
6. [ ] **工程质检门禁**：通过 `ruff check .`、`ruff format .` 以及 `pytest`（100% 通过）。
