<div align="center">

# QQ群日常分析插件


[![Plugin Version](https://img.shields.io/badge/Latest_Version-v1.0.0-blue.svg?style=for-the-badge&color=76bad9)](https://github.com/SXP-Simon/astrbot-qq-group-daily-analysis)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-ff69b4?style=for-the-badge)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

_✨ 一个基于AstrBot的智能群聊分析插件，能够生成精美的群聊日常分析报告。[灵感来源](https://github.com/LSTM-Kirigaya/openmcp-tutorial/tree/main/qq-group-summary)。 ✨_

<img src="https://count.getloli.com/@astrbot-qq-group-daily-analysis?name=astrbot-qq-group-daily-analysis&theme=booru-jaypee&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto" alt="count" />
    </div>


## 功能特色

### 🎯 智能分析
- **话题分析**: 使用LLM智能提取群聊中的热门话题和讨论要点
- **用户画像**: 基于聊天行为分析用户特征，分配个性化称号
- **统计数据**: 全面的群聊活跃度和参与度统计

### 📊 可视化报告
- **PDF报告**: 生成专业的PDF格式分析报告（推荐）
- **精美图片**: 生成美观的HTML+CSS可视化报告
- **多种格式**: 支持图片和文本输出格式
- **用户头像**: 自动获取QQ头像，让报告更加生动
- **详细数据**: 包含消息统计、时间分布、关键词等

### 🛠️ 灵活配置
- **群组管理**: 支持指定特定群组启用功能
- **参数调节**: 可自定义分析天数、消息数量等参数

## 效果
![效果图](./demo.jpg)

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

### 配置选项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| enabled_groups | 启用分析的QQ群列表 | [] (所有群) |
| max_messages | 最大分析消息数量 | 1000 |
| analysis_days | 默认分析天数 | 1 |
| output_format | 输出格式 (pdf/image/text) | pdf |
| require_admin | 仅管理员可用 | false |
| topic_analysis_enabled | 启用话题分析 | true |
| user_title_analysis_enabled | 启用用户称号分析 | true |

## 分析内容

### 📊 基础统计
- 消息总数
- 参与人数  
- 总字符数
- 表情数量
- 最活跃时段

### 💬 话题分析
- 自动提取3-5个主要话题
- 识别话题参与者
- 总结讨论要点和结论

### 🏆 用户称号
基于用户行为特征分配称号：
- **水群小能手**: 发言频繁的活跃用户
- **技术专家**: 经常讨论技术话题
- **夜猫子**: 深夜活跃用户
- **表情包批发商**: 经常发表情
- **沉默终结者**: 经常开启话题
- **剧作家**: 平均发言长度很长
- **互动达人**: 经常回复他人
- **KOL**: 群内意见领袖

### 🔥 数据洞察
- 热门关键词统计
- 用户活跃度排行
- 时间分布分析
- MBTI性格类型推测

## 安装要求

### 基础要求
- 已配置LLM提供商（用于智能分析）
- QQ平台适配器


## 注意事项

1. **性能考虑**: 大量消息分析可能消耗较多LLM tokens
2. **数据准确性**: 分析结果基于可获取的群聊记录，可能不完全准确

## 更新日志

### v1.0.0
- 初始版本发布
- 支持基础群聊分析功能
- 智能话题和用户称号分析
- 精美可视化报告生成

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request来改进这个插件！
