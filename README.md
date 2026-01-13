<div align="center">

# QQ群日常分析插件


[![Plugin Version](https://img.shields.io/badge/Latest_Version-v4.5.8-blue.svg?style=for-the-badge&color=76bad9)](https://github.com/SXP-Simon/astrbot-qq-group-daily-analysis)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-ff69b4?style=for-the-badge)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![](https://img.shields.io/badge/五彩斑斓的Bug群-Bug反馈群&水群-white?style=for-the-badge&color=76bad9&logo=qq&logoColor=76bad9)](https://qm.qq.com/q/oTzIrdDBIc)

_✨ 一个基于AstrBot的智能群聊分析插件，能够生成精美的群聊日常分析报告。[灵感来源](https://github.com/LSTM-Kirigaya/openmcp-tutorial/tree/main/qq-group-summary)。 ✨_

<img src="https://count.getloli.com/@astrbot-qq-group-daily-analysis?name=astrbot-qq-group-daily-analysis&theme=booru-jaypee&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto" alt="count" />
</div>


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
- **详细数据**: 包含消息统计、时间分布、关键词、金句等

### 🛠️ 灵活配置
- **群组管理**: 支持指定特定群组启用功能
- **参数调节**: 可自定义分析天数、消息数量等参数
- **定时任务**: 支持设置每日自动分析时间
- **自定义LLM服务** ：支持自定义指定的LLM服务

## 配置选项

> [!NOTE]
> 以下配置情况仅供参考，请仔细阅读插件配置页面中各个字段的说明，以插件配置中的说明为准。

| 配置项 | 说明 | 备注 |
|--------|------|--------|
| 启用自动分析 | 启用定时触发自动分析功能需要按照插件配置里面的说明填写相关的需要的字段；简略说明：打开自动分析功能，在群聊列表中添加群号或者使用 `/分析设置 enable` 启用当前群聊 | 默认关闭，需要填写机器人QQ号 |
| PDF格式的报告 | 初次使用需要使用 `/安装PDF` 命令安装依赖，首次使用命令安装，最后出现提示告诉你需要重启生效，是对的，需要重启 astrbot，而不是热重载插件。 | 输出格式需要设置为 PDF |
| 自定义LLM服务 | 插件配置中允许用户自行选取个人提供的 Astrbot 服务商列表中的大语言模型服务商 | 留空则回退到用户 Astrbot 现有服务商中第一个可用服务商 |

> [!IMPORTANT]
> **PDF 功能配置**：使用 `/安装PDF` 命令后，需要完全重启 AstrBot 才能生效，热重载插件无效！

> [!TIP]
> **自定义 LLM 服务**：新版本弃用此前硬编码的 provider 提供方式，采用更符合 Astrbot 生态的更用户友好的配置方式，根据配置键选取 Provider，支持多级回退：
>    1. 尝试从配置获取指定的 provider_id（如 topic_provider_id）
>    2. 回退到主 LLM provider_id（llm_provider_id）
>    3. 回退到当前会话的 Provider（通过 umo）
>    4. 回退到第一个可用的 Provider

## 效果
![默认模板效果图](./assets/scrapbook-demo.jpg)

<details>
<summary>点击展开查看其他模板效果图</summary>

format 模板效果图
![format效果图](./assets/format-demo.jpg)

simple 模板效果图(用于展示贡献指南)
![simple效果图](./assets/simple-demo.jpg)

retro_futurism 模板效果图
![retro_futurism效果图](./assets/retro_futurism-demo.jpg)

</details>

## 使用方法

### 基础命令

#### 群分析
```
/群分析 [天数]
```
- 分析群聊近期活动
- 天数可选，默认为1天
- 例如：`/群分析 3` 分析最近3天的群聊

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

## 安装要求

> [!CAUTION]
> **必需条件**：
> - 已配置 LLM 提供商（用于智能分析）
> - QQ 平台适配器

## 注意事项

> [!WARNING]
> 1. **性能考虑**: 大量消息分析可能消耗较多 LLM tokens
> 2. **数据准确性**: 分析结果基于可获取的群聊记录，可能不完全准确

## 更新日志

<details>
<summary>📋 点击展开查看完整更新日志</summary>

### v4.5.8
- 群贤毕至添加头像

### v4.5.7
- scrapbook 模板 footer 的 token 描述调整
- 仓库地址更新

### v4.5.6
- 更新 scrapbook 模板排版

### v4.5.5
- 修复 Jinja2 模板渲染线程安全问题
- 性能优化，CPU 密集型计算（统计和分析）已卸载到各线程池，避免阻塞事件循环

### v4.5.4
- 更新插件 metadata 描述，为了使用户更容易搜索到此插件，重新在插件市场提交


### v4.5.2
- 新增 `/查看模板` 指令，以合并转发消息形式查看所有模板预览图
- `/设置模板` 指令现支持通过序号设置模板 (@clown145)


### v4.5.0
- 添加新的模板主题 retro_futurism， 灵感来源明日方舟 孤星 未来复古主义主题；添加模板调试工具 scripts/debug_render.py，方便用户在不启动 AstrBot 的情况下调试模板效果 （@Saramanda9988）

### v4.4.0
- 修复可能的图片生成成功但是发送失败的情况，增加 Fallback 的 BASE64 编码的图片发送方式（@Heximiao）

### v4.3.0
- 纠正关闭特定分析区但是基础样式没有去除的 bug

### v4.2.0
- 适配 **AstrBot v4.5.7+** 的新 LLM API 标准，支持多套主题模板切换使用，欢迎为插件贡献新的报告模板

### v4.1.0
- 群黑白名单机制
- 使用信号量（Semaphore）并发限制和弱引用字典（WeakValueDictionary）优化锁管理

### v4.0.0
- feat(report/template): 全新设计的报告模板，采用卡通手账日记风格设计，灵感来源于 GalGame 《五彩斑斓的世界》女主二阶堂真红和男主悠马每天晚上写日记的场景

### v3.9.5
- fix(report/template): 迁移到应该使用的 jinja2 模板引擎， HTML 文件方便调试和修改

### v3.9.0
- 感谢 lxfight，参考 [Mnemosyne-AstrBot长期记忆插件](https://github.com/lxfight/astrbot_plugin_mnemosyne) 实现自动发版和 Issue 模板

### v3.8.0
- feat(multi-qq-platforms): 尝试适配多个适配器实例，支持填入多个QQ账号；
- 可以填写用于自动分析的机器人QQ号、多消息平台QQ号、不希望出现于群分析中的其他人的机器人QQ号等，这种群聊中出现但是不希望分析的QQ号；
- fix(多适配器支持): 处理 Bot 实例与平台 ID 之间的对应关系，确保在多适配器环境下正确获取消息和发送报告。

### v3.7.0
- feat(provider): 根据配置键获取 Provider，支持多级回退：

    1. 尝试从配置获取指定的 provider_id（如 topic_provider_id）

    2. 回退到主 LLM provider_id（llm_provider_id）

    3. 回退到当前会话的 Provider（通过 umo）

    4. 回退到第一个可用的 Provider

### v3.6.0
- 由于 napcat 存在的问题 [NapNeko/NapCatQQ#441](https://github.com/NapNeko/NapCatQQ/issues/441) 选择取消分页拉取和多次轮询获取逻辑，解决获取消息数量异常的情况
@exynos967

### v3.5.0
- max_tokens 参数处理 以及 过滤机器人自己的消息

### v3.4.1
- 更新配置文件配置项名称，为了避免用户手动卸载插件配置文件的更新，避免受 3.3.0 以及 3.2.0 错误版本的提示词配置影响导致群分析不可用

### v3.4.0
- 自定义提示词模板，简单修复格式问题，尽量保证可用

### v3.3.0
- 修复 `群分析获取历史消息的机制并不严格，出现超过当天消息、超过最大数量限制的情况` 的问题

### v3.2.0
- 自定义提示词模板，推荐根据群聊情况进行自定义修改以满足自己的需求

### v3.1.0
- llm_analyser 串行执行三部分分析导致处理单次请求耗时太长，修改为异步网络请求

### v3.0.0
- 解决自动分析器获取群聊消息失败的问题

### v2.9.0
- PDF 安装过程不阻塞主线程

### v2.8.0
- (#24) 在配置中启用 "偏好使用群昵称" @Ri-Nai

### v2.7.0
- (llm_analyzer) LLM 输出 json 提取增强

### v2.6.0
- (自动分析处理) 纠正分析日期处理情况

### v2.5.0
- 处理了自动分析器的不唯一问题
- 自动分析器并发处理群聊

### v2.4.0
- 纠正无法正确获取当前使用的模型情况

### v2.3.0
- 修复定时触发自动分析无法获取到实例的 bug，现在启用该功能需要传入 bot 的 QQ 号

### v2.2.0
- image 格式的报告图片清晰度提高
- 字体稍微调大，但是实际效果也不怎么好，后续可能需要彻底改变排版方式再进行调整

### v2.1.0
- 支持配置自定义 Provider 或者留空，支持自定义模型的重试和超时处理，思考模型可以根据情况延长请求超时时间

### v1.9.0
- 生成 24h 时间段活跃情况分析

### v1.8.0
- 修复表情统计情况

### v1.7.0
- 修复提示
- 解耦化

### v1.4.0
- PDF 版本情况说明更新

### v1.3.0
- token 消耗情况说明

### v1.2.0
- 增加了对 LLM 话题分析部分的提示词提示规范，并且提供正则处理来提高服务可用性

### v1.1.0
- 修复了部分bug
- 优化了权限情况，管理员控制绝大部分命令（防止滥用 token）
- 增加了定时自动触发分析功能
- 发送 PDF 版的推送，提供命令安装相关配置，也可以不配置 PDF 版

### v1.0.0
- 初始版本发布
- 支持基础群聊分析功能
- 智能话题和用户称号分析
- 精美可视化报告生成

</details>

## 常见问题 (FAQ)

### 获取不到带记录的引用消息

**现象**：
后台日志出现 `[warn] ... 似乎是旧版客户端 ... [error] ... 获取不到带记录的引用消息`。

**原因**：
这是由于 NapCat/NTQQ 消息 ID 格式变动、消息过期或临时会话限制导致的。机器人尝试降级使用旧版序号查找失败。

**忽略**：如果只是偶尔出现（如回复久远消息），不影响机器人核心功能（收发消息），可以直接忽略。


## 贡献

### 项目架构图

<div align="center">

![项目架构图](./assets/structure-demo.jpg)

</div>

### 贡献指南

<div align="center">

![贡献指南](./assets/contribution-guide.jpg)

</div>

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
在 `src/reports/templates/` 目录下创建一个新的文件夹，例如 `my_theme`。

#### 2. 必需文件结构
您的模板目录需要包含以下文件：

```text
src/reports/templates/your_theme_name/
├── image_template.html      # 图片报告主模板
├── pdf_template.html        # PDF报告主模板
├── activity_chart.html      # 活跃度图表组件
├── topic_item.html          # 话题列表项组件
├── user_title_item.html     # 用户称号项组件
└── quote_item.html          # 金句项组件
```

#### 3. 模板变量说明

**主模板 (`image_template.html` / `pdf_template.html`) 可用变量:**
- `current_date`: 当前日期 (YYYY-MM-DD)
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
- `topic_item.html`: `topic` (包含 `keyword`, `count`, `summary` 的对象), `loop.index` (序号)
- `user_title_item.html`: `user` (包含 `nickname`, `user_id`, `titles` (列表), `description` 的对象)
- `quote_item.html`: `quote` (包含 `content`, `sender_nickname`, `reason` 的对象)

#### 4. 参考示例
您可以参考 `src/reports/templates/simple/` 目录下的文件，这是一个最简化的模板实现，包含了所有必需的基本结构。

#### 5. 模板调试工具

本项目提供了一个专门用于模板开发的调试工具 `scripts/debug_render.py`，可以在不启动完整 AstrBot 环境的情况下快速预览模板渲染效果。

**使用方法：**

```bash
# 进入项目目录
cd astrbot-qq-group-daily-analysis

# 使用默认模板 (retro_futurism) 渲染
python scripts/debug_render.py

# 指定模板名称渲染
python scripts/debug_render.py -t simple

# 指定输出文件路径
python scripts/debug_render.py -t retro_futurism -o my_output.html

# 查看帮助信息
python scripts/debug_render.py -h
```

**工具特性：**

- 使用 Mock 数据模拟真实的群聊分析结果
- 无需配置 LLM 服务或启动 AstrBot
- 输出可使用live server打开 HTML 文件，并进行修改查看
- 支持所有内置模板的快速切换预览

**开发工作流推荐：**

1. 修改模板文件
2. 运行调试工具生成预览
3. 在浏览器中打开生成的 HTML 文件查看效果
4. 重复上述步骤直到满意

</details>

## 许可证

MIT License


欢迎提交Issue和Pull Request来改进这个插件！
