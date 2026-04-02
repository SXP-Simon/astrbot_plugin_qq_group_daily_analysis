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

- 配置加载时，系统会通过 `_validate_umo_groups()` 检测并**记录警告日志**
- 在运行时，`find_umo_group_for_source()` 和 `get_report_destination_umo()` 会返回**第一个匹配的 Group**
- "第一个"由配置文件中 Group 的定义顺序决定（上例中为 `tech_all`）

#### 最佳实践

**推荐做法**：确保每个 UMO 只属于一个 UMO Group

如果确实需要一个 UMO 的报告发送到多个目标：
1. 只将该 UMO 放入一个 UMO Group
2. 在应用层实现额外的分发逻辑（例如通过自定义插件）

### 2. UMO 既属于 Group 又需要独立报告

#### 问题描述

某些场景下，你可能希望：
- 一个 UMO 的消息被聚合到 UMO Group 进行统一分析
- 同时，该 UMO 也需要生成并发送自己的独立报告

例如：
- 群 A、B、C 聚合分析，报告发送到管理群 M
- 但群 A 同时也需要接收自己的独立报告

#### 当前行为

当前实现中，如果一个 UMO 属于某个 UMO Group：
- 报告会自动重定向到该 Group 的 `output_umo`
- **不会**再发送到原始 UMO

这是因为 `get_report_destination_umo()` 会优先返回 Group 的 `output_umo`。

#### 解决方案

目前有两种方案：

**方案 1：分离配置（推荐）**

不将需要独立报告的 UMO 加入 UMO Group：

```json
{
  "umo_groups": {
    "groups": [
      {
        "group_id": "tech_all",
        "source_umos": [
          "onebot:GroupMessage:222222",  // 只包含 B、C
          "onebot:GroupMessage:333333"
        ],
        "output_umo": "onebot:GroupMessage:999999"
      }
    ]
  },
  "auto_analysis": {
    "scheduled_group_list": [
      "_umoGroup:tech_all",
      "onebot:GroupMessage:111111"  // A 单独配置
    ]
  }
}
```

这样，群 A 会生成自己的独立报告，而群 B、C 的报告会聚合发送到群 M。

**方案 2：应用层实现双重发送（高级）**

如果需要真正的"既聚合又独立"，需要在调用方实现额外逻辑：

```python
# 伪代码示例
def send_report_with_dual_output(source_umo, report):
    # 1. 发送到 UMO Group 的 output_umo
    dest_umo = config.get_report_destination_umo(source_umo)
    await send_report_to(dest_umo, report)

    # 2. 如果 source_umo 在特殊列表中，也发送到其自身
    if source_umo in DUAL_OUTPUT_UMOS:
        await send_report_to(source_umo, report)
```

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

#### `get_report_destination_umo(source_umo: str) -> str`

**新增说明**：
- 明确多重成员关系时返回第一个匹配 Group 的 output_umo
- 明确不会同时发送到 Group 和原始 UMO

详见方法文档字符串。

## 总结

### 关键要点

1. **每个 UMO 应只属于一个 UMO Group**（强烈建议）
2. **如需独立报告，不要将 UMO 加入 Group**，或实现自定义分发逻辑
3. **关注配置加载时的警告日志**，及时修正配置
4. **所有匹配逻辑已统一**，行为一致且可预测

### 未来改进方向

可能的功能增强（待讨论）：
- 支持 UMO Group 优先级配置（`priority` 字段）
- 支持多目标发送（`output_umos` 数组）
- 支持条件发送（仅聚合或仅独立）

如有需求或建议，欢迎在 GitHub Issues 中讨论。
