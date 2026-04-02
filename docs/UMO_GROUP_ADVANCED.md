# UMO Group 高级特性与最佳实践

本文档补充说明 UMO Group 功能的高级特性、边界情况处理和最佳实践。

## 边界情况处理

### 1. UMO 属于多个 UMO Group

#### 问题描述

在某些配置场景下，一个 UMO 可能同时出现在多个 UMO Group 的 `source_umos` 列表中。例如：

```json
{
  "umo_groups": {
    "groups": [
      {
        "group_id": "tech_all",
        "source_umos": [
          "onebot:GroupMessage:111111",
          "onebot:GroupMessage:222222"
        ],
        "output_umo": "onebot:GroupMessage:999991"
      },
      {
        "group_id": "important_groups",
        "source_umos": [
          "onebot:GroupMessage:111111",  // 重复！
          "onebot:GroupMessage:333333"
        ],
        "output_umo": "onebot:GroupMessage:999992"
      }
    ]
  }
}
```

在这个例子中，`onebot:GroupMessage:111111` 同时属于 `tech_all` 和 `important_groups` 两个 UMO Group。

#### 当前行为

- 配置加载时，系统会通过 `_validate_umo_groups()` 检测并**记录提示日志**
- 在运行时，会收集该 UMO 所属的**所有** UMO Group，并将报告广播到它们的 `output_umo`
- 发送目标会进行去重，避免同一个 UMO 收到重复的消息

#### 最佳实践

**推荐做法**：仍建议每个 UMO 只属于一个 UMO Group

如果确实需要一个 UMO 的报告发送到多个目标：
1. 将该 UMO 放入多个 UMO Group
2. 系统会自动向所有匹配的 `output_umo` 发送报告（去重）

### 2. UMO 既属于 Group 又需要独立报告

#### 问题描述

某些场景下，你可能希望：
- 一个 UMO 的消息被聚合到 UMO Group 进行统一分析
- 同时，该 UMO 也需要生成并发送自己的独立报告

例如：
- 群 A、B、C 聚合分析，报告发送到管理群 M
- 但群 A 同时也需要接收自己的独立报告

#### 当前行为

从 v4.9.13 开始，可以通过配置直接启用“双重发送”：
- 报告会发送到 Group 的 `output_umo`
- 如果在 `dual_send_source_umos` 中声明了该 UMO（或所在的 UMO Group），也会发送一份到原始 UMO

#### 解决方案

可以在配置中添加 `umo_groups.dual_send_source_umos`：

```json
{
  "umo_groups": {
    "groups": [
      {
        "group_id": "tech_all",
        "source_umos": [
          "onebot:GroupMessage:222222",
          "onebot:GroupMessage:333333"
        ],
        "output_umo": "onebot:GroupMessage:999999"
      }
    ],
    "dual_send_source_umos": [
      "onebot:GroupMessage:222222"
    ]
  }
}
```

这样，群 222222 的报告会同时发到 `output_umo`（999999）和它自身。

也支持直接写 `_umoGroup:ID`，为整个 Group 成员开启双重发送。

## 匹配逻辑详解

### 统一的匹配算法

从 v4.9.12+ 开始，所有 UMO 匹配使用统一的 `_match_umo_to_source()` 方法，支持：

#### 1. 完整 UMO 精确匹配

```
source: "onebot:GroupMessage:111111"
target: "onebot:GroupMessage:111111"
结果: ✅ 匹配
```

#### 2. 简单 ID 匹配

当配置中使用完整 UMO，而查询使用简单 ID 时：

```
source: "onebot:GroupMessage:111111"
target: "111111"
结果: ✅ 匹配
```

或反过来：

```
source: "111111"
target: "onebot:GroupMessage:111111"
结果: ✅ 匹配
```

#### 3. Telegram 话题父群匹配

Telegram 的话题（Topic）使用 `#` 分隔父群 ID 和话题 ID：

```
source: "telegram:GroupMessage:-1001234567890"
target: "telegram:GroupMessage:-1001234567890#2264"
结果: ✅ 匹配（话题 #2264 属于父群）
```

简单 ID 也支持：

```
source: "-1001234567890"
target: "-1001234567890#2264"
结果: ✅ 匹配
```

### 一致性保证

以下功能使用相同的匹配逻辑：
- `is_group_allowed()` - 权限白/黑名单检查
- `is_group_in_filtered_list()` - 定时分析、增量分析名单检查
- `find_umo_group_for_source()` - 查找 UMO 所属的 Group

这确保了行为的一致性，避免了不同功能之间的匹配逻辑差异。

## 配置验证

### 自动验证

在 ConfigManager 初始化时（插件启动时），会自动调用 `_validate_umo_groups()` 进行验证。

验证内容：
- ✅ 检测 UMO 的多重 Group 成员关系
- ⚠️ 发现问题时记录警告日志，但不会阻止启动

### 示例警告日志

```
[WARNING] 配置警告：UMO 'onebot:GroupMessage:111111' 同时属于多个 UMO Group: ['tech_all', 'important_groups']。
在使用 find_umo_group_for_source 或 get_report_destination_umo 时，将使用第一个匹配的 Group ('tech_all')。
建议：确保每个 UMO 只属于一个 Group，或明确文档说明优先级规则。
```

### 如何查看警告

启动 AstrBot 或重载插件时，检查日志输出中是否有 `[WARNING]` 级别的配置警告。

## 故障排查增强

### 报告重定向日志

当报告被重定向到 UMO Group 的 output_umo 时，会记录以下日志：

```
[INFO] [trace-xxx] 群 111111 属于 UMO Group，重定向报告至: onebot:GroupMessage:999999
[INFO] [trace-xxx] 报告将发送至: platform=onebot, group=999999
```

### 无效 output_umo 格式

如果 `output_umo` 格式不正确（例如缺少部分），会记录调试日志：

```
[DEBUG] [trace-xxx] 无法解析目标 UMO 'invalid-format'，预期格式为 'platform:type:group_id'，
将回退到原始 group_id=111111 / platform_id=onebot
```

这种情况下，报告会回退到原始的群组，而不是静默失败。

## API 参考

### 新增方法

#### `find_all_umo_groups_for_source(source_umo: str) -> list[dict]`

查找一个 UMO 所属的**所有** UMO Group（而非仅第一个）。

**用途**：
- 诊断多重成员关系问题
- 实现自定义的多目标分发逻辑

**示例**：

```python
groups = config_manager.find_all_umo_groups_for_source("onebot:GroupMessage:111111")
if len(groups) > 1:
    logger.warning(f"UMO 属于 {len(groups)} 个 Group: {[g['group_id'] for g in groups]}")
```

### 更新的方法文档

#### `get_report_destinations(source_umo: str, include_source_if_group_member: bool = True) -> list[str]`

**新增说明**：
- 返回所有匹配 UMO Group 的 `output_umo`，按配置顺序去重
- 当 `include_source_if_group_member=True` 且命中 `dual_send_source_umos` 时，会附加原始 UMO

> 兼容性：`get_report_destination_umo` 仍然存在，但仅返回首个目标。

## 总结

### 关键要点

1. **仍建议一个 UMO 只属于一个 UMO Group**，但系统已支持多 Group 广播（去重）
2. **需要自发+聚合的 UMO** 可以加入 `dual_send_source_umos`
3. **关注配置加载时的提示日志**，确认是否存在多重成员关系
4. **所有匹配逻辑统一**，名单过滤与分发行为一致、可预测

### 未来改进方向

可能的功能增强（待讨论）：
- 支持 UMO Group 优先级配置（`priority` 字段）
- 支持多目标发送（`output_umos` 数组）
- 支持条件发送（仅聚合或仅独立）

如有需求或建议，欢迎在 GitHub Issues 中讨论。
