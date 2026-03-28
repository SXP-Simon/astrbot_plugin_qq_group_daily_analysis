<div align="center">

# 群聊日常分析插件

[![Plugin Version](https://img.shields.io/badge/Latest_Version-v4.9.8-blue.svg?style=for-the-badge&color=76bad9)](https://github.com/SXP-Simon/astrbot-qq-group-daily-analysis)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-ff69b4?style=for-the-badge)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis) 

<table align="center" style="border: none;">
  <tr>
    <td style="border: none;" align="center">
      <a href="https://qm.qq.com/q/oTzIrdDBIc"><img src="https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/QQ.png" width="300" alt="QQ Group"></a>
    </td>
    <td style="border: none;" align="center">
      <a href="https://t.me/AstrBotPluginGroupDailyAnalysis"><img src="https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/TG.png" width="300" alt="Telegram Group"></a>
    </td>
  </tr>
  <tr>
    <td style="border: none;" align="center"><b>QQ群</b></td>
    <td style="border: none;" align="center"><b>Telegram群</b></td>
  </tr>
</table>


_✨ 一个基于 AstrBot 的智能群聊分析插件，支持 **QQ (OneBot)**、**Telegram**、**Discord**，未来支持更多平台。 [灵感来源](https://github.com/LSTM-Kirigaya/openmcp-tutorial/tree/main/qq-group-summary)。 ✨_

<img src="https://count.getloli.com/@astrbot-qq-group-daily-analysis?name=astrbot-qq-group-daily-analysis&theme=booru-jaypee&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto" alt="count" />
</div>


## Feishu / Lark 集成说明

本插件通过 `LarkAdapter` 复用 AstrBot 已有的 `lark_oapi` 生态能力，在获得授权后即可对 Feishu 群聊执行完整的消息采集与分析。

- **一次性授权**：在飞书开放平台中为你的应用补齐如下权限（仅需在初次部署时授予）：
  - `im:message:readonly`、`im:chat:readonly`（读取群消息/群信息）
  - `contact:contact.base:readonly`（拉取用户昵称/头像；缺少该权限会导致头像永远显示默认）
  - 发送需要的附加 scope（如 `im:message:send` / `im:message:receive_v1` / 上传相关的 `im:resource` 系列）

- **用户头像保障**：插件在分析前会调用 `LarkAdapter.prepare_group_member_cache`，一次性批量拉取最多 100 名活跃成员的头像并在缓存中保留，让后续分析阶段不再遇到“未授权头像”。
- **令牌与长时运行**：飞书的 `tenant_access_token` 有 2 小时有效期，分析任务运行时间若超过此周期，请确保你的 Bot 框架会自动刷新令牌（通常是 SDK 默认行为）。

读取 Feishu 配置后，按照上述授权顺序重新安装/刷新应用，就能在报告里面看到与 QQ/Telegram 一样的用户筛选、头像与 LLM 输出。


## 效果

<table align="center" width="100%">
  <tr>
    <td align="center" width="33.3%" valign="top">
      <p><b>Scrapbook (默认)</b></p>
      <img src="https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/scrapbook-demo.jpg" alt="scrapbook" width="100%">
    </td>
    <td align="center" width="33.3%" valign="top">
      <p><b>Retro Futurism</b></p>
      <img src="https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/retro_futurism-demo.jpg" alt="retro_futurism" width="100%">
    </td>
    <td align="center" width="33.3%" valign="top">
      <p><b>HatsuneMiku</b></p>
      <img src="https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/HatsuneMiku-demo.jpg" alt="HatsuneMiku" width="100%">
    </td>
  </tr>
  <tr>
    <td align="center" width="33.3%" valign="top">
      <p><b>Hack</b></p>
      <img src="https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/hack-demo.jpg" alt="hack" width="100%">
    </td>
    <td align="center" width="33.3%" valign="top">
      <p><b>Format</b></p>
      <img src="https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/format-demo.jpg" alt="format" width="100%">
    </td>
    <td align="center" width="33.3%" valign="top">
      <p><b>Simple</b></p>
      <img src="https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/simple-demo.jpg" alt="simple" width="100%">
    </td>
  </tr>
</table>




## 功能特色

### 🎯 智能分析
- **统计数据**: 全面的群聊活跃度和参与度统计
- **话题分析**: 使用LLM智能提取群聊中的热门话题和讨论要点
- **用户画像**: 基于聊天行为分析用户特征，分配个性化称号
- **圣经识别**: 自动筛选出群聊中的精彩发言

### 📊 可视化报告
- **多种格式**: 支持图片和文本输出格式
    - **精美图片**: 生成美观的可视化报告
    - **PDF报告**: 生成专业的PDF格式分析报告（需配置）
    - **QQ群**: 支持上传到群相册和群文件，查阅黑历史友好
- **详细数据**: 包含消息统计、时间分布、关键词、金句等

> [!warning]
> **实验性开发中**：
> - 多平台支持功能尚在开发中，当前仅支持QQ OneBot, Discord, Telegram。
> - 旧版本稳定版在[QQ 分支](https://github.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis/tree/QQ)，仅 QQ 平台支持


> [!CAUTION]
> **Discord 用户重点注意**：
> 如果机器人无法获取群列表或分析报 `403 Forbidden`，请检查 Discord 开发者面板中：
> 1. **Privileged Gateway Intents**: 开启 `Message Content Intent`。
> 2. **频道权限**: 确保机器人所在的频道，对应的角色拥有 **“查看消息历史记录”** 权限。

> [!IMPORTANT]
> **Telegram 用户重点注意**：
> 1. 如果 TG Bot 不是群管理员，务必在拉入群前先关闭 BotFather 隐私模式。
> 2. 如果 Bot 已经在群里且不是管理员，关闭隐私模式后必须先移除再重新拉入群，否则新设置不会生效。
>
> 注：群聊隐私模式关闭流程：`@BotFather`→左下角Open→选择要调整的bot→Bot Settings→将`Group Privacy`关闭


> [!TIP]
> 如果生成图片失败，日志显示 `Endpoint https://t2i.soulter.top/text2img failed`、`Endpoint https://t2i.rcfortress.site/text2img failed` 这种情况并回退到文本总结，可考虑自部署 T2I 服务。
>
> <details>
> <summary><b>若不便自部署，可尝试使用以下 T2I 服务（点击展开）：</b></summary>
>
> - **Hugging Face 服务**: `https://huggingface.co/spaces/clown145/astrbot-t2i-service`
> - **API 接口地址**: `https://clown145-astrbot-t2i-service.hf.space`
>   - **说明**: 
>     1. **复制空间**：可访问上方空间地址并点击 **Duplicate Space** 复制到自己的账号下使用。
>     2. **配置填写**：在 **AstrBot 系统配置** 中填入相应的 API 地址（格式通常为 `https://用户名-空间名.hf.space`）。
>     3. **稳定性**：在一段时间内大概率稳定，但不保证长期有效。
>     4. **休眠保活**：由于免费空间若长时间（约 48 小时）无人访问会进入休眠。可选择使用保活服务（如 [UptimeRobot](https://uptimerobot.com/)）定期访问 API 地址以保持其处于唤醒状态。
>
> - **国内加速 (CF 代理)**: `http://t2i.ciallo.de5.net`
>   - **说明**: 在国内直接访问原始域名下载图片可能较慢，可选择使用此代理域名。在一段时间内大概率稳定。
> </details>
>
> **自部署 T2I 文档**：docs.astrbot.app/others/self-host-t2i.html


### 🛠️ 灵活配置
- **多平台支持**: 自动识别并适配 OneBot, Discord, Telegram 等平台
- **群组管理**: 支持指定特定群组启用功能（支持跨平台黑白名单）
- **参数调节**: 可自定义分析天数、消息数量等参数
- **定时任务**: 支持设置每日自动分析时间
- **增量分析**: 全新的滑动窗口分析模式，全天候覆盖群聊消息
- **自定义LLM服务**: 支持自定义指定的LLM服务



## 配置选项

> [!NOTE]
> 以下配置情况仅供参考，请仔细阅读插件配置页面中各个字段的说明，以插件配置中的说明为准。

| 配置项 | 说明 | 备注 |
|--------|------|--------|
| 定时分析名单模式 + 列表 | 控制哪些群参与定时任务（报告时间点触发）。 | `whitelist + 空列表` 表示不注册定时任务 |
| 增量分析名单模式 + 列表 | 控制哪些群走增量模式，其他群走传统全量。 | `whitelist + 空列表` 表示不启用增量周期任务 |
| PDF格式的报告 | 初次使用需要使用 `/安装PDF` 命令安装依赖。需重启 AstrBot 生效。 | 输出格式需设为 PDF |
| 自定义LLM服务 | 用户可自行选取个人提供的服务商。 | 留空则回退到默认服务商 |

### 分析黑白名单配置说明（小白能懂）

下面只讲“在面板里怎么点”。

#### 自动分析的判定顺序（很重要）

系统会按下面顺序判断，前一关没过就直接停止：

1. 基础群权限（`basic`）
2. 定时分析名单（`auto_analysis`）
3. 增量名单（`incremental`，只决定模式，不决定放行）

一句话版：  
`basic` 决定“能不能参与自动分析” -> `auto_analysis` 决定“会不会自动触发” -> `incremental` 决定“触发后用哪种分析方式”。

#### 场景 A：只让一个群自动出报告（最常用）

1. 在插件配置面板找到 `定时分析设置`。
2. 把 `定时分析名单模式` 设为 `whitelist`。
3. 在 `定时分析群列表` 里添加你的目标群（建议粘贴 `/sid` 拿到的完整会话ID）。
4. 在 `自动分析时间列表` 里填时间（例如 `09:00`、`21:30`）。
5. 去 `增量分析设置`：
6. 把 `增量分析名单模式` 设为 `whitelist`，并保持 `增量分析群列表` 为空。  
这样就是“这个群会自动跑，但走普通分析，不走增量”。

#### 场景 B：除了某个群，其他群都自动跑

1. 在 `定时分析设置` 里把 `定时分析名单模式` 设为 `blacklist`。
2. 在 `定时分析群列表` 里填“不要自动跑”的那个群。
3. 在 `自动分析时间列表` 里填每天自动运行时间。
4. 如果你希望其他群默认走增量：
5. 在 `增量分析设置` 把 `增量分析名单模式` 设为 `blacklist`，并把 `增量分析群列表` 留空。

#### 场景 C：Telegram 用户怎么填最稳

1. 在面板里需要填群的地方，尽量填完整会话ID（例如 `telegram2:GroupMessage:-1001234567890`）。
2. 不建议新手只填纯群号，容易填错平台。
3. 先在群里执行 `/sid`，复制结果粘贴到列表里就行。

#### 最容易踩坑的 3 点

- `定时分析名单模式` 选 `whitelist` 时，如果 `定时分析群列表` 为空，任务不会自动跑。
- `增量分析名单模式` 选 `whitelist` 时，如果 `增量分析群列表` 为空，增量不会生效，会走普通分析。
- `增量失败自动回退全量分析` 建议保持开启，这样增量异常时也能尽量产出报告。

#### 你可能会问（关键边界）

- 不在“定时白名单”里，但在“增量白名单”里，会触发吗？  
不会。因为会先被“定时白名单”拦住，进不到增量判断。

- 不在“基础群权限”里，但你开了定时分析，会触发吗？  
不会。基础群权限是第一关，不通过就不会进入后续流程。

> [!IMPORTANT]
> **多平台配置注意**：
> - **自动发现**: 插件会自动发现已登录的 Bot 实例。

> [!TIP]
> **自定义 LLM 服务回退机制**：性能优先，策略如下：
>    1. 尝试从配置获取指定的 provider_id
>    2. 回退到主 LLM provider_id
>    3. 回退到当前会话的 Provider (UMO)
>    4. 回退到第一个可用的 Provider


## 使用方法

### 基础命令

#### 群分析
```
/群分析 [天数]
```
- 分析群聊近期活动
- 天数可选，默认为1天
- 例如：`/群分析 3` 分析最近3天的群聊

#### 增量状态
```
/增量状态
```
- 查看当前增量分析的实时状态
- 显示当前滑动窗口内的分析次数、消息数、话题数等统计
- **仅在启用增量分析模式时可用**

#### 分析设置
```
/分析设置 [操作]
```
- `enable`: 为当前群启用分析功能
- `disable`: 为当前群禁用分析功能  
- `status`: 查看当前群的启用状态
- 例如：`/分析设置 enable`

#### 模板设置
```
/查看模板
/设置模板 [模板名称或序号]
```
- `/查看模板`: 查看所有可用模板及预览图
- `/设置模板`: 查看当前模板和可用模板列表
- `/设置模板 [序号]`: 切换到指定序号的模板
- 例如：`/设置模板 1` 或 `/设置模板 scrapbook`

## 平台支持与要求

| 平台 | 适配器类型 | 特殊要求/说明 |
|------|-----------|--------------|
| **QQ** | OneBot v11 | 建议使用 NapCat/Lagrange。需注意消息分页拉取限制。 |
| **Discord** | Discord | **必须** 拥有 `Read Message History` (查看消息历史记录) 权限。 |
| **Telegram** | Telegram Bot API | 若机器人不是群管理员，入群前需先在 BotFather 关闭隐私模式 (`/setprivacy` -> `Disable`)。若机器人已在群内且非管理员，关闭后需要先移出机器人再重新拉入，设置才会生效。 |



## 注意事项

> [!WARNING]
> 1. **性能考虑**: 大量消息分析可能消耗较多 LLM tokens
> 2. **数据准确性**: 分析结果基于可获取的群聊记录，可能不完全准确

## 增量分析模式 (Beta)

增量分析模式是为了解决消息量大的群聊（如日均消息 > 500 条）在单次分析时容易丢失上下文的问题。

**核心特性：**
- **滑动窗口**：不再受限于自然日，分析窗口随时间滑动（如过去 24 小时），确保任何时候生成的报告都覆盖完整的时间段。
- **分批处理**：定时（如每 2 小时）执行一次小批量分析，减轻 LLM 瞬时压力。
- **自动去重**：智能识别重复话题和金句，合并生成最终报告。

**启用方法：**
- 通过 `incremental_group_list_mode + incremental_group_list` 指定哪些群走增量模式，并根据需要调整分析间隔 (`incremental_interval_minutes`) 和消息阈值。

## 常见问题 (FAQ)

### 获取不到带记录的引用消息

**现象**：
后台日志出现 `[warn] ... 似乎是旧版客户端 ... [error] ... 获取不到带记录的引用消息`。

**原因**：
这是由于 NapCat/NTQQ 消息 ID 格式变动、消息过期或临时会话限制导致的。机器人尝试降级使用旧版序号查找失败。

**忽略**：如果只是偶尔出现（如回复久远消息），不影响机器人核心功能（收发消息），可以直接忽略。


## 贡献




### 开发环境设置

为了保持代码质量，本项目使用 [pre-commit](https://pre-commit.com/) 钩子进行代码规范检查和自动修复。所有的贡献代码都必须通过 pre-commit 检查。

#### 1. 安装 pre-commit
```bash
pip install pre-commit
```

#### 2. 安装 git hook
在项目根目录下运行，这将确保在每次提交时自动运行检查：
```bash
pre-commit install
```

#### 3. 手动运行检查
如果需要手动触发所有文件的检查（推荐在提交前运行一次）：
```bash
pre-commit run --all-files
```

### 模板贡献指南

<details>
<summary>🎨 点击展开查看如何贡献你的自定义模板给更多人玩</summary>

如果您想为插件贡献新的报告模板，请按照以下步骤操作：

#### 1. 创建模板目录
在 `src/infrastructure/reporting/templates/` 目录下创建一个新的文件夹，例如 `my_theme`。

#### 2. 必需文件结构
您的模板目录需要包含以下文件：

```text
src/infrastructure/reporting/templates/your_theme_name/
├── image_template.html      # 图片报告主模板
├── pdf_template.html        # PDF报告主模板
├── activity_chart.html      # 活跃度图表组件
├── topic_item.html          # 话题列表项组件
├── user_title_item.html     # 用户称号项组件
└── quote_item.html          # 金句项组件
```

#### 3. 模板变量说明

**主模板 (`image_template.html` / `pdf_template.html`) 可用变量:**
- `current_date`: 当前日期 (YYYY年MM月DD日)
- `current_datetime`: 当前时间 (YYYY-MM-DD HH:MM:SS)
- `message_count`: 消息总数
- `participant_count`: 参与人数
- `total_characters`: 总字符数
- `emoji_count`: 表情数量
- `most_active_period`: 最活跃时段
- `hourly_chart_html`: 渲染后的活跃度图表 HTML
- `topics_html`: 渲染后的热门话题 HTML
- `titles_html`: 渲染后的用户称号 HTML
- `quotes_html`: 渲染后的金句 HTML
- `total_tokens`: Token 消耗统计
- `prompt_tokens`: 提示词 Token 消耗
- `completion_tokens`: 生成内容 Token 消耗

**组件模板可用变量:**
- `activity_chart.html`: `chart_data` (包含 `hour`, `count`, `percentage` 的列表)
- `topic_item.html`: `topics` (列表，每一项包含 `index`, `topic` 对象, `contributors`, `detail`)
- `user_title_item.html`: `titles` (列表，包含 `name`, `title`, `mbti`, `reason`, `avatar_data` (Base64))
- `quote_item.html`: `quotes` (列表，包含 `content`, `sender`, `reason`, `avatar_url` (Base64))

#### 4. 参考示例
您可以参考 `src/infrastructure/reporting/templates/simple/` 目录下的文件，这是一个最简化的模板实现，包含了所有必需的基本结构。

#### 5. 模板调试工具

PDF 调试模板命令：

```bash
# 生成所有主题的 PDF (推荐)
uv run --with playwright --with diskcache scripts\debug_all_pdf_themes.py

# 生成指定主题的 PDF (例如：HatsuneMiku ，可以修改内部代码占位解决)
uv run --with playwright --with diskcache scripts\mock_pdf_gen.py
```

Image 模板调试：

本项目提供了一个专门用于模板开发的调试工具 `scripts/debug_render.py`，可以在不启动完整 AstrBot 环境的情况下快速预览模板渲染效果。

**使用方法：**

```bash
# 进入项目目录
cd astrbot-qq-group-daily-analysis

# 使用默认模板 (scrapbook) 渲染
python scripts/debug_render.py

# 指定模板名称渲染
python scripts/debug_render.py -t simple

# 指定输出文件路径
python scripts/debug_render.py -t retro_futurism -o my_output.html

# 查看帮助信息
python scripts/debug_render.py -h
```

```
uv run scripts\debug_render.py -t scrapbook -o debug_scrapbook.html
uv run scripts\debug_render.py -t hack -o debug_hack.html
uv run scripts\debug_render.py -t retro_futurism -o debug_retro.html
uv run scripts\debug_render.py -t format -o debug_format.html
uv run scripts\debug_render.py -t simple -o debug_simple.html
uv run scripts\debug_render.py -t spring_festival -o debug_spring.html
uv run scripts\debug_render.py -t HatsuneMiku -o debug_miku.html
```


**工具特性：**

- 使用 Mock 数据模拟真实的群聊分析结果
- 无需配置 LLM 服务或启动 AstrBot
- 输出可使用 live server 打开 HTML 文件，并进行修改查看
- 支持所有内置模板的快速切换预览

**开发工作流推荐：**

1. 修改模板文件
2. 运行调试工具生成预览
3. 在浏览器中打开生成的 HTML 文件查看效果
4. 重复上述步骤直到满意

</details>

## ❤️ Special Thanks

❤️ 特别感谢所有 Contributors 的贡献 ❤️

<a href="https://github.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=SXP-Simon/astrbot_plugin_qq_group_daily_analysis&max=200&columns=14" />
</a>

## Star History

<a href="https://www.star-history.com/#SXP-Simon/astrbot_plugin_qq_group_daily_analysis&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=SXP-Simon/astrbot_plugin_qq_group_daily_analysis&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=SXP-Simon/astrbot_plugin_qq_group_daily_analysis&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=SXP-Simon/astrbot_plugin_qq_group_daily_analysis&type=date&legend=top-left" />
 </picture>
</a>

## 许可证

MIT License


欢迎提交Issue和Pull Request来改进这个插件！
