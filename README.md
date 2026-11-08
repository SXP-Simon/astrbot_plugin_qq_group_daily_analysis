<div align="center">

# 群聊日常分析插件

[![Plugin Version](https://img.shields.io/badge/当前版本-v6.0.0-blue.svg?style=for-the-badge&color=76bad9)](https://github.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis)
[![AstrBot](https://img.shields.io/badge/AstrBot-插件市场入口-ff69b4?style=for-the-badge)](https://cloud.astrbot.app/plugin/SXP-Simon/astrbot_plugin_qq_group_daily_analysis)
[![AstrBot Version](https://img.shields.io/badge/AstrBot-%3E%3D4.24.1-orange.svg?style=for-the-badge)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Ask DeepWiki](https://img.shields.io/badge/Ask_DeepWiki-AI_知识库-1877F2?style=for-the-badge&logo=data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAAgACADASIAAhEBAxEB/8QAFwABAQEBAAAAAAAAAAAAAAAAAAYHCP/EACIQAAEDBAIDAQEAAAAAAAAAAAECAwQABQYHERIxMkFxCP/EABcBAQEBAQAAAAAAAAAAAAAAAAABAgP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwDkylK2r+f9b64zbDckn5fmaLJdYZ6Q2lzWY6UApBS6oOe4Kz148D9IroyxWlW+w9UZ5gFot91yqyiFEnqLbLiJLboC+CequhPBIBI8gj78qIqhW1aA2LrTC8NySDmWGt3u6yz3hOrgtSErSEgJZUV+gCx258H9AFYrSoLjYm2M72BaLfacqvKJkSAouNNtxm2QV8EdldAOSASkeAB8+1D0pVH/2Q==)](https://deepwiki.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis)

<table align="center" style="border: none;">
  <tr>
    <td style="border: none;" align="center">
      <a href="https://qm.qq.com/q/oTzIrdDBIc"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/QQ.png" width="300" alt="QQ Group"></a>
    </td>
    <td style="border: none;" align="center">
      <a href="https://t.me/AstrBotPluginGroupDailyAnalysis"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/TG.png" width="300" alt="Telegram Group"></a>
    </td>
  </tr>
  <tr>
    <td style="border: none;" align="center"><b>QQ群</b></td>
    <td style="border: none;" align="center"><b>Telegram群</b></td>
  </tr>
</table>

_✨ 一个基于 AstrBot 的智能群聊分析插件，支持 **OneBot** ( [NapNeko/NapCatQQ<img src="https://avatars.githubusercontent.com/u/165024194?s=200&v=4" width="14px" >](https://napneko.github.io/), [LLOneBot/LuckyLilliaBot<img src="https://avatars.githubusercontent.com/u/161472069?s=200&v=4" width="14px" >](https://www.llonebot.com/), [SnowLuma/SnowLuma<img src="https://avatars.githubusercontent.com/u/216149176?s=200&v=4" width="14px" >](https://snowluma.github.io/))、**QQ 官方机器人**、**Telegram**、**Discord**，未来支持更多平台。 ✨_

<img src="https://count.getloli.com/@astrbot-qq-group-daily-analysis?name=astrbot-qq-group-daily-analysis&theme=booru-jaypee&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto" alt="count" />
</div>

- [常见问题 (FAQ)](#常见问题-FAQ)
- [效果](#效果)
- [功能特色](#功能特色)
- [配置选项](#配置选项)
- [每日群漫画配置](#每日群漫画配置)
- [使用方法](#使用方法)
- [大模型原生函数调用 (LLM Tools)](#大模型原生函数调用-llm-tools)
- [平台支持与要求](#平台支持与要求)
- [增量分析模式](#增量分析模式-beta)
- [图片报告与 Typst 本地渲染](#图片报告与-typst-本地渲染)
- [数据与资源管理](#数据与资源管理)
- [HTML报告与自建外链](#HTML-报告与自建外链)
- [人格设定 (Persona)](#人格设定-Persona)

## 效果

### 1. **群分析报告**：生成群聊活跃度、参与度、话题、金句等统计的可视化报告

<table align="center" width="100%">
  <tr>
    <td align="center" width="33.3%" valign="top">
      <p><b>HatsuneMiku (默认)</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/HatsuneMiku-demo.webp"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/HatsuneMiku-demo.webp" alt="HatsuneMiku 示例" height="520"></a>
    </td>
    <td align="center" width="33.3%" valign="top">
      <p><b>maria</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/maria-demo.webp"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/maria-demo.webp" alt="圣母在上 (Maria · 山百合会) 报告示例" height="520"></a>
    </td>
    <td align="center" width="33.3%" valign="top">
      <p><b>Scrapbook</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/scrapbook-demo.webp"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/scrapbook-demo.webp" alt="Scrapbook 示例" height="520"></a>
    </td>
  </tr>
  <tr>
    <td align="center" width="33.3%" valign="top">
      <p><b>Hack</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/hack-demo.webp"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/hack-demo.webp" alt="Hack 示例" height="520"></a>
    </td>
    <td align="center" width="33.3%" valign="top">
      <p><b>ATRI</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/ATRI-demo.webp"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/ATRI-demo.webp" alt="ATRI 示例" height="520"></a>
    </td>
    <td align="center" width="33.3%" valign="top">
      <p><b>DeepSeek 鲸鱼女仆娘</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/deepseek_maid-demo.webp"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/deepseek_maid-demo.webp" alt="DeepSeek 鲸鱼女仆娘报告示例" height="520"></a>
      <p><code>deepseek_maid</code> · <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/deepseek_maid/SOURCE-NOTICE.md">素材署名与许可</a></p>
    </td>
  </tr>
</table>

### 2. **每日群漫画**：将群分析结果改编为趣味连环漫画，支持图生图参考图和独立绘图服务

<table align="center" width="100%">
  <tr>
    <td align="center" width="100%" valign="top">
      <img src="https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/comic-demo.webp" alt="群每日漫画功能" width="60%">
      <p><b>参考 Atri 人格的群每日漫画 Demo</b></p>
    </td>
  </tr>
</table>

## 功能特色

### 🎯 智能分析

- **统计数据**: 全面的群聊活跃度和参与度统计
- **话题分析**: 使用LLM智能提取群聊中的热门话题和讨论要点
- **用户画像**: 基于聊天行为分析用户特征，分配个性化称号
- **圣经识别**: 自动筛选出群聊中的精彩发言
- **每日群漫画**: 将本次分析结果改编为趣味连环漫画，支持图生图参考图和独立绘图服务
- **LLM 函数调用**: 提供 AstrBot 原生 Tool Calling 的群聊分析工具，支持自然语言只读报告检索与按需异步分析触发

### 🎛️ WebUI 控制台

- **内嵌管理面板**: 原生集成在 AstrBot 插件管理页面，无需额外部署，集中提供总览、分析记录、统计、报告、日志、配置与数据七个页面
- **插件配置中心**: 内置专属可视化配置界面，提供 12 个功能分组导航与即时搜索；支持已有人格与大模型服务商下拉点选、漫画参考图本地上传与灯箱预览，修改保存即时生效
- **趋势分析与消耗看板**: 支持近48小时、近7天、近14天、近30天等不同时间跨度切换，直观呈现 API 请求走势、大模型 Tokens 消耗堆叠图与服务商消耗占比环形饼图
- **报告浏览与主题重绘**: 历史报告支持长图与 HTML 在线预览及一键下载。图片可拖动查看，使用滚轮或双指缩放，也可选择原始尺寸；支持切换视觉主题（手账、亚托莉、蔚蓝档案、初音未来、黑客赛博、复古像素、极简等）重新生成报告，直接复用已有数据，0 Token 成本
- **时序事件时间线**: 在「统计」页面提供连续水平时间轴，支持鼠标拖拽平移与快速回溯历史样本，直观查看各群聊的消息清洗留存与模块消耗
- **全流程可观测性与实时监控**: 运行中任务状态与步骤实时同步感知；任务详情按父子阶段展示分析、素材准备、排队、编译和发送过程，保留重试与恢复原因；Typst 可分别查看编译子进程内存、CPU 耗时与宿主内存净变化
- **任务停止与断点续跑**: 群内手动分析沿用 AstrBot 内置 `stop`，WebUI 任务可在「总览」中止；续跑有有效快照的任务时复用已有分析，重复续跑也继承原任务数据与分析日期
- **字体、素材与存储管理**: 可从 Typst 方案直达字体或素材管理，按主题补齐、上传及替换；报告文件支持搜索、类型筛选与多选删除，自定义模板按实际目录选择管理，详见[数据与资源管理](#数据与资源管理)
- **任务与报告双向关联**: 在任务详情中可直接查看对应产生的所有报告文件；从历史报告中点击任务编号，可快速跳转到该次任务的执行明细与日志
- **异常任务自动清理**: AstrBot 重启时自动标记并清理未正常结束的中断任务，不留烂尾

部分截图使用示例数据。

<table align="center" width="100%">
  <tr>
    <td align="center" width="50%" valign="top">
      <p><b>总览</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/overview-20261108-b3eb04579d.png"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/overview-20261108-b3eb04579d.png" alt="总览" width="100%"></a>
    </td>
    <td align="center" width="50%" valign="top">
      <p><b>配置与校验</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/config-20261108-3d36f42581.png"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/config-20261108-3d36f42581.png" alt="配置与校验" width="100%"></a>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%" valign="top">
      <p><b>分析记录</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/traces-20261108-de3b7d2ba0.png"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/traces-20261108-de3b7d2ba0.png" alt="分析记录" width="100%"></a>
    </td>
    <td align="center" width="50%" valign="top">
      <p><b>报告与重绘</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/reports-20261108-29096c774f.png"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/reports-20261108-29096c774f.png" alt="报告与重绘" width="100%"></a>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%" valign="top">
      <p><b>统计与消耗</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/statistics-20261108-1ab5371b6c.jpg"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/statistics-20261108-1ab5371b6c.jpg" alt="统计与消耗" width="100%"></a>
    </td>
    <td align="center" width="50%" valign="top">
      <p><b>日志</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/logs-20261108-8ce3608813.png"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/logs-20261108-8ce3608813.png" alt="日志" width="100%"></a>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%" valign="top">
      <p><b>任务阶段与渲染回退</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/task-diagnosis-20261108-c6b0ca7c4a.jpg"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/task-diagnosis-20261108-c6b0ca7c4a.jpg" alt="任务阶段与渲染回退" width="100%"></a>
    </td>
    <td align="center" width="50%" valign="top">
      <p><b>继续分析</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/resume-20261108-ee6a4545b4.jpg"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/resume-20261108-ee6a4545b4.jpg" alt="继续分析" width="100%"></a>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%" valign="top">
      <p><b>数据与阶段快照</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/data-checkpoints-20261108-299de32635.png"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/data-checkpoints-20261108-299de32635.png" alt="数据与阶段快照" width="100%"></a>
    </td>
    <td align="center" width="50%" valign="top">
      <p><b>Typst 字体管理</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/typst-fonts-20261108-2d0a6ff65f.png"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/typst-fonts-20261108-2d0a6ff65f.png" alt="Typst 字体管理" width="100%"></a>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%" valign="top">
      <p><b>报告模板画廊</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/template-gallery-20261108-9440eea52d.png"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/template-gallery-20261108-9440eea52d.png" alt="报告模板画廊" width="100%"></a>
    </td>
    <td align="center" width="50%" valign="top">
      <p><b>报告文件管理</b></p>
      <a href="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/report-file-management-20261108-14aca297cb.png"><img src="https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/plugin/webui/report-file-management-20261108-14aca297cb.png" alt="报告文件管理" width="100%"></a>
    </td>
  </tr>
</table>

### 📊 可视化报告

- **多种格式**: 支持图片、文本与 HTML 输出格式
  - **精美图片**: 可通过 AstrBot T2I、自定义 T2I 服务或插件独立 Typst 引擎生成报告长图；Typst 无需浏览器，支持内置主题，详见[启用方法](#图片报告与-typst-本地渲染)
  - **HTML报告**: 生成清晰的HTML格式分析报告，可以进一步配置为外链形式发送
  - **QQ群**: 支持上传到群相册和群文件，查阅黑历史友好
- **详细数据**: 包含消息统计、时间分布、关键词、金句等

## 配置选项

> [!NOTE]
> 以下配置情况仅供参考，请仔细阅读插件配置页面中各个字段的说明，以插件配置中的说明为准。

| 配置项                  | 说明                                                        | 备注                                                                             |
| ----------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------- |
| 自动分析时间列表        | 控制定时报告的每日触发时间。                                | 清空并保存后会移除已注册的定时报告；增量分析仍按其独立配置和新增消息量触发       |
| 定时分析名单模式 + 列表 | 控制哪些群参与定时任务（报告时间点触发）。                  | 可选 `inherit` 继承基础群权限；`whitelist + 空列表` 表示不注册定时任务           |
| 增量分析名单模式 + 列表 | 控制哪些群走增量模式，其他群走传统全量。                    | 可选 `inherit` 继承定时分析最终名单；`whitelist + 空列表` 表示不启用增量周期任务 |
| 每日群漫画              | 分析结果完成后并行生成漫画，也可用 `/群漫画` 单独生成。     | `enable_daily_comic` 是总开关，`enable_auto_daily_comic` 控制分析后自动联动      |
| 图片渲染方案            | 在「图片渲染策略」添加 AstrBot、自定义 T2I 或 Typst 方案。 | 优先级越小越先尝试；已有配置不会自动切换为 Typst，参见[本地渲染说明](#图片报告与-typst-本地渲染) |
| HTML 格式 (自建)        | 配置 `html_base_url` 后，机器人会发送可直接点击的报告外链。 | 输出格式需设为 html                                                              |
| 自定义 LLM 服务         | 用户可自行选取个人提供的服务商。                            | 留空则回退到默认服务商                                                           |

## 每日群漫画配置

每日群漫画不按自然日限流：每次成功得到群分析结果时都会尝试生成一张。手动群分析、定时传统分析、定时增量最终报告，以及开启“增量分析立即报告”后的即时增量最终报告都适用。同一群已有漫画在排队或生成时，新请求会直接跳过，避免重复出图；不同群仍受漫画并发配置限制。

也可以使用 `/群漫画 [天数]` 单独生成漫画。这个命令只拉取消息、提取话题并启动漫画生成，不会生成日报、称号、金句、聊天质量，也不会写入日报历史。

1. `enable_daily_comic` 是漫画总开关：关闭时，手动 `/群漫画` 和所有自动联动漫画都不会出图。
2. `enable_auto_daily_comic` 是自动联动开关，默认开启。它同时控制手动群分析、定时分析和增量最终报告完成后的漫画生成；关闭后仍可使用 `/群漫画` 按需出图。
3. 如果希望“群分析完成后自动联动漫画”，需要在 `分析功能` 配置组保持 `topic_analysis_enabled` 开启，让漫画直接复用报告已提取的话题；手动 `/群漫画` 会单独提取话题。
4. 使用 `漫画群名单模式` 和 `漫画群白/黑名单列表` 控制哪些群可以生成漫画。默认 `inherit` 会继承基础群权限：分析报告触发的漫画会直接复用已通过的手动/定时/增量入口判定，不需要重复填写名单。若只想开放漫画、不开放分析，可把漫画名单模式改为 `blacklist`（空列表=所有群允许）或 `whitelist`（只允许列表里的群）。
5. 可选切换绘图后端 `drawing_backend`：`builtin`（默认，使用本插件内置绘图客户端）；`general_plugin`（调用 [「通用生图」插件](https://github.com/Railgun19457/astrbot_plugin_image_generation) 公共 API）；`big_banana`（调用 [「大香蕉」插件](https://github.com/sukafon/astrbot_plugin_big_banana) 绘图管线）。外部后端需在对应插件中配置其自身的 API/提供商。外部后端失败时由 `drawing_external_fallback` 决定是否回退内置后端（默认回退，关闭则直接取消本次漫画）。
6. 在 `绘图供应商配置表` 点击“添加条目”，选择与上游服务匹配的预设；每个条目独立填写 API Key、端点、模型、尺寸、宽高比、超时与可选代理。至少保留一个启用且包含 API Key 的条目。
7. 多个条目按 `priority` 从高到低尝试；优先级相同时按表中顺序尝试。当前条目请求失败后会自动切换到下一个候选，全部失败才判定本次漫画生成失败。
8. 可选填写 `drawing_prompt_provider_id`。它用于把分析结果整理成绘图分镜提示词；留空时使用插件的常规 Provider 回退策略。
9. 可选在 `漫画角色方案` 中新增一个或多个方案：每个方案可单独选择漫画专用人格、编辑漫画场景分析提示词，并上传 `jpg`、`jpeg`、`png` 或 `webp` 参考图；没有参考图时仍会走文生图。具体会发送多少张参考图取决于当前绘图供应商的能力和条目上限。
10. 默认固定使用第一个已启用角色方案。开启 `每天随机切换漫画角色` 后，插件会在运行环境时区的每天首次生成漫画时随机选择一个已启用方案，并在当天持续使用同一方案；优先读取 `TZ` 环境变量，未设置或无效时使用系统本地时区。角色方案内的人格和场景提示词只作用于漫画分镜提示词，不会改变话题、金句或最终报告的人格。
11. 升级前已配置的 `漫画参考图` 会自动迁移为 `默认角色方案`，迁移前数据会备份到插件数据目录的 `config_backups`。既有角色方案会继承升级时的全局漫画场景分析提示词；新建角色方案自带默认提示词，清空后回退到全局默认模板。

#### 漫画生图服务商兼容性

致谢：[@piexian/astrbot_plugin_gemini_image_generation](https://github.com/piexian/astrbot_plugin_gemini_image_generation)

供应商预设负责将漫画分镜和角色参考图转换为各家的原生请求格式。是否可用仍取决于你的账号权限、模型名称、区域和上游服务状态；选择 OpenAI 兼容 Chat 预设时，也需要上游模型本身能够在聊天响应中返回图片。

| 预设                     | 请求协议                           | 参考图           | 主要能力与限制                                                                                                                      |
| ------------------------ | ---------------------------------- | ---------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Google Gemini            | Gemini `generateContent`           | 支持，最多 14 张 | 支持 `1K/2K/4K` 与宽高比。                                                                                                          |
| OpenAI / Z.ai / grok2api | OpenAI 兼容 Chat Completions       | 支持             | 将尺寸与布局要求写入提示词，图片从聊天响应中提取；由上游模型决定是否支持生图。                                                      |
| OpenAI Images            | `/v1/images/generations`、`/edits` | 支持，可设置上限 | GPT Image 可设置质量、背景、响应格式、JPEG/WebP 压缩、审核和仅文生图模式。                                                          |
| xAI                      | xAI Images                         | 支持，最多 5 张  | 自动在文生图与 edits 间切换。                                                                                                       |
| Agnes AI                 | 原生 Images                        | 支持             | 通过 `extra_body.image` 发送参考图。国际站使用 `apihub.agnes-ai.com`，中国站使用 `api.agnes-ai.cn`，请按 API Key 所属站点选择预设。 |
| MiniMax                  | `/v1/image_generation`             | 支持，最多 9 张  | 使用 `subject_reference` 角色参考图字段。                                                                                           |
| 阶跃星辰                 | Images generations / edits         | 支持，首张       | 有参考图时使用官方 multipart edits 请求。                                                                                           |
| 豆包 Seedream            | 火山方舟 Images                    | 支持             | 普通模型最多 14 张，Seedream 5.0 Pro 最多 10 张且不支持组图；支持 Endpoint ID、自定义尺寸、提示词优化和组图。                       |
| SenseNova U1 Fast        | SenseNova Images                   | 不支持           | 仅文生图；支持官方尺寸映射，单次生成数量限制为 1-4 张。                                                                             |
| DashScope                | 通义万相 / 千问原生接口            | 支持，最多 9 张  | 支持自定义尺寸、数量、水印、负面提示词和提示词扩展；wan2.7 的推理与顺序组图互斥，qwen-image-2.0 最多 6 张。                         |
| 自定义协议               | Images / Chat / Grok / Gemini      | 取决于协议       | 用于未列出的兼容服务；请选择与实际端点一致的协议。                                                                                  |

所有条目均可单独配置 `proxy`；条目代理优先于全局 `drawing_proxy`，全局代理也会用于下载同次生图响应中的图片。请求超时按条目配置，重试、下载代理和投递策略仍为全局设置。

分析结果完成后，自动联动漫画会立即在后台运行，报告渲染与发送不会等待出图完成。反过来，报告发送失败也不会取消已经开始的漫画任务。自动联动只复用报告中的有效话题总结，因此需要开启话题分析；话题功能关闭、话题 LLM 无结果或标题为空时会跳过本次自动漫画。手动 `/群漫画` 则会独立提取话题，不依赖报告功能开关。

### 分析黑白名单配置说明（小白能懂）

同一个 AstrBot 接入多个机器人时，名单只填群号会匹配这些机器人下的同号群。只想让其中一个机器人分析，请在对应群聊中通过 AstrBot 的 `/sid` 获取完整 UMO（命令前缀跟随宿主配置），将它填入名单，例如 `bot_a:GroupMessage:123456`。两个接入都启用时，会分别分析并消耗 Token；插件不会跨接入合并它们的分析数据。

下面只讲“在面板里怎么点”。

#### 自动分析的判定顺序（很重要）

系统会按下面顺序判断，前一关没过就直接停止：

1. 基础群权限（`basic`）
2. 定时分析名单（`auto_analysis`）
3. 增量名单（`incremental`，只决定模式，不决定放行）

一句话版：  
`basic` 决定“能不能参与自动分析” -> `auto_analysis` 决定“会不会自动触发” -> `incremental` 决定“触发后用哪种分析方式”。

#### inherit 模式怎么工作

`inherit` 不保存或复制任何名单，而是在判定时复用上一级的最终结果：

| 配置组                      | 设为 `inherit` 后的行为                                                            | 该组列表 |
| --------------------------- | ---------------------------------------------------------------------------------- | -------- |
| 定时分析（`auto_analysis`） | 直接继承基础群权限。基础白名单允许的群会参与定时分析；基础黑名单排除的群不会参与。 | 忽略     |
| 增量分析（`incremental`）   | 直接继承“基础群权限 + 定时分析名单”的最终结果。通过定时分析的群全部使用增量。      | 忽略     |

因此，最省配置的组合是：基础名单填一次，定时分析设为 `inherit`，增量分析也设为 `inherit`。名单变更后，定时目标和增量消息计数状态会按新的继承结果刷新。

兼容性边界：定时分析和增量分析仍默认 `whitelist`，且空列表仍表示未启用，升级不会意外创建自动任务。只有显式改为 `inherit`，才会开始继承上一级名单。

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

#### 场景 C：名单只填一次，所有自动群都走增量

1. 在 `基础设置` 配置群聊白名单或黑名单。
2. 在 `定时分析设置` 把 `定时分析名单模式` 设为 `inherit`。
3. 在 `增量分析设置` 把 `增量分析名单模式` 设为 `inherit`。
4. 在 `自动分析时间列表` 填入需要的时间。

例如，基础白名单只填写群 A、群 B 后，定时任务只会处理 A、B，且 A、B 都会走增量；不用再把 A、B 填到后两组列表。

#### 场景 D：Telegram 用户怎么填最稳

1. 在面板里需要填群的地方，尽量填完整会话ID（例如 `telegram2:GroupMessage:-1001234567890`）。
2. 不建议新手只填纯群号，容易填错平台。
3. 先在群里执行 `/sid`，复制结果粘贴到列表里就行。

#### 最容易踩坑的 5 点

- `定时分析名单模式` 选 `whitelist` 时，如果 `定时分析群列表` 为空，任务不会自动跑。
- `增量分析名单模式` 选 `whitelist` 时，如果 `增量分析群列表` 为空，增量不会生效，会走普通分析。
- 定时分析设为 `inherit` 时，基础白名单为空也不会有自动目标；基础黑名单或无限制模式则会让所有未被基础名单排除的群成为自动目标。
- 增量分析设为 `inherit` 时，所有通过定时名单的群都会走增量；若只想让部分群增量，请改用 `whitelist` 或 `blacklist`。
- `增量失败自动回退全量分析` 建议保持开启，这样增量异常时也能尽量产出报告。

#### 你可能会问（关键边界）

- 不在“定时白名单”里，但在“增量白名单”里，会触发吗？  
  不会。因为会先被“定时白名单”拦住，进不到增量判断。

- 不在“基础群权限”里，但你开了定时分析，会触发吗？  
  不会。基础群权限是第一关，不通过就不会进入后续流程。

> [!IMPORTANT]
> **多平台配置注意**：
>
> - **自动发现**: 插件会自动发现已登录的 Bot 实例。

> [!TIP]
> **自定义 LLM 服务回退机制**：性能优先，策略如下：
>
> 1.  尝试从配置获取指定的 provider_id
> 2.  回退到主 LLM provider_id
> 3.  回退到当前会话的 Provider (UMO)
> 4.  回退到第一个可用的 Provider

## 使用方法

### 基础命令

#### 群分析

```
/群分析 [天数]
```

- 分析群聊近期活动
- 天数可选，默认为1天
- 例如：`/群分析 3` 分析最近3天的群聊

手动分析进行中，可在同一会话发送 AstrBot 内置的 `/stop`（前缀跟随 AstrBot 配置，如 `*stop`）。插件通过宿主后台任务登记和共享停止信号取消关联的分析、渲染和后续发送，不额外注册 `stop` 命令，也不覆盖宿主 Agent 的停止回调。启用群内用户会话隔离时，需要由原发起人在同一机器人实例下发送。不提供后台任务登记的旧版宿主依赖内置 `stop` 写入前台事件停止标记；如果旧版第三方 Agent 只终止事件传播，需要升级宿主。WebUI 或定时任务请在任务面板中止。

#### 群漫画

```
/群漫画 [天数]
```

- 单独生成群聊趣味漫画，不生成日报
- 天数可选，默认为基础配置中的分析天数
- 例如：`/群漫画 3` 根据最近3天群聊话题生成漫画

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
/查看模板 [模板名称或序号]
/设置模板 [模板名称或序号]
```

- `/查看模板`: 查看可用模板及预览图；QQ 官方 Bot 每次展示一张，可用按钮填入翻页或切换命令，没有相关权限时使用普通消息
- `/查看模板 [序号或名称]`: 查看指定模板，例如 `/查看模板 2`；查看和设置仍需管理员权限
- `/设置模板`: 查看当前模板和可用模板列表
- `/设置模板 [序号]`: 切换到指定序号的模板
- 例如：`/设置模板 1` 或 `/设置模板 scrapbook`

发送预览时会自动转为 JPEG 并复用缓存，兼容平台图片接口；WebUI 画廊仍使用 WebP。

### 大模型原生函数调用 (LLM Tools)

插件原生接入 AstrBot `@filter.llm_tool` 规范，为宿主大模型（Agent）注入群聊分析记忆与调度能力。用户无需记忆任何 `/` 斜杠指令，在日常自然语言对话中即可与 AI 助手无缝交互：

```text
群友: "今天群里聊了什么？大家都在讨论什么热点话题？"
AI:   (自动调用 group_daily_analysis_get_report)
      "今天群里主要讨论了两个话题：1. Docker 容器网络配置... 2. 新番讨论..."

管理员: "帮我重新分析一下今天的群聊，发到群里"
AI:     (自动调用 group_daily_analysis_trigger)
        "已为您提交今日群聊的异步重算任务（预计耗时约 1 分钟）。分析完成后将自动把长图推送到本群！"
```

#### 原生工具矩阵

| 工具标识 (Tool Name) | 操作类型 | 调用权限 | 响应时延 | 默认行为 |
| :--- | :--- | :--- | :--- | :--- |
| **`group_daily_analysis_get_report`**<br>群日报只读检索 | 纯只读检索 | **全体成员** | 毫秒级直出 | 提取历史快照，组装为紧凑 Markdown 返回给模型回答，**0 额外 Token 消耗** |
| **`group_daily_analysis_trigger`**<br>按需分析异步触发 | 重型分析流水线 | **仅管理员** | ~500ms 异步受理 | 启动后台分析流水线（预计 1 分钟左右完成），**默认自动渲染长图推送至群聊** |

#### 工具特性与设计亮点

1. **只读报告检索 (`group_daily_analysis_get_report`)**：
   - **4 级群目标自适应解析（防反问）**：群聊环境中调用时**自动精准绑定当前群**；私聊中支持**群名模糊搜索**；出现重名时返回候选列表引导用户。大模型无需反复向用户追问群号。
   - **弹性自然语言日期**：无缝支持 `今天`、`昨天`、`前天` 以及标准 `YYYY-MM-DD` 格式；当指定日期尚无报告时，自动向后滑动探测最近一天的有效快照。
   - **同日多版本窗口去重**：底层基于 SQL 窗口函数，即使一天内手动或定时多次触发，永远仅返回最新生成的一份有效报告。
   - **跨平台脱敏与格式清洗**：自动将话题发言人中的纯数字 ID / OpenID 清洗替换为真实群昵称；过滤空称号与无效空行。
   - **防爆流安全截断**：文本输出上限严格控制在 40,000 字符以内，防止超长记录击穿模型上下文窗口。

2. **按需异步触发 (`group_daily_analysis_trigger`)**：
   - **严格管理员双重鉴权**：仅限群主、群管理员、Bot 全局管理员及配置白名单用户触发，普通成员越权触发时秒级拦截并引导其使用只读检索工具，防止昂贵分析流水线被闲聊误刷。
   - **异步非阻塞受理（Fire-and-Forget）**：群分析全量流水线通常需要约 1 分钟，触发工具在 500ms 内向大模型返回 Trace 受理凭证，将计算任务转交后台协程异步执行，**彻底消除对话端 30s HTTP 阻塞超时与 504 网关中断隐患**。
   - **长图推送与静默模式双轨 (`render_to_chat`)**：
     - **默认发图 (`render_to_chat=True`)**：符合用户自然期待，分析完成后自动调用派发器将渲染出的高清日报长图发送至目标群聊。
     - **静默入库 (`render_to_chat=False`)**：当明确要求“后台更新不要发群”时，仅完成数据持久化落库，不打扰群友。
   - **群级并发排他锁**：群粒度互斥锁保护，防止同一群聊并发重复触发分析任务。

> [!TIP]
> 📖 想要了解工具调用协议细节、上下文防反问设计与 8 大 Corner Cases 边界规范？请参阅 **[《大模型工具 (LLM Tools) 技术规格与开发指南》](docs/llm_tools_development_guide.md)**。


## 平台支持与要求

| 平台              | 适配器类型                         | 驱动与方言支持                                                                                                                   | 特殊要求/说明                                                                                                                                                        |
| ----------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **QQ (OneBot)**   | OneBot v11 / v12                   | **方言驱动架构**：内置 NapCat、LLOneBot (LuckyLilliaBot)、SnowLuma、Standard (go-cqhttp / Lagrange / onebots / WeChatBridge) 驱动 | 插件通过 `get_version_info` / `get_version` 自动探测并动态绑定最佳方言驱动；支持多端群相册、群文件多级解包、协议端真实头像与全链路观测日志。                       |
| **QQ 官方机器人** | QQ Bot API v2（WebSocket/Webhook） | 官方统一 API                                                                                                                     | 需开启群全量消息；只分析启用后实时缓存的消息；图片/HTML 优先显示事件昵称，缺失时使用群内稳定匿名名；Markdown 文本使用成员艾特。                                      |
| **Discord**       | Discord                            | Discord Gateway                                                                                                                  | **必须** 拥有 `Read Message History` (查看消息历史记录) 权限。                                                                                                       |
| **Telegram**      | Telegram Bot API                   | Telegram Bot API                                                                                                                 | 若机器人不是群管理员，入群前需先在 BotFather 关闭隐私模式 (`/setprivacy` -> `Disable`)。若机器人已在群内且非管理员，关闭后需要先移出机器人再重新拉入，设置才会生效。 |

> [!TIP]
> **OneBot 协议端方言驱动架构特性**：
>
> 插件采用了开放闭合原则 (OCP) 的**方言驱动解耦架构**，在连接时自动探测后端实现并无缝自适应：
> 1. **NapCat.Onebot**：支持标准逆序分页、独有的 `upload_file_stream` 分块流式上传大图/兜底、`get_qun_album_list` 群相册列表与协议端真实头像解析。
> 2. **LLOneBot (LuckyLilliaBot)**：支持相册上传专属 `files` 列表参数、相册列表 `data: list` 数组解包与多层嵌套兼容。
> 3. **SnowLuma**：支持专属 `message_id` 锚点分页拉取群历史（不传 `reverseOrder`）、精准识别 `result=120` / `rejected` 发送拒绝与禁言错误。
> 4. **Standard (go-cqhttp / Lagrange / onebots / 微信桥接 WeChatBridge)**：
>    - **真实用户头像**：针对微信/企业微信接入等映射数字 ID 场景，优先通过 `get_stranger_info` / `get_user_info` 获取真实头像 URL（带 1 小时正缓存与并发去重），失败时自动回退官方 CDN 并进入 10 分钟负缓存，杜绝重复无效请求。
>    - **群文件与相册多级解包**：自动兼容 `data.folders`、`data.album_list`、顶层列表等不同协议端返回格式，确保文件夹自动创建与归档不回退。
>    - **全链路可观测日志**：动作发起、参数目标、原始响应 Payload 与解析降级流转全景上报，方便快速诊断排障。

> [!IMPORTANT]
> **QQ 官方机器人用户注意**：
> 插件同时支持 AstrBot 的 `qq_official` 与 `qq_official_webhook` 平台。
>
> - 在群聊中需要由群主允许机器人接收群内全部消息，使 AstrBot 能收到 `GROUP_MESSAGE_CREATE` 事件；只开放 @ 消息时，报告只能覆盖 @ 机器人的聊天。
> - QQ 官方 API 不提供“按群拉取历史消息”的接口。插件会从启用后开始实时保存消息，并从 AstrBot 本地消息历史库分页读取；启用前的群聊无法自动回填。
> - 官方群和成员使用 `group_openid` / `member_openid`，不是群号或 QQ 号。配置白名单、定时任务时建议先在群内执行 `/sid`，填写完整 UMO。
> - 新分析会通过官方接口查询群名并显示在任务记录中，无需新增配置。群名会缓存一小时；权限不足、限流或网络失败时保留上次获取的群名或 OpenID，五分钟后可再次尝试，不影响分析和发送。已有历史记录不会批量改名，群名查询也不用于判断管理员权限。
> - 官方群事件提供有效昵称时会用于报告；昵称缺失时使用群内稳定匿名名，避免直接展示 `member_openid`。
> - 表情统计只采用本条原始事件的 `<faceType=…>` 标记或明确的 `Face` 组件，入库保存类型、标识与必要的可读名称，历史读取后用于群统计、个人统计及增量合并。同一消息重复接收不会重复入库；同一条正文中重复使用的表情按实际次数记录，引用消息中的表情不重复计算。
> - QQ 官方附件无法仅凭 URL、GIF 后缀或文件名可靠区分普通图片与表情包，因此图片保持图片类型，不一律计为表情；纯文本 Unicode emoji 也不额外扫描，不增加相关依赖。旧记录若只剩 `[表情:…]` 描述，无法确定是否为用户手打文字，不据此补猜表情。
> - QQ 官方文本报告使用自定义 Markdown，默认启用透明背景的群聊概览图，将日期、基础统计和 24 小时竖向直方图合并为紧凑布局。可在 `QQ 官方机器人 → 启用群聊概览图` 关闭（原名称为“启用 T2I 群聊概览图”，配置键不变）。生成或发送概览图失败时恢复包含文字条形图的完整报告。
> - 首选图片方案为 Typst 时，使用插件数据目录中的中文字体生成固定 940×423 PNG，通过 QQ 官方素材管理接口上传，获得 `qqbot-media://` 引用后与正文在同一条 Markdown 中发送；不需要公网图床，也不会把本地路径或 Base64 塞进 Markdown。请先在数据管理下载中文字体。
> - QQ 素材接口有每个机器人 100 张的数量限制；报告发送结束后，插件只删除本次自己上传的素材以释放配额，已发送消息中的图片不受影响。接口不可用或上传失败时使用完整文字报告，不会另发独立图片。
> - HTML/T2I 概览图沿用公网 URL 在 Markdown 内嵌入图片；请确保 T2I 端点域名已加入 QQ 开放平台的消息 URL 配置。消息要求 QQ 校验图片转存，失败后使用完整文字报告。
> - 本次适配只覆盖普通 QQ 群，不包含频道或子频道。

> [!CAUTION]
> **Discord 用户重点注意**：
> 如果机器人无法获取群列表或分析报 `403 Forbidden`，请检查 Discord 开发者面板中：
>
> 1. **Privileged Gateway Intents**: 开启 `Message Content Intent`。
> 2. **频道权限**: 确保机器人所在的频道，对应的角色拥有 **“查看消息历史记录”** 权限。

> [!IMPORTANT]
> **Telegram 用户重点注意**：
>
> 1. 如果 TG Bot 不是群管理员，务必在拉入群前先关闭 BotFather 隐私模式。
> 2. 如果 Bot 已经在群里且不是管理员，关闭隐私模式后必须先移除再重新拉入群，否则新设置不会生效。
>
> 注：群聊隐私模式关闭流程：`@BotFather`→左下角Open→选择要调整的bot→Bot Settings→将`Group Privacy`关闭

## 注意事项

> [!WARNING]
>
> 1. **性能考虑**: 大量消息分析可能消耗较多 LLM tokens
> 2. **数据准确性**: 分析结果基于可获取的群聊记录，可能不完全准确

## 增量分析模式 (Beta)

增量分析模式是为了解决消息量大的群聊（如日均消息 > 500 条）在单次分析时容易丢失上下文的问题。

**核心特性：**

- **滑动窗口**：不再受限于自然日，分析窗口随时间滑动（如过去 24 小时），确保任何时候生成的报告都覆盖完整的时间段。
- **按量分批**：目标群每累计到配置的消息数就执行一个固定规模批次，平滑 LLM 负载。
- **自动去重**：智能识别重复话题和金句，合并生成最终报告。

**启用方法：**

- 通过 `incremental_group_list_mode + incremental_group_list` 指定哪些群走增量模式，并使用 `incremental_min_messages` 设置每批触发消息数。

## 图片报告与 Typst 本地渲染

### 选择渲染方式

图片报告可按优先级依次尝试不同方案：

| 方案 | 在哪里渲染 | 字体与装饰图片 |
| --- | --- | --- |
| 海外 / 内地方案（AstrBot T2I） | 使用群聊绑定的 AstrBot 图片服务 | 按当前方案的 CDN、在线字体等配置加载 |
| 自定义 T2I 方案 | 连接自行填写的兼容 T2I 服务地址 | 在线加载；也可显式选择使用服务端已安装字体 |
| Typst 本地排版 | 在 **AstrBot 所在服务器或容器**中启动插件独立编译进程，无需 Chromium 或 AstrBot T2I 服务 | 字体由插件 data 目录管理，装饰图片本地优先，缺失时从方案 CDN 获取 |

Typst 只生成静态图片，支持 PNG 和 JPEG；HTML 网页报告仍走 HTML 模板，保留网页交互与动效。远程 T2I 通常无法访问机器人本机的文件，给 Typst 下载字体或素材不会让远程 HTML 渲染器自动使用它们，HTML 默认仍使用 CDN 字体和图片。

目前内置主题提供 Typst 排版。各主题保留自身配色和主要组件结构；静态图片不包含 HTML 的响应式布局、折叠或动画。

### 启用 Typst

1. 升级插件并确认依赖安装成功。若提示缺少 `typst`，通过 AstrBot 插件依赖安装流程补装后重载插件。
2. 打开插件 WebUI「**配置中心 → 图片渲染策略 → 图片渲染方案**」，点击「**添加渲染方案 → Typst 本地排版**」。希望首先使用本地渲染时，设置比其他方案更小的优先级；同优先级按列表顺序执行。已有 T2I 方案可保留用于失败回退。
3. 在该方案的「**Typst 字体**」选择报告主题，点击「**下载所选模板字体**」；在「**模板原始素材**」选择同一主题并下载缺失素材。只需准备所用主题，共享文件自动复用，也可一次补齐全部预设资源。
4. 在「**基础设置**」选择「**报告模板**」，并在「**输出格式（可多选）**」中包含 `image`。手动分析使用首个选中的输出格式，希望手动生成图片时请将 `image` 放在首位。方案内的 PNG / JPEG 是图片文件格式，与这里的 `image` / `text` / `html` 报告类型不同。
5. 保存配置。可先点击方案内的「**测试渲染**」验证编译器能否出图；测试不调用大模型、不向群发送消息，也不能代替完整主题的字体和素材检查。随后使用群内「群分析」命令或 WebUI「手动触发分析」生成报告。

> [!NOTE]
> Release 包不附带全部字体及装饰图。首次使用请先补齐资源；Typst 的字体、原始素材分别保存在插件数据目录 `typst/fonts/`、`typst/resources/`，升级时可继续复用。模板列表会按当前渲染引擎和输出格式显示兼容项；只有 HTML 的主题不会用于 Typst，仅有 Typst 的主题不能生成 HTML 网页。

### 字体与素材下载、上传

方案内的「**管理 / 上传字体**」和「**管理 / 上传模板素材**」可直达同一套[数据管理面板](#数据与资源管理)，带上所选主题和下载来源；返回方案后保留未保存的配置。

- **字体来源**：默认「CDN 优先（大字库直连）」，也可切换为「GitHub Raw 直连（全部字体）」。ATRI 文楷、Miku 全瀨體等大字体本身就从固定版本 Raw 下载，更换 CDN 不会改变这些直连地址。下载由机器人服务器或容器执行，浏览器能访问不代表服务端能访问；Raw 受限时需检查服务端网络或代理。
- **下载进度与取消**：字体显示当前文件、实际来源、接收字节与等待时间，素材显示完成数量与失败文件。下载可以取消，已完成文件保留；失败重试只补缺失项，可切换 CDN 或字体来源后再试。
- **手动补字体**：在字体管理对应行点击「查看上游」核对版本，或使用「直接下载」在浏览器下载，再点击该行「上传此字体」，自动按预设文件名保存。上传显示进度并支持取消；普通「上传字体」保留文件名，适合自定义字体。若提示宿主不支持二进制上传，请升级 AstrBot 后重试。
- **逐文件补素材**：进入「模板原始素材 → 主题素材管理」，选定主题并展开「素材文件与状态」，可上传或替换清单中的单个文件；「本地素材与替换」管理已保存到插件 data 的文件。资源优先本地复用，尚未准备的装饰图会在渲染时尝试从方案 CDN 获取，缺图时记录警告并降级展示。
- **共享影响**：替换或移除字体可能影响多个主题，操作前可查看依赖关系。

### 清晰度、超时与运行开销

Typst 排版固定为 **940px 逻辑版心**，高度随内容增长。方案的「**导出清晰度（PPI）**」只改变像素密度，不改变字号、换行和布局：

| 导出密度 | 成品宽度 | 使用建议 |
| --- | --- | --- |
| 144 PPI（默认） | 940px | 日常使用、资源有限的服务器 |
| 180 PPI | 1175px | 需要更多文字细节，接受额外开销 |
| 216 PPI | 1410px | 更看重原图清晰度，接受更高内存与更长等待 |

PNG 无损，调节「JPEG 质量」不会改变 PNG 清晰度。超长报告会在导出前根据像素预算逐档降低密度，任务详情显示请求值与实际值。提高 PPI 会增加栅格导出耗时和内存，不能保证本地渲染比远程 T2I 更快；多个原生编译任务共用编译名额，排队可以避免同时生成长图叠加内存峰值。

「**单次编译超时（毫秒）**」默认 `30000`（30 秒），仅限制每次编译进程，素材准备与排队另计；主题编译和基础恢复分别计时，整轮图片生成仍受五分钟总上限约束。主题失败或超时时，会尝试以标准密度的基础排版保留正文；仍失败时继续尝试已配置的其他方案，最终无法出图时回退文字。主动取消不会继续恢复或尝试下一方案。

耗时较长时，打开「**分析记录 → 详情**」，逐层展开图片渲染阶段，查看素材、排队、布局与栅格导出耗时。开启运行时遥测后还可查看编译子进程 RSS 峰值、峰值增长与 CPU 耗时；「宿主 RSS 净变化」仅表示 AstrBot 进程变化，不能代替编译内存占用。父阶段包含子阶段耗时，各层百分比不要直接相加。CPU 较弱、报告较长或密度较高时，可降低 PPI，或根据实测调整单次编译超时。

## 数据与资源管理

新版 WebUI 简化了顶部入口名称，功能仍在原位置：「运行总览」改为「总览」，「统计与消耗」改为「统计」，「历史报告」改为「报告」，「配置中心」改为「配置」，「数据管理」改为「数据」，「运行日志」改为「日志」；「分析记录」名称不变。下文沿用旧名称的操作路径也对应这些入口。

在「分析记录」点击「详情」查看阶段树，选择阶段后可阅读对应的调用、渲染或错误记录；「耗时、内存与传输」保留图表，「完整任务记录」可查看全部字段。原「幂等续跑」按钮改为「继续分析」，仍可临时选择模型和报告模板；系统优先复用已有快照，快照缺失时可能重新分析并产生模型消耗。

打开插件 WebUI「**数据管理 → 存储空间概览 → 存储分区明细与管理**」，可查看各类数据占用，并进入对应管理页：

| 分区 | 可以做什么 |
| --- | --- |
| 历史报告文件 | 预览、下载，按文件名搜索，按 HTML / JPG / PNG 筛选；支持 JPG + PNG 组合筛选和跨页多选删除 |
| 自定义报告模板 | 搜索并选择实际模板目录，查看 HTML / Typst 支持标签，安装模板包、管理源码与素材、移除模板 |
| Typst 字体 | 按主题检查已安装、缺失和共享依赖，补齐、上传、替换或移除字体 |
| 模板原始素材 | 查看主题资源清单，按需下载或全部补齐，上传替换单个文件，管理本地素材 |
| 配置参考素材 | 预览、上传或替换参考图片，管理文件时注意仍在使用它的配置 |
| 配置自动备份 | 查看版本、时间与原始配置内容，下载原件或删除备份；不直接修改备份内容 |
| 派生图片与预览缓存 | 查看并清理可重建文件；运行目录和数据库通过对应业务入口管理 |

文件列表包含「**Typst 模板（.typ）**」等类型筛选。多选删除每批最多 200 项，改变筛选条件会清空选择，防止误删隐藏项；覆盖和删除会校验文件版本，遇到其他页面刚修改过的文件时请刷新后再操作。增量批次、阶段快照与分析存档也提供相应的查询和管理入口，无需直接编辑数据库文件。

WebUI 手动分析可从「**运行总览 → 正在执行中的分析任务 → 中止**」取消。取消请求接受后仍需等待后台资源回收；运行状态、分析记录与任务详情会同步更新。任务失败后可在详情中续跑，有有效分析快照时复用已经完成的 LLM 分析；历史记录只有摘要时不能还原完整结果。

## HTML 报告与自建外链

如果你希望在群里发送的不是图片，而是一个可以点击跳转的精美网页链接，可以使用 HTML 格式输出。

### 1. 配置流程

1. **设置输出格式**：在「基础设置」的「输出格式（可多选）」（`output_format`）中选择 `html`；手动分析希望直接发送网页时，将它放在首位。
2. **指定储存目录 (`html_output_dir`)**：设置 HTML 文件在服务器上的保存路径。留空则默认保存在插件数据目录。
3. **配置外链基址 (`html_base_url`)**：这是关键。如果你使用 Nginx/Apache 等 Web 服务器将上述目录映射到了公网，请在这里填写访问的前缀（如 `https://report.example.com`）。

### 2. 工作原理

- 机器人生成 HTML 报告并保存到本地目录。
- 机器人根据文件名和 `html_base_url` 拼接成完整链接发送到群里。
- **注意**：本插件**不提供** Web 服务器功能，你需要自行使用 Nginx 或 AstrBot 所在的服务器环境来实现静态文件的公网访问。

## 人格设定 (Persona)

插件支持深度的“人格化”分析，让 AI 能够以特定的人设风格（口吻、偏好、语气）来产出摘要和锐评。

### 人格识别优先级

插件在构建分析任务时，会按以下顺序确定最终使用的“人设状态”：

1.  **强制插件人格 (优先级最高)**：在配置中开启 `强制使用插件指定人格` 并选择 ID。此时 **全平台、所有群聊** 都会统一使用这一种人设，忽略群聊本身的设置。
2.  **继承会话人设 (优先级次之)**：在配置中开启 `继承会话人设风格`。插件会尝试识别当前群聊在 AstrBot 中设置的人格（如通过 `/persona` 指令设置的人设）。如果该群已有人设，分析报告将尽量模拟其说话倾向。
3.  **系统默认人设**：若上述开关均关闭，或未识别到有效人设，则回退到当前默认设定。

### 自定义与第三方报告视觉模板

插件支持动态加载和实时识别用户自定义或第三方的报告视觉排版模板：

1. **模板存放路径**：
   放置于插件数据目录 `custom_t2i_templates/reporting_templates/<模板英文或拼音目录名>/`（例如 `custom_t2i_templates/reporting_templates/genshin/`）。
2. **按所需输出提供入口**：
   - `report.typ`：Typst 图片入口，可以独立组成 Typst 模板，也可与 HTML 入口共存；接收运行时提供的 `data.json`，使用固定 940px 逻辑版心，高度自然延伸。

   HTML 主题可包含以下 7 个 Jinja2 文件，分别提供长图、网页与子模块排版：

   - `image_template.html`：**长图海报主骨架**（接收并组合以下各小模块生成的 HTML 片段）。
   - `html_template.html`：**独立网页报告主骨架**。
   - `topic_item.html`：**话题总结列表模块**（渲染 `topics_list`）。
   - `user_title_item.html`：**群友称号与画像模块**（渲染 `titles_list`、头像与 MBTI 标签）。
   - `quote_item.html`：**群友金句与锐评模块**（渲染 `quotes_list`）。
   - `activity_chart.html`：**24小时活跃轨迹折线图/热力图模块**（渲染 `chart_data`）。
   - `chat_quality_item.html`：**群聊质量多维锐评模块**（渲染质量得分与维度评价）。
3. **支持局部修改与自动兜底**：
   - **全量深度定制**：提供全部 7 个 HTML 文件，实现从页面主视觉到各个子卡片组件的 100% 定制。
   - **轻量局部定制**：如果仅针对长图外框或主布局进行微调（例如仅提供了 `image_template.html`），插件的 Jinja2 多层回退引擎会自动使用默认手账模板（`scrapbook`）中对应的小模块 HTML 作为兜底加载，确保即使子模块不全也能稳定渲染。
   - **Typst 失败恢复**：主题编译失败后尝试基础排版保留正文。HTML 与 Typst 主入口各自独立，不会把缺少入口的主题当作另一种引擎的完整实现。
4. **即选即用**：
   放入新模板目录后无需重启机器人。配置、断点续跑和历史报告重绘按当前渲染引擎及输出格式筛选兼容入口，展示 HTML 图片、HTML 网页、Typst 图片等支持标签；只有 Typst 入口的模板不能用于 HTML 网页输出。
5. **在线安装与卸载**：
   在 Web 控制台配置页的模板选择器旁点击「安装模板」，可通过 **GitHub 仓库链接**
   （如 `https://github.com/owner/repo`，支持 `/tree/<分支>`）自动下载安装，
   或直接上传 **zip 压缩包**；安装后立即生效，可随时通过「卸载模板」移除。
   也可在「数据管理 → 存储分区明细与管理 → 自定义报告模板」安装模板包，通过可搜索的选择器进入指定模板，维护源码与素材。安装包、手动创建的模板及缺少有效入口的目录均可按整组移除；**内置模板不可卸载**。删除整个模板前请确认没有群聊仍在使用它。
   📖 完整模板制作指南（变量契约、回退机制、打包规范、调试、贡献清单）见
   **《[报告视觉模板开发指南](docs/REPORT_TEMPLATE_GUIDE.md)》**，参考示例仓库：[lingyun14beta/daily-analysis-report-theme](https://github.com/lingyun14beta/daily-analysis-report-theme)。

### 插件更新升级配置保护

插件会在每次正常启动时记录当前版本与配置结构。后续只要检测到**配置结构发生变化**，就会把上一次正常加载的插件配置快照保存到**插件数据目录**（注意不是插件目录）的 `config_backups`；文件名包含旧版本和备份时间，只保留最新二十份。插件版本仅用于标识备份来源，不是备份条件；调整描述或提示文本不会生成备份。日志会显示旧版本、备份文件名和完整路径。通过 WebUI 修改配置后，请正常重载插件或重启 AstrBot，使该配置成为下一次升级可保护的快照。

官方内置模板（`src/infrastructure/reporting/templates/`）与用户自定义模板（`data/plugin_data/astrbot_plugin_qq_group_daily_analysis/custom_t2i_templates/reporting_templates/`）完全解耦分离。内置模板跟随插件统一升级维护，自定义模板可在 WebUI「安装模板」或通过独立目录存放，无需改动源码，升级不丢失。

AstrBot 更新插件时会先删除旧插件目录，再解压或移动新目录，并在实例化插件前依据新 schema 清理旧配置项。因此升级保护依赖上一次正常启动预先保存的配置快照。WebUI 每次保存都会自动重载插件，正常保存过的配置会成为下一次升级可保护的快照。

## 常见问题 (FAQ)

### 获取不到带记录的引用消息

**现象**：
后台日志出现 `[warn] ... 似乎是旧版客户端 ... [error] ... 获取不到带记录的引用消息`。

**原因**：
这是由于 NapCat/NTQQ 消息 ID 格式变动、消息过期或临时会话限制导致的。机器人尝试降级使用旧版序号查找失败。

**忽略**：如果只是偶尔出现（如回复久远消息），不影响机器人核心功能（收发消息），可以直接忽略。

### 图片生成失败 / 渲染返回非图片数据 / 头部 `496e7465726e616c...` 的排查指南

以下排查针对 HTML / T2I 服务。若使用「Typst 本地排版」，请先查看[本地渲染的超时与开销说明](#清晰度超时与运行开销)，并在任务详情区分素材下载、排队、编译和编码耗时；Typst 不使用 Playwright / Chromium。

> [!WARNING]
> **常见报错特征**：
> - `[群分析插件] 渲染引擎返回了非图片数据: HTTP 500 (Internal Server Error) ...`
> - `[群分析插件] 渲染结果似乎不是有效的图片数据 (头部: 496e7465726e616c2053)`
> - `playwright._impl._errors.TimeoutError: Page.goto: Timeout 50000ms exceeded. navigating to "file:///app/data/rendered_....html", waiting until "load"`

#### 🔍 报错根因拆解

十六进制 `496e7465726e616c2053` 转为 ASCII 文本即为 **`Internal S`**（`Internal Server Error`）。说明 T2I 渲染服务在调用 Playwright / Chromium 无头浏览器生成T2I时遭遇了内部错误或超时，向 AstrBot 返回了 **HTTP 500 纯文本**而非合法的 PNG/JPEG 二进制图片流。

---

#### 🛠️ 典型根因与排查解决手段

> [!IMPORTANT]
> **排查手段 1：外链大字体包/图片 CDN 下载阻塞（国内服务器高发）**
> - **每轮单独配置资源**：在插件 WebUI 的「图片渲染方案」点击「添加渲染方案」（AstrBot 配置页为「添加条目」），选择海外、内地或自定义 T2I 方案，再修改这一轮的模板 CDN、Google Fonts 和 Gstatic 地址。AstrBot 配置页使用下拉预设和“自定义地址”入口，保存后会显示并保留实际地址；插件 WebUI 可直接填写地址，也可通过“选择预设”填入。两端共用配置，已打开的页面需重新打开后查看另一端的修改。CDN 需支持 `/gh/` 和 `/npm/`。使用前请测试T2I服务所在网络的速度和可达性；「检测可用性」检查的是机器人服务器，远程 T2I 仍需实际生成报告确认。
> - **自定义服务的字体加载方式**：通常保持「在线字体」。已在T2I服务安装字体，或字体下载经常超时且愿意接受备用字体时，可选择「使用已安装字体」；只影响本轮图片报告，素材图片仍需 CDN。安装位置、完整字体清单及适用情况见[字体安装指南](https://cdn.jsdmirror.com/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/docs/T2I_FONTS.md)。
> - **配置多轮回退**：可为不同轮次填写不同 CDN，也可以只更换字体地址。优先级越小越先执行，同优先级按列表顺序执行；资源地址变化时重新准备 HTML，成功后停止。所有轮次共用 5 分钟总等待上限。独立 HTML 报告和模板预览采用第一优先级方案的资源地址。
> - **先单独测试渲染服务**：海外、内地、自定义 T2I 与 Typst 方案均有「测试渲染」按钮，不用先保存，也不消耗大模型 Token 或向群里发消息。海外／内地方案可测试 AstrBot 默认配置，或已有群聊绑定的配置；自定义方案测试当前填写的地址和 Token；Typst 验证本地编译器。测试小图不能代替完整报告的字体和素材检查。容器名称支持下划线，但两个容器需要网络互通；配置示例见[渲染方案与容器网络说明](docs/REPORT_TEMPLATE_GUIDE.md#52-模板内部引用的图片重要渲染链路约束)。
> - **添加自定义T2I服务**：添加时可选「海外方案」「内地方案」或「自定义 T2I 方案」。前两种跟随本群绑定的 AstrBot 配置，未配置地址时仍由框架使用官方服务。自定义方案默认填入 `http://127.0.0.1:8999/text2img`，可修改地址并填写可选 Token，兼容官方独立服务与 [插件形式的 T2I 服务](https://github.com/XTsat/astrbot_plugin_t2i_service)。它直接连接指定服务，不读取 AstrBot 地址或环境代理。T2I超时默认 20 秒，请求等待上限默认 40 秒，两项可独立设置，为服务内部切换备用地址和返回图片留出时间；停止操作与五分钟总上限仍生效。自定义方案的资源环境默认海外，可切换内地；空资源地址跟随环境预设，手填地址优先。容器中的 `127.0.0.1` 指向该容器，其他容器或宿主机服务需填写对应地址。本地T2I不会自动缓存外链素材。
> - **查看升级前的配置**：在「数据管理 → 存储空间概览 → 配置自动备份」点击「查看备份」，可以查看旧版本、备份时间和原始 JSON 层级。升级时先归档旧快照再迁移配置，正常保存后同步更新保护快照；旧资源项不再长期保留在正式配置中。没有历史快照时只能使用预设，无法自动找回已被宿主清理的旧地址。
> - **默认与旧配置**：初始提供海外（优先级 10）和内地（优先级 20）两项方案（均为 PNG、高分辨率、20 秒），默认 CDN 保留原地址。旧方案缺少资源字段时，升级会将原环境级地址补入方案并保存一次；已有的新字段和自定义图片保留。之后每轮独立生效，新字段留空使用该预设的默认地址。保存后列表按优先级排列，同优先级保持原顺序；清空列表后恢复上述两项，已有非空列表不会自动增加条目。渲染成功但缺少个别素材时，不会自动进入下一轮。
> - **原因**：Playwright `page.goto` 默认使用 `wait_until="load"` 策略，会阻塞等待 HTML 报告中引入的所有外链 CSS、字体包及角色立绘图片全部下载完毕。部分精美模板包含 30MB+ 的中文字体文件或引用的海外 CDN（如 jsDelivr/Fastly），若国内服务器网络波动，50 秒内未全部下载完毕便会触发超时抛出 500。
> - **解决方案**：
>   1. **优先走 IPv4 路由（推荐）**：国内云服务器（如腾讯云/阿里云）默认启用了 IPv6，但访问海外 CDN 经常遭遇 IPv6 握手黑洞（超时等待 15~30s）。在宿主机编辑 `/etc/gai.conf`，追加 `precedence ::ffff:0:0/96 100` 强制系统优先走 IPv4。
>   2. **尝试海外资源环境**：添加一项海外预设方案，或直接修改这一轮的 CDN 和字体地址，并从T2I服务所在网络测试。
>   3. **配置资源环境回退**：例如第一项使用内地预设，第二项使用海外预设或另一 CDN，并降低分辨率或 JPEG 质量。只有前一项渲染失败才会执行下一项，全部失败后沿用原有的文字回退流程；是否复用浏览器缓存由渲染服务决定。

> [!IMPORTANT]
> **排查手段 2：容器化部署未挂载共享数据卷 (Volume)**
> - **原因**：AstrBot 生成的 HTML 报告保存在宿主机的 `astrbot_data` 目录；如果 T2I 服务容器在启动时**未正确挂载该目录**，容器内部的 Chromium 访问 `file:///app/data/rendered_*.html` 时将找不到该文件，直接抛出 `TimeoutError` 或 `ERR_FILE_NOT_FOUND`。
> - **解决方案**：检查 Docker / Podman 启动参数，确保挂载了与 AstrBot 相同的数据卷：
>   ```bash
>   # T2I 容器必须挂载 AstrBot 数据目录至 /app/data 与 /AstrBot/data
>   -v /path/to/astrbot_data:/app/data \
>   -v /path/to/astrbot_data:/AstrBot/data
>   ```

> [!TIP]
> **排查手段 3：无头环境 Chromium 沙箱或共享内存限制**
> - **原因**：在资源受限环境下，Chromium 渲染大型高清图片容易因 `/dev/shm` 共享内存不足（默认仅 64MB）或系统 seccomp/沙箱策略拦截导致浏览器进程假死崩溃。
> - **解决方案**：为 T2I 服务容器补充以下安全参数与内存分配：
>   ```bash
>   --shm-size=1g \
>   --security-opt seccomp=unconfined \
>   -e PLAYWRIGHT_CHROMIUM_SANDBOX=0
>   ```

---

#### 📋 底层报错日志查看与 Issue 上报指引

<details>
<summary><b>点击展开：自部署获取 T2I 真实底层堆栈与向社区反馈</b></summary>

1. **查看 T2I 容器实时运行日志**：
   ```bash
   # Podman 部署环境
   podman logs -f --tail 100 astrbot-t2i-service
   
   # Docker 部署环境
   docker logs -f --tail 100 astrbot-t2i-service
   ```
2. **遇到未知十六进制头部 (如 `头部: 1f8b0800...`)**：
   - 插件已内置响应多态解析，若遇到未知二进制数据，日志中会打印完整 Hex 头部与大小；
   - 提交 Issue 时请一并附上 **AstrBot 插件运行日志** 与 **T2I 容器终端日志**，以便维护者快速定位是网络压缩编码问题、反向代理拦截还是底层渲染异常。

</details>

> [!NOTE]
> **更换 T2I 端点或自部署参考**：
> - **官方自建教程**：[docs.astrbot.app/others/self-host-t2i.html](https://docs.astrbot.app/others/self-host-t2i.html)
> <details>
> <summary><b>若配置调整后渲染仍频繁失败，可尝试更换 T2I 服务（点击此行展开说明）：</b></summary>
>
> - **Hugging Face 服务**: `https://huggingface.co/spaces/clown145/astrbot-t2i-service`
> - **API 接口地址**: `https://clown145-astrbot-t2i-service.hf.space`
>   - **说明**:
>     1. **复制空间**：可访问上方空间地址并点击 **Duplicate Space** 复制到自己的账号下使用。
>     2. **配置填写**：在 **AstrBot 系统配置** 中填入相应的 API 地址（格式通常为 `https://用户名-空间名.hf.space`）。
>     3. **稳定性**：上方地址为维护者提供 T2I 服务（国外网络环境），在一段时间内大概率稳定，但不保证长期有效，如果自己不想部署可以使用。
>     4. **休眠保活**：由于免费空间若长时间（约 48 小时）无人访问会进入休眠。可选择使用保活服务（如 [UptimeRobot](https://uptimerobot.com/)）定期访问 API 地址以保持其处于唤醒状态。
> - **国内加速**: `https://t2i.vercel.ciallo.de5.net`
>   - **说明**: 在国内直接访问原始域名下载图片可能较慢，可选择使用此代理域名。在一段时间内大概率稳定。
>   </details>


## 🤝 参与贡献 (Contributing)

我们非常欢迎社区参与插件的开发与改进！

如果你希望：

- 🛠️ 参与 Python 后端或 WebUI 前端代码开发
- 🎨 贡献新的精美视觉模板（提供离线热调预览工具）
- 🐛 提交 Bug 修复或性能优化 PR
- 📝 了解代码规范（Google-style Docstring、FSD、0 any、Ruff 格式化、Conventional Commits）

👉 请参阅完整的 **[贡献指南 (CONTRIBUTING.md)](./CONTRIBUTING.md)**。

## ❤️ Special Thanks

❤️ 特别感谢所有 Contributors 的贡献 ❤️

<a href="https://github.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=SXP-Simon/astrbot_plugin_qq_group_daily_analysis&max=200&columns=14" />
</a>

## ⭐ Star History

> [!TIP]
> 如果这个项目对你的生活或工作有帮助，或者你对它的未来发展感兴趣，请给这个项目一个 Star。这是维护这个开源项目的动力 <3

<a href="https://www.star-history.com/?repos=SXP-Simon%2Fastrbot_plugin_qq_group_daily_analysis&type=date&releases=&legend=bottom-right">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=SXP-Simon/astrbot_plugin_qq_group_daily_analysis&type=date&theme=dark&legend=bottom-right" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=SXP-Simon/astrbot_plugin_qq_group_daily_analysis&type=date&legend=bottom-right" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=SXP-Simon/astrbot_plugin_qq_group_daily_analysis&type=date&legend=bottom-right" />
 </picture>
</a>

## 许可证

MIT License

欢迎提交Issue和Pull Request来改进这个插件！
