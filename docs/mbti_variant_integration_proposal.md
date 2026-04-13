# 趣味人格标签体系接入与扩展方案

## 背景

Issue #167 提出的核心诉求不是“把 MBTI 算得更准”，而是让群日常分析里的“用户称号”部分更有趣、更可玩。  
结合参考项目来看，这类能力更适合做成一个“可切换的人格标签体系”，而不是继续把输出能力绑定死在 `MBTI` 上。

这份文档基于以下内容整理：

- 当前插件实现
- [nexu-io/sbti-skill](https://github.com/nexu-io/sbti-skill)
- [tianxingleo/ACGTI](https://github.com/tianxingleo/ACGTI)

## 结论先行

推荐分三步推进：

1. 第一阶段只做“语义扩展，不改链路”
   先保留当前 `mbti` 字段和现有 JSON schema，不动渲染和数据模型，只把它解释为“人格标签结果位”。
2. 第二阶段做“配置化标签体系”
   增加 `label_system` 配置和对应的标签库/提示词片段，让 MBTI、SBTI、ACGTI 原型可以切换。
3. 第三阶段做“可扩展人格玩法”
   将标签体系抽象成数据驱动注册表，支持更多二创体系、群体画像、相性和彩蛋玩法。

如果只想低成本满足需求，第一阶段其实就够了，而且风险最低。

## 当前插件的切入点

当前插件已经天然具备接入基础，不需要重做分析主流程。

### 已有基础

- [`_conf_schema.json`](C:/Helianthus/SXP-Simon/astr/official/AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis/_conf_schema.json) 默认的 `user_title_prompt` 已要求模型返回 `title + mbti + reason`
- [`src/infrastructure/analysis/analyzers/user_title_analyzer.py`](C:/Helianthus/SXP-Simon/astr/official/AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis/src/infrastructure/analysis/analyzers/user_title_analyzer.py) 会把活跃用户统计整理成 prompt 输入
- [`src/domain/models/data_models.py`](C:/Helianthus/SXP-Simon/astr/official/AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis/src/domain/models/data_models.py) 的 `UserTitle` 数据结构已经有 `mbti` 字段
- [`src/infrastructure/analysis/utils/structured_output_schema.py`](C:/Helianthus/SXP-Simon/astr/official/AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis/src/infrastructure/analysis/utils/structured_output_schema.py) 和 [`src/infrastructure/analysis/utils/response_validation.py`](C:/Helianthus/SXP-Simon/astr/official/AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis/src/infrastructure/analysis/utils/response_validation.py) 已经把 `mbti` 当成结构化输出字段进行校验

### 当前约束

现在的字段名、schema、校验器、渲染层大概率都默认这个字段叫 `mbti`。  
因此如果直接把字段重命名为 `persona_label` 或 `label`，会产生一串兼容性修改。

所以最稳的策略是：

- 第一阶段继续保留 JSON 字段名 `mbti`
- 但在产品语义上把它解释成“人格标签”
- UI 文案和提示词里可以写“MBTI / SBTI / ACGTI 等趣味标签”

也就是说，先“改语义”，后“改字段”。

## 参考仓库分析

## 1. `sbti-skill` 的启发

`sbti-skill` 的强项不在算法复杂度，而在“人格库和文案库外置”。

它的关键特点：

- 用 `SKILL.md` 驱动完整交互流程
- 用 `references/personalities.md` 存人格定义、文案、稀有度
- 用 `references/questions.md` 存题库和计分规则
- 输出非常强调“人格代码、人格文案、展示仪式感”

对本插件最有价值的不是“30 道题测试”，而是这三个思想：

- 人格体系本身可以作为独立内容资产维护
- 提示词只要引用“标签库 + 风格说明”，就能产出有趣结果
- 彩蛋、稀有度、专属开场白都很适合做二次创作增强项

对群日常分析来说，可以直接借鉴为：

- 做一个 `labels/sbti.*` 的标签库文件
- 给每个标签补一句“群友画像文案”
- 允许模型只基于聊天统计做“轻量命中”，不追求测试式精确

这和 Issue 里“没必要太精确，省点 token”的方向完全一致。

## 2. `ACGTI` 的启发

`ACGTI` 的强项是“分层抽象稳定，上层内容可扩”。

它把能力拆成了几层：

- 底层维度：MBTI 四维
- 中层原型：8 个 archetype
- 上层角色：24 个具体角色
- 展示层：visual、tag、note、海报

对本插件最值得借鉴的是这种结构化分层：

- 不一定直接输出最细的标签
- 可以先输出“趣味原型”，再映射到更具体的标签
- 标签库、原型库、文案库都可以数据驱动扩展

对于群日常分析，适合转化成：

- 底层仍使用现有群聊统计特征
- 中层引入“群聊人格原型”
- 顶层再映射到 SBTI、ACGTI 风格标签或自定义称号

这样后面想继续加：

- 二次元原型
- 职场梗原型
- 互联网抽象人格
- 某个群专属黑话人格

都会更自然。

## 前端展示层思考

上一版方案更多集中在后端链路和数据结构，但这类玩法真正让用户感知到差异的地方，其实是展示页。

当前插件本身已经有比较成熟的 HTML 报告模板体系，不是从零开始：

- [`src/infrastructure/reporting/generators.py`](C:/Helianthus/SXP-Simon/astr/official/AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis/src/infrastructure/reporting/generators.py) 会在 `_prepare_render_data` 里生成 `titles_html`
- [`src/infrastructure/reporting/templates.py`](C:/Helianthus/SXP-Simon/astr/official/AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis/src/infrastructure/reporting/templates.py) 会按当前模板目录加载 Jinja2 模板
- 各模板目录下已经有独立的 `user_title_item.html` 片段，适合承载人格卡片

这意味着“人格标签结果”完全可以升级成“人格视觉卡片”，而不是停留在一行文字。

## 为什么前端展示很重要

`SBTI` 和 `ACGTI` 之所以传播强，不只是因为标签本身有趣，还因为它们普遍具备：

- 强主题色
- 明显的角色或原型形象
- 适合截图传播的结果页
- 清晰的层级结构：代码、人格名、短句、说明、扩展标签

如果本插件只输出：

- 称号
- 一个标签
- 一段理由

那可玩性会明显弱于参考项目。  
所以建议把“趣味人格标签”视为一个独立展示模块来设计。

## 推荐的前端展示结构

以每个群友的人格卡片为单位，建议拆成 4 层：

### 1. 核心识别层

- 用户头像
- 用户名
- 群内称号
- 人格标签代码或人格名

### 2. 视觉氛围层

这一层最值得补强。

建议支持：

- 人格主题色
- 人格背景纹理
- 人格装饰图层
- 人格角色形象图或原型图

对于你提到的“像 ACGTI / SBTI 那样的人物形象图作为装饰背景”，建议优先做成弱化背景视觉，而不是主内容图：

- 右下角半透明立绘
- 卡片边缘剪影
- 低透明度 emblem
- 主题色渐变叠加

这样能兼顾可读性和氛围感。

### 3. 描述信息层

不建议只有一条 `reason`，建议预留扩展字段。

推荐展示字段：

- `subtitle`
  一句副标题，例如“把场子点亮的人”
- `one_liner`
  一句 punchline
- `reason`
  基于群聊数据的命中说明
- `traits`
  2 到 4 个关键词标签
- `rarity`
  稀有度或趣味等级

### 4. 扩展信息层

适合高配 HTML 模板使用：

- `accent`
- `archetype`
- `match_score`
- `mood`
- `quote`
- `series`

## 前端实现切入点

当前最直接的切入点就是：

- 在 `_prepare_render_data` 里丰富 `title_data`
- 在各模板的 `user_title_item.html` 中消费新增字段

当前 `title_data` 只有：

- `name`
- `title`
- `mbti`
- `reason`
- `avatar_data`

建议后续扩展成：

```python
title_data = {
    "name": title.name,
    "title": title.title,
    "mbti": title.mbti,
    "reason": title.reason,
    "avatar_data": avatar_data,
    "label_system": "...",
    "label_name": "...",
    "label_code": "...",
    "subtitle": "...",
    "one_liner": "...",
    "traits": [...],
    "accent": "#7b6cff",
    "rarity": "SR",
    "background_image": "...",
    "overlay_image": "...",
}
```

这样模板就可以自由决定展示深度：

- 简版模板只显示 `label_code + reason`
- 炫酷模板显示 `overlay_image + accent + subtitle + traits`

## 人物形象图的接入建议

你提到希望展示 `ACGTI`、`SBTI` 相关的人物形象图作为装饰背景，这个方向是对的，但建议分成两种来源。

### 1. 原型图层

适用于通用人格体系。

例如：

- `发光主角位` 对应一张统一原型图
- `冰面观察者` 对应一张统一原型图
- `CTRL` 对应一张统一视觉卡面

优点：

- 可控
- 不依赖具体 IP
- 容易统一风格

### 2. 角色图层

适用于更强的二次元产品化路线。

例如：

- `发光主角位` 命中后再映射一个具体角色形象
- 或者给某个标签体系附带角色视觉配置

这个方向更接近 `ACGTI`，但也更重：

- 要维护图资源
- 要考虑版权和来源
- 要解决模板适配

所以更推荐：

- 第一版先做“原型图层”
- 后续再允许体系作者配置“角色图层”

## 视觉资源配置建议

为了不把前端写死，建议让视觉资源也进入配置。

例如每个标签可配置：

- `accent`
- `background`
- `overlay_image`
- `badge_style`
- `layout_variant`

示例数据：

```json
{
  "code": "CTRL",
  "name": "拿捏者",
  "subtitle": "方向感和控制力都很强",
  "accent": "#6a5cff",
  "background": "gradients/ctrl-purple-grid",
  "overlay_image": "personas/ctrl-figure.webp",
  "traits": ["推进型", "高控制感", "高响应"],
  "rarity": "SR"
}
```

然后模板层按这些字段决定：

- 背景渐变
- 装饰图位置
- 标签胶囊颜色
- 是否展示角标

## 推荐的展示形态

基于当前插件的 HTML 报告能力，最建议做这三种展示形态：

### 1. 卡片墙

对应当前 `群友风云榜`。

每个群友一张人格卡：

- 左上头像
- 右侧称号和人格标签
- 右下角半透明原型图
- 下方命中描述

这是最容易落地的形态。

### 2. 详情弹层或展开区

HTML 报告可以做 hover / 展开效果，显示：

- 人格副标题
- 关键词
- 趣味短句
- 详细原因
- 稀有度

这会让页面更像一个测试产品，而不是普通报表。

### 3. 顶部群人格 Hero

参考 `ACGTI` 的结果页，可以在整份 HTML 报告顶部增加一个 Hero 区：

- 今日群人格主题
- 一句副标题
- 一张大号背景图或原型图
- 今日 dominant archetype

这样会显著提升页面的产品感。

## 可扩展字段设计

如果未来想让这块不止支持 `SBTI / ACGTI / MBTI`，而是轻松变成“自定义类 MBTI 产品”，那么字段设计需要前置抽象。

建议把当前 `UserTitle` 的趣味人格部分理解成两层：

- 群友结果层
- 标签体系定义层

## 群友结果层

每个用户的结果建议至少支持：

- `title`
- `label_code`
- `label_name`
- `subtitle`
- `reason`
- `traits`
- `rarity`
- `accent`
- `visual_key`
- `extra`

其中 `extra` 用于体系自定义扩展。

## 标签体系定义层

建议每个体系文件包含：

- `system_id`
- `display_name`
- `theme`
- `fields`
- `labels`
- `visuals`
- `prompt_strategy`

这里最关键的是 `fields`。  
它决定“这个类 MBTI 产品想展示什么”。

示例：

```json
{
  "system_id": "acgti-lite",
  "display_name": "ACGTI Lite",
  "theme": {
    "card_style": "anime-archetype",
    "hero_layout": "character-cover"
  },
  "fields": [
    {"key": "label_code", "label": "原型代码", "type": "text"},
    {"key": "label_name", "label": "人格原型", "type": "text"},
    {"key": "subtitle", "label": "副标题", "type": "text"},
    {"key": "one_liner", "label": "一句话描述", "type": "text"},
    {"key": "traits", "label": "关键词", "type": "tag_list"},
    {"key": "rarity", "label": "稀有度", "type": "badge"}
  ]
}
```

这样前端模板就不需要知道“是不是 MBTI”，而是根据体系定义去渲染。

## 轻松配置自己的类 MBTI 产品

如果目标是让使用者自己扩展一个新的“类 MBTI 产品”，推荐把门槛压到“写数据，不改代码”。

理想方式是让用户只要提供：

1. 一个体系定义文件
2. 一个标签列表文件
3. 一组可选视觉资源
4. 一段 prompt 提示策略

就能新增一个玩法。

### 最小可配置单元

建议插件支持下面这种最小结构：

```text
data/persona_systems/
  my_fun_system/
    manifest.json
    labels.json
    visuals/
      hero.webp
      labels/
        label_a.webp
        label_b.webp
```

### `manifest.json` 建议包含

- 系统名称
- 系统描述
- 输出字段
- 默认模板风格
- prompt 拼装策略
- 是否允许开放生成

### `labels.json` 建议包含

- 标签 code
- 标签名
- 副标题
- 短句
- 关键词
- 命中提示
- 视觉 key
- 稀有度

### 这样做的意义

以后如果想做这些，都不用重写后端逻辑：

- 职场人格测试版
- 二次元原型版
- 抽象互联网人格版
- 游戏公会群专属人格版
- 某项目组内部黑话人格版

## 面向模板的扩展建议

为了让模板不反复重写，建议把展示分成三个层级：

### Level 1：通用字段

所有模板都能消费：

- 头像
- 名称
- 称号
- 标签
- 理由

### Level 2：增强字段

高级模板可以消费：

- 副标题
- 关键词
- 稀有度
- 一句话文案
- accent

### Level 3：视觉字段

炫酷模板专用：

- 背景图
- 原型图
- 装饰贴纸
- 角色立绘
- card style variant

这样模板作者可以按能力选择支持深度。

## 推荐的产品化方向

如果把这块当成长期玩法，我更建议把它产品化成：

“群聊人格宇宙生成器”

而不只是：

“给用户加一个 MBTI 字段”

因为后者很快会遇到上限，前者则可以持续扩：

- 换标签体系
- 换视觉风格
- 换展示字段
- 换 prompt 策略
- 换群体玩法

## 对当前插件最值得优先落地的前端点

如果只挑最值得做的几个点，我会建议优先级如下：

1. 把 `user_title_item.html` 里的 “MBTI” 文案统一升级为“人格标签”或按体系动态显示
2. 给每个人格卡新增 `subtitle / traits / rarity / accent`
3. 支持卡片背景装饰图或人格原型图
4. 在整份 HTML 报告顶部增加“今日群人格” Hero 区
5. 抽象出“体系定义 + 标签定义 + 视觉资源”的配置结构

这五步一旦落下去，这个功能就不再只是“趣味标签补丁”，而会开始接近真正可扩展的类 MBTI 产品平台。

## 推荐方案

## 方案 A：仅改 Prompt，最快上线

### 做法

- 不改 Python 结构
- 不改 schema
- 不改渲染模板
- 只修改 `user_title_prompt`
- 在 prompt 中明确告诉模型：
  - `mbti` 字段现在代表“人格标签结果”
  - 可以输出 `MBTI`、`SBTI`、`ACGTI` 风格标签
  - 优先输出更有趣、更贴合群聊气质的标签

### 优点

- 改动最小
- 几乎没有兼容成本
- 可以非常快验证用户是否买账

### 缺点

- 不可控，标签风格容易漂移
- 每次都靠 prompt 描述，复用性差
- 想新增体系时会让 prompt 越来越长

### 适合场景

- 想快速响应 Issue
- 想先做 A/B 试验
- 暂时不想引入额外数据文件

## 方案 B：配置化标签体系，推荐

这是我最推荐的落地方案。

### 目标

把“MBTI”升级为“可配置的人格标签体系”，但对现有调用链尽量保持兼容。

### 建议新增配置

可在 [`_conf_schema.json`](C:/Helianthus/SXP-Simon/astr/official/AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis/_conf_schema.json) 中新增一组配置，例如：

- `persona_label_system`
  可选值：`mbti`、`sbti-lite`、`acgti-lite`、`mixed`
- `persona_label_mode`
  可选值：`strict`、`prefer_fun`
- `persona_label_candidates`
  可选的候选标签列表，用于群定制
- `persona_label_show_name`
  控制前端/报告里显示为“MBTI”“人格标签”“赛博人格”等文案

### 建议新增数据资产

建议在插件内新增一个数据目录，例如：

- `data/persona_label_systems/mbti.json`
- `data/persona_label_systems/sbti_lite.json`
- `data/persona_label_systems/acgti_lite.json`

每个体系文件建议至少包含：

- `id`
- `display_name`
- `style`
- `description`
- `labels`

其中每个 `label` 可包含：

- `code`
- `name`
- `prompt_hint`
- `tone`
- `examples`
- `rarity`
- `extra_tags`

### Prompt 组织方式

不要把所有体系说明硬编码到一个超长 prompt 里，建议按以下思路拼装：

1. 通用任务说明
2. 当前启用的标签体系说明
3. 当前体系允许输出的标签候选
4. 用户统计数据
5. 返回 JSON 结构

这样可以明显减少 token 浪费，也方便继续扩。

### 兼容建议

为了不打断现有链路：

- 仍然返回 `mbti` 字段
- 但允许其值为 `INTJ`、`CTRL`、`发光主角位` 这类结果
- 如果想让报告里显示更自然，可以在渲染层把字段标题从“MBTI”改成更中性的“人格标签”

这个方案下，内部字段名还是 `mbti`，但对用户展示时不再强调“必须是 MBTI 类型”。

## 方案 C：体系注册表，适合后续演进

如果后续准备把这块做成插件特色玩法，建议再往前走一步，做成注册式体系。

### 可抽象的接口

每个标签体系都定义这些能力：

- `build_prompt_context`
- `allowed_labels`
- `display_name`
- `result_formatter`
- `extra_sections`

更轻一点的做法是不做 Python 类，而是做数据驱动注册表：

- 一个注册文件声明有哪些体系
- 一个体系文件声明 prompt 片段、候选标签、展示文案
- 通用分析器负责装载和拼 prompt

### 这样做的收益

- 后面新增一个人格体系基本只要补数据文件
- 不需要不断改主分析器
- 很适合做社区共创

## 接入建议

## 推荐的第一版产品行为

第一版不建议把它做成“严肃人格测试”，建议定义成：

“根据群聊行为特征，为活跃群友生成趣味人格标签和称号”

这样产品预期更稳定，也更适合现有输入数据。

### 推荐输出格式

保持现在的结构不变：

```json
[
  {
    "name": "用户名",
    "user_id": "123456",
    "title": "沉默终结者",
    "mbti": "CTRL",
    "reason": "经常开启话题并推动群聊节奏，控制感强。"
  }
]
```

这里的 `mbti` 实际就是“人格标签位”。

### 推荐的提示词原则

- 不追求心理学准确性
- 允许夸张和趣味化表达
- 必须基于群聊统计特征，不要完全瞎编
- 优先从有限候选中挑选，避免结果失控
- 当统计特征不明显时，允许回落到保守标签

## 与参考项目的映射建议

### `SBTI` 映射方式

适合做成“轻量趣味标签库”，不适合原样照搬完整测试流程。

建议做法：

- 选取 8 到 12 个辨识度高的 SBTI 标签做精简版
- 为每个标签写一条短描述和命中倾向
- 让模型基于统计特征做软匹配

示例：

- 高发言、高回复、高推进感 -> `CTRL` / `BOSS`
- 深夜活跃、低互动、高潜水回归 -> `ZZZZ`
- 高表情、高整活、高轻松内容 -> `JOKE-R` / `WOC!`

### `ACGTI` 映射方式

更适合借它的“原型层”思路，而不是直接输出具体角色。

建议做法：

- 先引入 `acgti-lite` 原型层
- 第一版只输出 8 个 archetype 风格标签
- 暂时不输出具体角色名，避免知识偏移和用户圈层门槛

示例：

- 高表达、高带头 -> `发光主角位`
- 高秩序、高责任 -> `誓约队长`
- 低表达、高观察 -> `冰面观察者`
- 高戏剧性、高整活 -> `混沌火花`

这类标签对大多数用户更友好，也更通用。

## 建议的实现拆分

## 第一阶段：低风险接入

目标：先把“支持趣味 MBTI 变体”做出来。

建议改动：

1. 调整 `user_title_prompt` 文案
2. 将“MBTI 类型”改写成“人格标签”
3. 在 prompt 中加入可选体系说明和候选标签示例
4. 若展示层有“MBTI”字样，统一改成更中性的文案

这一阶段可以不改数据模型。

## 第二阶段：配置化

目标：让运营或使用者可切换标签体系。

建议改动：

1. `_conf_schema.json` 增加 `persona_label_system`
2. `ConfigManager` 增加对应读取方法
3. `user_title_analyzer.py` 在构建 prompt 时注入当前体系上下文
4. 新增标签体系数据文件

这一阶段仍可保留 `mbti` 字段名。

## 第三阶段：完整扩展

目标：做成插件特色玩法。

建议改动：

1. 抽象标签体系注册表
2. 支持体系专属展示文案
3. 支持体系专属扩展字段
4. 为 HTML 模板增加标签体系样式区块
5. 加入群体级人格总结和彩蛋玩法

## 可以做的玩法扩展

除了“给每个人一个趣味标签”，还可以继续扩展：

### 1. 群整体人格

给整群一个标签，例如：

- “今日群像：混沌火花型技术吐槽局”
- “本群常驻人格：高压锅版 CTRL 群”

### 2. 今日人格漂移

对比最近几天，输出：

- 今天比昨天更 `BOSS`
- 最近一周从“冰面观察者”漂移到“混沌火花”

### 3. 相性/组合梗

识别群内典型组合：

- `CTRL + JOKE-R` 负责带节奏
- `月下守护者 + 温柔修复者` 负责接情绪

### 4. 彩蛋机制

参考 `SBTI` 的做法，可以做：

- 深夜消息比例极高触发隐藏标签
- 表情包占比极高触发表情彩蛋标签
- 某类高频群梗触发专属人格

### 5. 群专属标签体系

允许群主或管理员自定义：

- 标签名
- 标签简介
- 命中倾向
- 群内黑话

这会非常适合私域群、游戏群、项目群。

## Token 与效果平衡建议

Issue 里提到“没必要太精确，省点 token”，这一点非常合理。

建议控制方式：

- 单次只对 Top N 活跃用户做标签分析
- 每个体系只提供有限候选标签，不做开放生成
- 每个标签说明尽量控制在一两句话
- 不做复杂问卷，不新增多轮交互
- 需要时优先用统计特征做硬约束，再让 LLM 写 `reason`

简单说：

- “让模型选标签”比“让模型创造体系”更省
- “给有限候选列表”比“完全开放生成”更稳

## 风险与注意事项

### 1. 字段名风险

内部字段目前就是 `mbti`。  
如果急着改字段名，会牵涉：

- 数据模型
- schema
- 校验
- 正则提取
- 报告渲染

所以建议先保留。

### 2. 标签漂移风险

如果候选不收敛，模型会出现：

- 一会儿输出 MBTI
- 一会儿输出二次元原型
- 一会儿输出自己瞎造的标签

所以一定要给“当前体系允许输出的候选列表”。

### 3. 圈层门槛风险

像 `ACGTI` 具体角色名虽然好玩，但不是所有群都懂。  
因此第一版建议输出“原型标签”，不要直接输出角色名。

### 4. 解释过拟合风险

当前输入数据主要是：

- 发言数
- 平均字数
- 表情比例
- 夜间比例
- 回复比例

这些特征足够做趣味标签，但不足以支撑太细的人格论断。  
所以文案风格要保持“娱乐化、观察式”，不要写得像心理测评结论。

## 推荐落地顺序

如果目标是“先把 Issue 做漂亮”，推荐这样排：

1. 先做 `方案 A`，验证用户接受度
2. 很快补成 `方案 B`，把体系切换能力做出来
3. 有反馈后再考虑 `SBTI` 彩蛋、`ACGTI` 原型层、群整体人格等玩法

## 最终建议

这次需求最合适的方向，不是“新增一个 MBTI 功能”，而是：

“把用户称号分析升级成可扩展的趣味人格标签系统”

其中：

- `SBTI` 适合提供“标签库、文案库、彩蛋感”
- `ACGTI` 适合提供“分层抽象、原型扩展、数据驱动”
- 当前插件非常适合从 `user_title_analysis` 这一层切入

如果只做一版最划算的实现，我建议：

- 保留 `mbti` 字段
- 新增 `persona_label_system` 配置
- 提供 `mbti`、`sbti-lite`、`acgti-lite` 三种体系
- 报告展示文案统一改成“人格标签”

这样能用很小的改动，把后续扩展空间直接打开。
