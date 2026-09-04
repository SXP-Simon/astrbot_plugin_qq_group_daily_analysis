# 报告视觉模板开发指南（Report Template Guide）

本指南面向想要为「群聊日常分析」插件贡献或自建**报告视觉模板**的作者。

模板 = 一组 Jinja2 HTML 文件，用于把分析结果（统计、话题、群友画像、金句、活跃图等）
渲染成长图海报（`image` 格式）或可交互网页（`html` 格式）。

---

## 1. 模板的两种形态

| 形态 | 位置 | 说明 |
| --- | --- | --- |
| **内置模板** | 插件目录 `src/infrastructure/reporting/templates/<模板名>/` | 随插件分发，跟随版本升级 |
| **自定义模板** | 插件数据目录 `data/plugin_data/astrbot_plugin_qq_group_daily_analysis/custom_t2i_templates/reporting_templates/<模板名>/` | 用户通过 WebUI「安装模板」在线安装，或手动放入 |

两条路径**按模板名共同作用于渲染**：同名的自定义目录优先于内置目录
（用于“覆盖修改内置模板”），同名内置模板没有的局部文件会向自定义目录回退后再回退
默认手账模板（详见 §4）。模板放入后**无需重启机器人**，
在「断点续跑」「免 Token 切换主题重绘」及 `/查看模板` 中即时可见。

> 安装以自定义形态落到数据目录，**升级插件不会被删除**（插件本体在
> `data/plugins/`，与数据目录分离）。

## 2. 模板目录结构（完整 7 件套）

```
<模板名>/
├── image_template.html    ★ 长图海报主骨架（必选其一）
├── html_template.html     ★ 独立网页报告主骨架（必选其一）
├── topic_item.html          话题总结列表模块
├── user_title_item.html     群友称号与画像模块
├── quote_item.html          群友金句与锐评模块
├── activity_chart.html      24 小时活跃轨迹模块
├── chat_quality_item.html   群聊质量多维锐评模块
├── shared_styles.html       可选：全局共享样式片段（参考 hack/）
├── inline_assets.html       可选：内联资源与装饰（参考 HatsuneMiku/）
└── template.json            可选：模板显示名 {"name": "中文名", "desc": "说明"}
```

只需提供 `image_template.html` 或 `html_template.html` 任一即可被识别，
缺失的子模块自动回退到内置 `scrapbook` 模板的对应文件（§4）。

各模板目录的 **HTML 文件名与 Jinja2 变量契约完全相同**（第 3 节），
内置模板之间可以直接复制改色改版。

## 3. 渲染变量契约

### 3.1 主骨架（`image_template.html` / `html_template.html`）

| 变量 | 类型 | 说明 |
| --- | --- | --- |
| `topics_html` | str | 话题列表 HTML 片段（由 `topic_item.html` 渲染） |
| `titles_html` | str | 群友称号/画像 HTML 片段 |
| `quotes_html` | str | 金句锐评 HTML 片段 |
| `hourly_chart_html` | str | 24h 活跃图表 HTML 片段 |
| `chat_quality_html` | str | 聊天质量锐评 HTML 片段（无数据时为空串） |
| `message_count` | int | 消息总数 |
| `participant_count` | int | 参与人数 |
| `total_characters` | int | 总字符数 |
| `emoji_count` | int | 表情数 |
| `most_active_period` | str | 最活跃时段描述 |
| `current_date` | str | 报告日期（`2026年08月01日` 格式） |
| `current_datetime` | str | 精确时间戳 |
| `total_tokens` / `prompt_tokens` / `completion_tokens` | int | Token 消耗统计（未消耗为 0） |
| `hide_user_names` | bool | 是否隐藏真实昵称（隐私模式） |
| `t2i_font_source` / `t2i_google_fonts_mirror` / `t2i_gstatic_mirror` / `t2i_atri_font_mirror` | str | 字体来源与镜像配置，模板内引字体时应使用 |

主骨架通过 `{% include %}` 或类 CSS 方式组合 5 个 `*_html` 片段为整体画面。
参考内置 `scrapbook/` 实现（结构最经典）。

### 3.2 子模块变量

| 模板文件 | 变量名 | 元素结构 |
| --- | --- | --- |
| `topic_item.html` | `topics` | `[{index, topic: {topic}, contributors, detail}]`；`detail` 内联了头像与系统自动加的可见用户 @ 引用 |
| `user_title_item.html` | `titles` | `[{name, title, mbti, reason, avatar_data, ...profile_info}]`（profile 随显示模式附加字段） |
| `quote_item.html` | `quotes` | `[{content, sender, reason, avatar_url}]` |
| `activity_chart.html` | `chart_data` | `[{hour: 0-23, count, percentage}]`（percentage 为相对峰值的百分比，保留 1 位小数） |
| `chat_quality_item.html` | 直接展开 | `title`、`subtitle`、`summary`、`dimensions: [{name, percentage, comment, color}]` |

所有子模块还会收到 `hide_user_names` 与 `t2i_*` 字体配置（同 3.1 表）。

### 3.3 通用约定

- 渲染引擎为 Jinja2（autoescape 开启、`trim_blocks`/`lstrip_blocks` 开启）。
- 变量中凡是**可能展示用户输入**的字段（话题、金句、锐评、昵称等），
  渲染前已由 `generators.py` 做身份脱敏/转义，模板**不要自行进行 HTML 拼接二次转义**。
- 头像通过 `avatar_url` / `avatar_data` 传入，模板直接按 URL 使用。

## 4. 渲染与回退机制

模板加载是一个「多层优先、逐层回退」的 Jinja2 `ChoiceLoader` 链：

```text
1. 自定义模板目录（用户在线安装 / 手动放入）
2. 内置模板目录（<模板名>/）
3. scrapbook（默认手账，永远作为最底层兜底）
```

因此：

- **全新自定义模板**：各文件取自自定义目录，缺失的任意文件从 `scrapbook` 兜底；
- **覆盖内置模板**：只在自定义目录放想要替换的单个文件（如仅 `image_template.html`），
  其余文件自动使用内置同名模板内容；
- **HTML 输出**：优先加载 `html_template.html`，不存在或渲染失败时回退 `image_template.html`。

> 若配置的模板名不存在于任何一层，渲染会以 `scrapbook` 兜底并记录警告日志。

## 5. 资源与预览图

### 5.1 预览图

- 插件仓库 `assets/<模板名>-demo.jpg`（本地优先，回退仓库图库链接）；
- **随模板打包**：模板目录内的 `preview.jpg/png` 或 `demo.jpg/png`
  （经安装器装入数据目录后，QQ `/查看模板` 优先显示；见 §6.5）。

### 5.2 模板内部引用的图片（重要：渲染链路约束）

报告 HTML 是**字符串**形式交给 AstrBot 的 T2I 渲染服务（远程 API / 本地 Shiki 运行时），
渲染端**没有模板文件的文件系统上下文**。因此：

| 引用方式 | 是否可用 |
| --- | --- |
| 绝对 URL（https://… 的公开图库链接） | ✅ 可用；必须长期稳定，不要用会失效的临时链接 |
| 内联 `data:image/...;base64,` | ✅ 可用；自包含无网络依赖，小图/纯装饰推荐 |
| 相对路径（`src="assets/bg.png"`） | ❌ 渲染时必然 404（远程渲染端无法解析相对路径） |

参考实现：`HatsuneMiku/` 的装饰图全部以仓库图库链接（绝对 URL）引用。

**选择建议**（按资源大小）：

| 场景 | 推荐方式 | 原因 |
| --- | --- | --- |
| 小图标/贴纸（<50KB） | base64 `data:` URI 或内联 `<svg>` | 自包含、离线可用、零外部依赖 |
| 大装饰图（背景/立绘） | 仓库图库绝对 URL（Miku 式） | base64 膨胀 33% 且每次渲染都整串携带；CDN 有缓存、换图不换链接 |
| 矢量装饰 | 内联 `<svg>` | 零体积零请求 |

> 这些约束只影响**报告渲染**；`preview.jpg`（/查看模板 预览）与 WebUI 画廊
> 图片走本地文件读取路径，打包目录内的图片可正常使用。

## 6. 打包与在线安装

### 6.1 命名建议

- 建议使用**小写英文蛇形**并带命名空间前缀（如 `gda_miku_dream`），
  仅含小写字母、数字、下划线，长度不超过 50；
- 避免空格与特殊字符——模板名会进入报告文件名（`report_<群号>_<时间>_<模板名>.jpg`）、
  预览图文件名与链接；
- 与内置模板（`scrapbook` 等）同名会导致与内置模板合并，**安装时会被拒绝**。

### 6.2 zip 打包要求

| 要求 | 说明 |
| --- | --- |
| 单个模板 | 一个 zip 只装一个模板；包含多个模板根目录会被拒绝 |
| 主文件 | 根目录下必须有 `image_template.html` 或 `html_template.html` |
| 根目录 | 允许外层套一层目录（GitHub 归档的 `repo-main` 形式自动剥离该层） |
| 大小 | 解压后总量 ≤ 64MB、单文件 ≤ 20MB、成员 ≤ 300 个（防压缩炸弹） |
| 安全 | 路径穿越（`../`、绝对路径）会被拒绝 |

### 6.3 安装途径

- **WebUI 安装**：配置页「安装模板」→
  - GitHub 链接：`https://github.com/<owner>/<repo>`（可带 `/tree/<分支>`），填写后自动下载源码 ZIP 安装；
  - 上传 zip：直接拖入打包好的模板 zip。
  - 两个入口均支持手动指定模板名（留空时从仓库名/zip 根目录名推断，`-main`/`-master` 后缀自动去除）。
- **手动放置**：把模板文件夹放入
  `data/plugin_data/astrbot_plugin_qq_group_daily_analysis/custom_t2i_templates/reporting_templates/<模板名>/`。

### 6.4 展示元信息（template.json）

**文件位置**：模板**根目录**下的 `template.json`（与 `image_template.html` 同级），
内置模板目录、自定义模板目录、zip 打包时均相同：

```text
<模板名>/
├── template.json        ← 本文件（可选）
├── image_template.html
├── html_template.html   （可选）
├── topic_item.html      （可选）
├── preview.jpg          （可选，见 §6.5）
└── ...
```

**最小可选示例**（仅需 `name`，其余字段可省）：

```json
{
  "name": "樱雨日记"
}
```

**完整示例**（全部字段）：

```json
{
  "name": "樱雨日记",
  "desc": "樱花与水彩风格的日记手账",
  "tag": "水彩樱花",
  "tag_color": "pink"
}
```

| 字段 | 必填 | 用途 |
| --- | --- | --- |
| `name` | 可选 | WebUI 下拉/列表中的显示名；缺省时直接使用模板目录名 |
| `desc` | 可选 | WebUI 下拉悬停提示与卸载列表中的描述 |
| `tag` | 可选 | WebUI 下拉中的风格标签（`名称 [标签]` 形式展示） |
| `tag_color` | 可选 | 标签配色（antd Tag 颜色名：`default/blue/green/cyan/pink/purple/red/orange/lime/geekblue`） |

> 全部字段均为字符串，长度上限 100 字符，多余部分自动截断；
> 文件缺失、JSON 解析失败或字段为空时自动忽略，模板依旧可用。
> 仅支持 JSON（不接受 YAML）。

### 6.5 预览图（随模板打包）

在模板目录内放 `preview.jpg`（或 `preview.png` / `demo.jpg` / `demo.png`），
大小需 ≤ 3MB（防止超大图片造成内存与网络带宽消耗）。
随 zip 一起安装后，QQ `/查看模板` 与 WebUI 画廊会优先显示该图（其次查找插件仓库
`assets/<模板名>-demo.jpg`，最后回退仓库图库链接）。

```text
<模板名>/
├── preview.jpg      ← 可选：/查看模板 使用的预览图
├── image_template.html
└── ...
```

## 7. 卸载

- WebUI「卸载模板」只列出**通过安装器下载**的模板；
- 安装器会在模板目录写入标记 `.tpl_installed.json`，卸载仅删除带标记的目录；
- **内置模板不可卸载**；手动放入或由插件自动备份的目录（无标记）也不允许
  自动卸载，需手动删除文件；
- 卸载成功后，若该模板当前是正在使用的报告模板，渲染自动回退默认手账风格。

## 8. 本地调试

```bash
# 渲染指定模板为 HTML，浏览器直接打开查看效果（无需真实运行机器人/LLM）
python scripts/debug_render.py -t <模板名> -o debug_output.html [-m mbti|sbti|acgti]
```

## 9. 安全须知

- **仅安装可信来源的模板**：安装器不执行模板代码，但模板会在**渲染服务端**
  （AstrBot T2I，可能是远程 y 服务或本机 Shiki 运行时）以完整 HTML 打开，
  恶意模板可在渲染环境发起网络请求/消耗资源。请像对待普通软件一样对待模板来源。
- **Jinja 渲染已启用沙箱**（`SandboxedEnvironment`）：模板无法访问
  `__class__`/`__subclasses__` 等 dunder 属性（SSTI 防护），但这**不限制**模板
  在 HTML 输出中引用任意 URL/资源。
- **命名校验**：模板名禁止路径分隔符与危险字符，安装/卸载/预览接口均有
  路径穿越防护；GitHub 分支名仅允许 `[A-Za-z0-9._-]`。
- **上传/下载限额**：zip 解压后总量 ≤ 64MB、单文件 ≤ 20MB、成员 ≤ 300、
  下载体 ≤ 64MB（流式限制），防止资源耗尽。

## 10. 贡献为内置模板时的改动清单（仅贡献者）

除模板目录外，还需要修改（参照已有主题的注册方式）：

| 文件 | 改动 |
| --- | --- |
| `src/infrastructure/reporting/templates.py` | `KNOWN_TEMPLATE_NAMES` 增加 `"<模板名>": "中文名"` |
| `_conf_schema.json` | `report_template.options` 数组追加模板名（WebUI 配置下拉） |
| `dashboard/src/entities/report/model/templates.ts` | `KNOWN_TEMPLATES`（画廊信息：名称/描述/标签/标签色）与 `DEFAULT_REPORT_TEMPLATES`（兜底列表） |
| `assets/<模板名>-demo.jpg` | 预览图（仓库展示与图库链接） |
| `README.md` / `CHANGELOG.md` | 模板展示与更新记录 |

前端改动后需重新构建 dashboard：`cd dashboard && pnpm install && pnpm build`
（产物输出到 `pages/daily-analysis/`，随包发布的就是该产物）。
