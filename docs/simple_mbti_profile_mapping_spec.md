# MBTI 三模式角色映射规范

## 结论先行

这次需求的本质不是改分析逻辑，而是改展示逻辑。

第一版建议这样做：

1. 保留现有 `MBTI` 分析链路
2. 不修改分析区提示词
3. 不新增复杂人格推断
4. 只在渲染阶段，根据当前选择的模式，把 `MBTI` 映射成对应主题的角色图和中文标签

也就是说：

- LLM 继续输出 `mbti`
- 插件渲染前根据模式做一次查表
- 把对应图片、中文名、缩写一起塞到群友画像卡片里

这是最稳、最省改动、也最符合当前插件结构的方案。

## 产品行为定义

建议把原本单一的 `MBTI` 展示拆成三个模式：

- `mbti`
- `sbti`
- `acgti`

这三个模式只影响“展示映射”和“背景图呈现”，不影响 LLM 分析本身。

## 三种模式的定义

### 1. `mbti` 模式

直接展示原始 MBTI。

例如：

- `INFP`
- `ENTJ`

可选显示文案：

- `INFP`
- `INFP（调停者）`

这一模式下不强制使用角色图，可以留空，或者允许用户自行配置一张通用背景图。

### 2. `sbti` 模式

先拿现有 `MBTI`，再查一张 `MBTI -> SBTI` 的朴素映射表。

例如：

- `INTJ -> CTRL（拿捏者）`
- `INFP -> SOLO（孤儿）`
- `ENTP -> JOKE-R（小丑）`

展示时不要只显示缩写，建议统一使用：

- `CTRL（拿捏者）`
- `SOLO（孤儿）`
- `JOKE-R（小丑）`

### 3. `acgti` 模式

先拿现有 `MBTI`，再查 `MBTI -> ACGTI 角色`。

例如：

- `INFP -> BCHI（后藤一里）`
- `INTP -> KNAN（江户川柯南）`
- `ENTJ -> SAKI（丰川祥子）`

展示时同样不要只显示缩写，建议统一使用：

- `BCHI（后藤一里）`
- `KNAN（江户川柯南）`
- `SAKI（丰川祥子）`

## 关键原则

### 1. 不改提示词

这一版明确不改：

- `user_title_prompt`
- 其他分析 prompt
- 分析 schema

原因很简单：

- 当前链路已经能稳定输出 `mbti`
- 需求只是“换主题展示”
- 如果为了展示层去改分析 prompt，收益很低，风险反而上升

所以第一版只做展示映射。

### 2. 中文必须跟着缩写一起展示

`SBTI` 和 `ACGTI` 的缩写对普通用户不友好。  
因此建议统一采用：

- `缩写（中文名）`

例如：

- `CTRL（拿捏者）`
- `THIN-K（思考者）`
- `BCHI（后藤一里）`
- `FRNA（芙宁娜）`

不要只显示：

- `CTRL`
- `BCHI`

否则用户几乎看不懂。

### 3. 图片只做底层淡淡显示

考虑到当前模板很多已经成型，不适合大改布局，建议角色图只做背景装饰层。

推荐效果：

- 右下角淡化立绘
- 卡片底层低透明度剪影
- 遮罩后只保留 8% 到 18% 可见度
- 永远不压住正文

不要做：

- 大图占满卡片
- 直接盖在文字上
- 高饱和实底遮挡

## 最适合当前插件的实现方式

当前插件最适合的实现点不是分析器，而是渲染器。

直接在 [`src/infrastructure/reporting/generators.py`](C:/Helianthus/SXP-Simon/astr/official/AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis/src/infrastructure/reporting/generators.py) 的 `_prepare_render_data` 阶段，把 `title_data` 扩展一下即可。

当前已经有：

```python
title_data = {
    "name": title.name,
    "title": title.title,
    "mbti": title.mbti,
    "reason": title.reason,
    "avatar_data": avatar_data,
}
```

建议扩成：

```python
title_data = {
    "name": title.name,
    "title": title.title,
    "mbti": title.mbti,
    "reason": title.reason,
    "avatar_data": avatar_data,
    "profile_mode": "mbti",
    "profile_display": "INFP（调停者）",
    "profile_image": "https://...",
    "profile_image_opacity": 0.12,
    "profile_code": "INFP",
    "profile_name_zh": "调停者",
}
```

或者在 `sbti` / `acgti` 模式下：

```python
title_data = {
    ...
    "profile_mode": "sbti",
    "profile_display": "SOLO（孤儿）",
    "profile_image": "https://...",
    "profile_image_opacity": 0.12,
    "profile_code": "SOLO",
    "profile_name_zh": "孤儿",
}
```

## 三模式的简单映射表

下面这张表就是第一版最够用的范式。

| MBTI | SBTI | SBTI中文 | ACGTI | ACGTI中文 |
|------|------|----------|-------|-----------|
| INTJ | CTRL | 拿捏者 | MRTS-X | Mortis |
| INTP | THIN-K | 思考者 | KNAN | 江户川柯南 |
| ENTJ | BOSS | 领导者 | SAKI | 丰川祥子 |
| ENTP | JOKE-R | 小丑 | CHKA | 藤原千花 |
| INFJ | LOVE-R | 多情者 | DLRS | 三角初华 |
| INFP | SOLO | 孤儿 | BCHI | 后藤一里 |
| ENFJ | THAN-K | 感恩者 | YCYO | 月见八千代 |
| ENFP | GOGO | 行者 | HTMK | 初音未来 |
| ISTJ | OH-NO | 哦不人 | MRTS | 若叶睦 |
| ISTP | POOR | 贫困者 | AYRE | 绫波丽 |
| ESTJ | SHIT | 愤世者 | MIKT | 御坂美琴 |
| ESTP | WOC! | 握草人 | ASKA | 明日香 |
| ISFJ | MUM | 妈妈 | SOYO | 长崎爽世 |
| ISFP | MALO | 吗喽 | LTYI | 洛天依 |
| ESFJ | ATM-er | 送钱者 | ANON | 千早爱音 |
| ESFP | SEXY | 尤物 | FRNA | 芙宁娜 |

说明：

- `ACGTI` 基本直接使用其 `characters.json` 中的 `matchCode`
- `SBTI` 没有现成 MBTI 对照，这里采用产品化朴素映射

## 推荐的资源组织方式

不要直接把参考仓库路径写死在业务里。  
建议统一在插件自己的目录中组织资源。

例如：

```text
data/profile_assets/
  sbti/
    CTRL.png
    THIN-K.png
    SOLO.png
  acgti/
    BCHI.png
    KNAN.png
    HTMK.png
  mbti/
    INFP.png
    ENTJ.png
```

如果你不想把图片打包进插件，也可以完全用外链。

重点是：插件只消费配置里的图片地址，不负责图片可访问性。

也就是说：

- 插件不保证 URL 有效
- 插件不代理图片
- 插件不检查 CDN 稳定性
- 用户自行维护图片可用性

## 推荐的配置方式

考虑到 AstrBot 插件配置的使用习惯，建议不要让用户去改复杂 JSON 文件路径嵌套。

第一版更适合：

1. `_conf_schema.json` 里新增几个简单配置项
2. 再加一个可编辑的 JSON 文本配置项

## 建议新增配置项

### 1. 展示模式

```json
"profile_display_mode": {
  "type": "string",
  "description": "人格展示模式",
  "options": ["mbti", "sbti", "acgti"],
  "default": "mbti",
  "hint": "只影响群友画像卡片的角色主题展示，不影响实际 MBTI 分析结果。"
}
```

### 2. 图片透明度

```json
"profile_image_opacity": {
  "type": "float",
  "description": "人格背景图透明度",
  "default": 0.12,
  "hint": "建议 0.08 ~ 0.18，仅作为卡片底层装饰，避免遮挡正文。"
}
```

### 4. 人格映射配置

这个配置项建议直接给用户一个可编辑文本框。

```json
"profile_mapping_config": {
  "type": "text",
  "description": "人格映射配置(JSON)",
  "editor_mode": true,
  "editor_language": "json",
  "default": "{ ... }",
  "hint": "按 MBTI 映射到当前展示模式的人格名称与图片地址。插件不负责校验图片链接可访问性。"
}
```

这样非常符合 AstrBot 插件当前配置编辑习惯：

- 简单开关和枚举用普通字段
- 稍复杂结构用 JSON 文本编辑

不需要用户去改仓库文件，也不需要特别麻烦的路径维护。

## 推荐的映射配置范式

建议把最终配置压成一个容易编辑的结构。

例如：

```json
{
  "mbti": {
    "INFP": {
      "code": "INFP",
      "name_zh": "调停者",
      "display": "INFP（调停者）",
      "image": "https://example.com/mbti/INFP.png"
    }
  },
  "sbti": {
    "INFP": {
      "code": "SOLO",
      "name_zh": "孤儿",
      "display": "SOLO（孤儿）",
      "image": "https://example.com/sbti/SOLO.png"
    }
  },
  "acgti": {
    "INFP": {
      "code": "BCHI",
      "name_zh": "后藤一里",
      "display": "BCHI（后藤一里）",
      "image": "https://example.com/acgti/BCHI.png"
    }
  }
}
```

这份结构有几个好处：

- 用户不需要理解 `systems`、`items`、`asset_base` 这类抽象概念
- 直接按当前模式查 `mode -> mbti`
- 修改图片地址最直观
- 修改中文标注也最直观

## 最简单的查表逻辑

伪代码如下：

```python
mode = config_manager.get_profile_display_mode()
mapping_config = config_manager.get_profile_mapping_config()

mbti = (title.mbti or "").strip().upper()
profile_info = mapping_config.get(mode, {}).get(mbti, {})

title_data["profile_mode"] = mode
title_data["profile_code"] = profile_info.get("code", mbti)
title_data["profile_name_zh"] = profile_info.get("name_zh", "")
title_data["profile_display"] = profile_info.get(
    "display",
    f"{title_data['profile_code']}（{title_data['profile_name_zh']}）"
    if profile_info.get("name_zh")
    else title_data["profile_code"],
)
title_data["profile_image"] = profile_info.get("image", "")
title_data["profile_image_opacity"] = config_manager.get_profile_image_opacity()
title_data["profile_image_size_mode"] = config_manager.get_profile_image_size_mode()
```

## 模板呈现建议

当前模板不适合大改，所以建议只做轻微增强。

### 必做项

- 在卡片中显示 `profile_display`
- 也就是：
  - `INFP（调停者）`
  - `SOLO（孤儿）`
  - `BCHI（后藤一里）`

### 选做项

- 如果 `profile_image` 存在，就作为卡片底层背景图
- 使用绝对定位
- 透明度由配置控制
- 默认放右下角

### 推荐 CSS 策略

```css
.profile-overlay {
  position: absolute;
  right: 8px;
  bottom: 8px;
  width: 40%;
  height: 70%;
  object-fit: contain;
  opacity: 0.12;
  pointer-events: none;
  filter: saturate(0.9) contrast(1.02);
}
```

建议再加一个浅遮罩，保证文字可读。

## 不建议做的事情

为了保持简单，第一版不建议：

- 改分析提示词
- 改 `mbti` 字段语义
- 引入复杂前端交互
- 做随机抽卡式角色匹配
- 一次同时显示 `MBTI + SBTI + ACGTI` 三套大块内容

第一版就做“单模式切换显示”最合理。

## 最终建议

如果把这次需求收敛成一句话，就是：

“现有 MBTI 结果不变，只新增三种主题展示模式，在群友画像卡片中用中文补全后的标签和淡化角色底图进行呈现。”

对应实现策略就是：

1. 不改 prompt
2. 不改分析结果结构
3. 配置里新增一个模式开关
4. 配置里新增一个易编辑的映射 JSON
5. 模板里只增加一个淡化背景图层和一个新的显示字段

这就是当前插件里最轻量、最稳、最容易扩展的做法。
