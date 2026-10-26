# 报告视觉模板开发指南（Report Template Guide）

本指南面向想要为「群聊日常分析」插件贡献或自建**报告视觉模板**的作者。

模板 = 一组 Jinja2 HTML 文件，用于把分析结果（统计、话题、群友画像、金句、活跃图等）
渲染成长图海报（`image` 格式）或可交互网页（`html` 格式）。

---

## 1. 模板的两种形态

| 形态 | 位置 | 说明 |
| --- | --- | --- |
| **内置模板** | 插件目录 `src/infrastructure/reporting/templates/<模板名>/` | 随插件分发，跟随版本升级统一维护 |
| **自定义模板** | 插件数据目录 `data/plugin_data/astrbot_plugin_qq_group_daily_analysis/custom_t2i_templates/reporting_templates/<模板名>/` | 用户通过 WebUI「安装模板」在线安装，或手动放入独立主题目录 |

官方内置模板始终优先由源码统一提供并渲染，自定义模板用于承载第三方独立主题；自定义主题若未提供完整子组件，会自动向默认手账模板（`scrapbook`）优雅兜底（详见 §4）。模板放入后**无需重启机器人**，在「断点续跑」「免 Token 切换主题重绘」及 `/查看模板` 中即时可见。

> 安装以自定义形态落到数据目录，**升级插件不会被删除**（插件本体在
> `data/plugins/`，与数据目录分离）。
>
> 💡 **参考示例仓库**：可参考社区标准示例模板 [lingyun14beta/daily-analysis-report-theme](https://github.com/lingyun14beta/daily-analysis-report-theme) 学习目录结构、`template.json` 配置与打包规范。

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
| `t2i_font_source` / `t2i_google_fonts_mirror` / `t2i_gstatic_mirror` / `t2i_atri_font_mirror` | str | 当前方案的资源环境与字体镜像，模板内引字体时应使用 |

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

> 若配置或指定的模板名在自定义和内置目录中均不存在，渲染引擎会明确提示未找到指定的报告主题模板，而不会静默替换。

## 5. 资源与预览图

### 5.1 预览图

- 插件仓库 `assets/<模板名>-demo.jpg`（本地优先，回退仓库图库链接）；
- **随模板打包**：模板目录内的 `preview.jpg/png` 或 `demo.jpg/png`
  （经安装器装入数据目录后，QQ `/查看模板` 优先显示；见 §6.5）。

### 5.2 模板内部引用的图片（重要：渲染链路约束）

在「图片渲染策略 → 图片渲染方案」中，插件 WebUI 点击「添加渲染方案」，AstrBot 配置页点击「添加条目」，选择内地或海外预设。两种预设提供配套的 Google Fonts 和 Gstatic 地址，CDN 沿用插件原默认地址；可在条目内分别修改本轮的 `cdn_base_url`、`google_fonts`、`gstatic`。CDN 需支持 `/gh/` 和 `/npm/` 路径，首尾空格和末尾 `/` 会在保存时整理；字体地址也支持反向代理路径前缀。

每轮的资源地址与截图服务独立配置。可以先尝试 CDN A，再尝试 CDN B，也可以只更换字体镜像。地址发生变化时会重新准备主模板和所有组件，不修改全局配置，也不重复调用大模型。用户自定义图片与明确指定的 ATRI 镜像保持原地址。

方案按优先级稳定排序，数值越小越先尝试，成功后停止。进入渲染队列后，资源准备与各轮截图共用五分钟总等待上限；停止任务或总超时后不再进入下一轮。

每个方案还可选择截图服务：

- **跟随 AstrBot（默认）**：沿用本群绑定配置中的 T2I 地址，继续兼容旧版宿主回调。
- **自定义 T2I 服务**：填写根地址、`/text2img` 基础地址或完整 `/text2img/generate` 地址；首尾空白及末尾斜杠会整理，完整生成接口会转成基础地址。反向代理的路径前缀会保留。服务需要鉴权时填写可选 Bearer Token，地址中不接受账号密码、查询参数或片段。

资源地址与截图服务分别选择，例如第一项使用自定义本地服务和海外字体，第二项跟随 AstrBot 并使用另一套 CDN 和字体。服务失败继续原有优先级回退，不重新分析消息。自定义模式直接通过 HTTP(S) 连接，不读取环境代理；只影响本插件本轮报告，不修改 AstrBot 全局地址、普通回复转图开关或其他群聊的配置。

自定义客户端按官方协议提交 `html`、`json: false` 和截图 `options`，读取 PNG/JPEG 字节，不依赖第三方插件的 Python 类或临时图片目录。自定义响应采用流式读取，图片最多接收 32 MiB，并检查完整性和实际解码；损坏或过大的图片会进入后续方案。错误响应只读取有限样本；配置了 Token 时不回显服务错误正文，详情请查看服务日志。请求超时按本轮毫秒值执行，并受现有五分钟总上限约束。分析记录保留成功、失败和已停止的轮次，自定义服务地址只显示协议、主机和端口，不显示路径；独立 HTML 导出与预览不调用截图服务。

HTTP 保留对本机、Docker 和可信内网部署的支持；跨网络连接建议配置 HTTPS，以免报告内容和 Token 明文传输。只填写自己信任的服务地址。

WebUI 保存时会校验读取配置时的内容版本。如果其他页面或 AstrBot 管理界面已经修改配置，会拒绝旧快照并保留当前未保存的草稿。请先留存需要的修改，再重新读取配置；旧版调用方不带版本字段时仍沿用原保存方式。

[astrbot_plugin_t2i_service](https://github.com/XTsat/astrbot_plugin_t2i_service) 默认可在 `http://127.0.0.1:8999/text2img` 提供兼容服务。使用本插件的自定义模式时，无需开启对方的“自动写入 AstrBot 文转图端点”，也无需为此打开所有普通回复自动转图。如果希望请求始终由本机处理，请同时检查对方的远程转发开关：本地浏览器不可用时，它可以自行转发到备用公共服务。选择本地服务并不意味着模板中的外链图片和字体也已缓存到本地。

例如先添加优先级 10 的内地 PNG 方案，再添加优先级 20 的海外 JPEG 方案；两轮地址都可自行修改。第一项返回错误、空内容或非图片数据时才继续第二项。正常返回的图片中缺少个别外链素材，目前无法据此触发自动切换。独立 HTML 导出不调用 T2I，使用第一优先级方案的资源地址；图片接口返回的 HTML 则与本次实际生成并用于截图的内容一致。模板预览也采用第一优先级方案的 CDN。

配置入口对应关系：

| 原配置 | 新配置 |
| --- | --- |
| `t2i_r1_*`、`t2i_r2_*` | `t2i_rendering_strategies` 方案列表中的格式、质量、分辨率和超时 |
| 全局 `t2i_font_source` | 添加内地或海外预设，再修改本轮资源地址 |
| 全局及环境级 CDN | 每个方案的 `cdn_base_url` |
| `t2i_mainland_google_fonts` / `t2i_overseas_google_fonts` | 每个方案的 `google_fonts` |
| `t2i_mainland_gstatic` / `t2i_overseas_gstatic` | 每个方案的 `gstatic` |

原固定两轮字段和全局资源环境已移除，不再读取。初始配置提供一项默认方案：名称“默认方案”、优先级 10、`Overseas`、PNG、JPEG 质量 80（PNG 时忽略）、`high` 分辨率、20000 毫秒超时。方案缺失或列表为空时仍使用这一默认方案，不代表关闭渲染；WebUI 会显示可编辑的默认方案，配置页读取不会自动保存。在 WebUI 清空列表后保存，会保存并重新显示默认方案。旧环境级资源字段保留为隐藏的兼容项，避免宿主先清理掉旧地址；不会出现在编辑器中。升级时仅为缺少新字段的旧方案补入原地址并保存一次；已有新字段保持原值，扩展字段与顺序保留。新字段显式清空时使用预设默认地址；默认 CDN 不变。

AstrBot 原生配置页的三个资源地址都是单选下拉框。需要新增地址时选择“自定义地址…”，再填写出现的输入框；保存后会整理为实际 URL，并补入选项列表。插件 WebUI 则可以直接在选框中输入。两端保存的是同一份配置；已打开的页面保留编辑快照，需要关闭后重新打开才能看到另一端的修改。

开发验证可在真实 AstrBot 环境中运行 `tests/native_config_contract.py`（将宿主和插件根目录加入 `PYTHONPATH`）。该独立测试使用真实 `AstrBotConfig` 和原生配置读取服务，覆盖宿主清理旧字段、注入默认方案、原生自定义地址迁移、保存同步及重载；与 Pytest 离线桩测试分别执行。

选择或填好本轮 CDN 地址后，点旁边的「检测可用性」即可测试，不用先保存。检测会向下表中的实际资源地址发送 HEAD 请求，只接收响应头，不下载文件内容。可以展开「查看检测详情」，查看地址、响应耗时和 HTTP 状态。

| 检查内容 | 实际文件（GitHub 文件均位于本仓库 `assets/` 下） | 用途 |
| --- | --- | --- |
| 小图片 | `maria/rose_red.png` | Maria 模板蔷薇装饰 |
| 较大的图片 | `HatsuneMiku/retouch_2026032810150449.png` | 初音未来模板装饰 |
| 多层目录 | `deepseek_maid/layers/eye-0.png` | 鲸鱼女仆模板图层 |
| 背景图片 | `ATRI/file/1775130588385_1774881257527_bg1.webp` | ATRI 模板背景 |
| 中文文件名图片 | `ATRI/file/1775130581843_1774881262835_疑惑.webp` | ATRI 模板表情 |
| 中文文件名动图 | `ATRI/file/1775132805081_1774881262835_疑惑.gif` | ATRI 话题卡片动图 |
| 字体文件 | `ATRI/file/1775130743963_1774880718993_LXGWWenKai-Regular.woff2` | ATRI 霞鹜文楷字体，约 8 MB |
| 预览图 | `maria-demo.jpg` | WebUI 模板选择页面 |
| npm 兼容性 | `/npm/normalize.css@8.0.1/normalize.css` | 额外检查；当前内置模板未使用该文件 |

这些文件覆盖当前内置模板在此 CDN 上使用的路径类型：`/gh/用户/仓库@main/assets/...`、大小写目录、多层目录、英文和中文文件名，以及 PNG、JPG、WebP、GIF、WOFF2。中文文件名发送时会自动进行 URL 编码。npm 目前只是额外的兼容性测试，不能说成内置模板的实际依赖；项目目前没有使用 npm 作用域包、版本别名或无版本路径，因此没有加入这些无关检查。以后模板增加了新的路径类型，需要同步补充检测文件。

检测最多同时请求 4 个链接，每个请求最多等待 15 秒，跟随重定向后以 HTTP 2xx 作为可访问的依据。站点返回 405 或 501 时，会提示不支持 HEAD 检测，不会改用 GET 下载。检测不校验文件内容或测量下载速度，只说明这些代表链接本次是否响应成功；未通过时可以打开链接确认或稍后重试。

这里测试的是机器人所在服务器。如果使用远程图片渲染服务，请保存后再生成一份报告确认。Google 字体使用单独的镜像设置；自行设置的 ATRI 镜像、自定义模板写死的外链和画像资源地址也不在本次检测范围内。

开发模板时，请使用 `cdn_assets_base`、各主题的 `t2i_*_assets_mirror` 或 `t2i_npm_mirror` 变量拼接地址。WebUI 会提示并阻止保存格式错误的地址；为兼容手动编辑的旧配置，后端读到无效值时仍使用默认地址。国际化域名请使用 Punycode 形式。

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
| 大小 | 解压后总量 ≤ 5MB、单文件 ≤ 3MB、成员 ≤ 100 个（防恶意大文件与压缩炸弹） |
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
- **上传/下载限额**：zip 解压后总量 ≤ 5MB、单文件 ≤ 3MB、成员 ≤ 100、
  下载体 ≤ 5MB（流式限制），防止资源耗尽与大文件滥用。

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

## 11. 报告语言（report_language）与设置项条件显示

### 11.1 报告语言

- 配置项：`_conf_schema.json` → `basic.report_language`（紧跟 `report_template`，仅 HatsuneMiku
  模板可见），取值 `auto` / `zh-Hans` / `zh-Hant` / `en` / `ja`，默认 `auto`。
- `auto` = **按群聊消息正文自动判断**（不是「不干预」）：
  1. 先剥离非正文噪音（媒体占位整行、链接、`[CQ:...]`、方括号占位词、`@提及` 里的 ID）——
     昵称/贴纸名不算语言证据（真实场景：群友昵称就是三个平假名）；
  2. 每条有语言证据的正文投一票（出现假名 → ja；拉丁多于汉字 → en；否则有汉字 → zh）；
  3. 某一语言票数占比 **超过 70%** 且样本足够（≥3 条正文、≥20 个语言字符）才判定，
     否则不干预（混合语群不猜，走历史行为）；
  4. 中文再判简繁：**字形特征字 + 用词差异**合议——用词（应用程式/应用程序、资讯/信息、
     影片/视频…）会先折算成简体再比对，所以「用简体字写的台湾用词」同样算繁中；
     香港粤语用字（嘅/咗/唔/冇…）也算繁中。繁体分数更高且 ≥4 分 → `zh-Hant`，否则 `zh-Hans`。
- 字表/词表在 `src/shared/zh_variant_tables.py`（**自动生成，别手改**；数据来自 OpenCC，
  Apache-2.0）：约 2700 组简繁特征字 + 约 840 个繁中侧用词 + 约 820 个大陆侧用词 + 粤语常用字；
  重新生成：`python scripts/gen_zh_variant_tables.py`（可用 `--dict-dir` 指向本地字典）。
- 作用面三处：① 模板骨架文案、页面语言声明与字体优先级；② 报告日期格式；③ LLM 撰写的解说文案
  （唯一注入点在 `call_provider_with_retry`，覆盖全部分析器）。
- 引用保护：注入的指令强制要求「引用群友原话 / 昵称 / 群名 / @ / 链接 / JSON 字段名」原样保留，
  不得翻译或改写；报告语言只作用于解说文案。
- 模板侧：渲染上下文带 `report_language`，模板自解释（`auto` 未命中时不下发值）。
- 观测：分析服务会打一行 `报告语言自动判断(auto): <语言>`，验收直接 grep 这行。

### 11.2 新增一个多语言模板要动哪些地方（复用报告语言开关）

**唯一真源 = `src/shared/report_language.py` 的 `LANGUAGE_AWARE_TEMPLATES`**，加模板只需三步：

1. 模板自己内建语言字典（`en` / `zh-Hant` / `ja` 各列文案齐全），骨架文案按 `REPORT_LANG` 切换，
   页面语言声明与字体优先级一并跟随（参考 `templates/HatsuneMiku/` 的做法）；
2. 把模板名加进 `LANGUAGE_AWARE_TEMPLATES`——**报告语言只对该白名单生效**
   （未适配的模板套上语言只会得到「骨架中文 + 解说英文」的半成品，故做门禁）；
3. 跑 `python scripts/sync_report_language_templates.py`，它会把这个名单写进
   `_conf_schema.json` 的 `report_language.condition.report_template`——
   设置项「可见」与「生效」因此永远一致，不需要手改 JSON。

漏同步也不会静默出错：`tests/test_report_language.py::test_schema_condition_matches_code`
会在两边不一致时失败，并提示跑哪个脚本。

### 11.3 设置项条件显示 `condition`（AstrBot 官方键）

配置项位置：`basic.items` 里**紧跟在 `report_template` 之后**（渲染顺序即 JSON 键顺序，
所以面板上它就显示在「报告模板」正下方，只有选中 HatsuneMiku 时才出现）。

```json
"report_language": {
  "type": "string",
  "options": ["auto", "zh-Hans", "zh-Hant", "en", "ja"],
  "condition": {"report_template": "HatsuneMiku"}
}
```

- 语义：依赖项的当前值**等于**声明值时才显示本字段（**单值**，不是数组）。本仓库维护者已在
  `daily_comic.drawing_provider_overrides.*.size` / `custom_size` 上用同一写法；白名单超过一个模板时
  同步脚本会写成数组（插件自带面板支持命中任一即显示，官方面板届时需回归确认）。
- 支持裸字段名（跨分组查找）与 `"分组.字段"` 两种写法；多个键为「与」关系；`invisible` 优先级更高。
- 实现位置：`dashboard/src/pages/config/model/useConfigViewModel.ts` 的 `isFieldVisible()`；
  分组侧栏的字段计数与搜索命中数走同一规则，避免出现「侧栏数字 ≠ 实际可见字段数」。
- 官方键的好处：**AstrBot 官方 WebUI 与插件自带面板都按它隐藏字段**，不再需要各写一套私有逻辑。
  官方插件配置文档尚未列出该键（属于官方 core/WebUI 实际使用中的键），因此本仓库以
  `condition` 为唯一写法，并由 `test_schema_uses_official_keys_only` 禁止回退到自造键。

### 11.4 选项显示名 `labels`（AstrBot 官方键）

`options` 里存的是配置真实值（`zh-Hans` / `en` / `ja`…），直接摆给用户看不懂。官方键 `labels`
是**与 `options` 顺序一一对应**的显示名数组（官方文档「配置项国际化」一节明确说明：`options`
是保存值不建议翻译，下拉框展示文本用 `labels`，且支持按 WebUI 语言显示）：

```json
"report_language": {
  "options": ["auto", "zh-Hans", "zh-Hant", "en", "ja"],
  "labels": ["自动（按群聊判断）", "简体中文", "繁體中文", "ENGLISH", "日本語"]
}
```

- 实现：`dashboard/src/entities/config/model/optionLabel.ts` 的 `resolveOptionLabel(raw, options, labels)`，
  由 `FieldRenderer` 的单选下拉分支使用；纯显示层，不影响取值与校验。
- **位置数组，不是字典**：改造/新增选项时顺序必须与 `options` 严格对齐，否则标签会串位——
  `test_schema_uses_official_keys_only` 断言两者等长，前端单测里也有「顺序错位」用例。
- 未配标签、标签为空、或整份缺失时回退显示原始值。
