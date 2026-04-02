# UMO Group 功能使用指南

## 概述

UMO Group（Unified Message Origin Group）是一个强大的功能，允许您将多个消息来源（UMO）聚合为一个虚拟群组进行统一管理和分析。

### 核心概念

- **UMO (Unified Message Origin)**: 消息的统一来源标识，格式为 `平台ID:消息类型:群组ID`，例如 `onebot:GroupMessage:123456`
- **UMO Group**: 一个虚拟的消息聚合体，包含：
  - **Group ID**: 唯一标识符
  - **Source UMOs**: 多个来源 UMO 列表
  - **Output UMO**: 报告输出目标

## 使用场景

1. **跨群组分析**: 将多个相关群组的消息聚合在一起进行统一分析
2. **统一报告输出**: 多个群组的分析报告统一发送到一个指定的群组
3. **灵活的权限管理**: 通过 UMO Group 简化多群组的白名单/黑名单配置

## 配置方法

### 在 WebUI 中配置

1. 打开 AstrBot WebUI
2. 进入插件管理
3. 找到"群日常分析"插件，点击设置
4. 找到"UMO Group 设置"区域
5. 点击"添加"创建新的 UMO Group

### 配置示例

```json
{
  "umo_groups": {
    "groups": [
      {
        "group_id": "tech_groups",
        "source_umos": [
          "onebot:GroupMessage:111111",
          "onebot:GroupMessage:222222",
          "telegram:GroupMessage:333333"
        ],
        "output_umo": "onebot:GroupMessage:999999"
      }
    ]
  }
}
```

在这个示例中：
- 创建了一个名为 `tech_groups` 的 UMO Group
- 它包含 3 个来源群组（2 个 QQ 群 + 1 个 Telegram 群）
- 所有分析报告将发送到群组 `999999`

## 在其他配置中使用 UMO Group

在所有支持配置 UMO 的地方，都可以使用 `_umoGroup:ID` 的格式引用 UMO Group：

### 1. 基础群聊权限

```json
{
  "basic": {
    "group_list_mode": "whitelist",
    "group_list": [
      "_umoGroup:tech_groups",
      "onebot:GroupMessage:444444"
    ]
  }
}
```

### 2. 定时分析群列表

```json
{
  "auto_analysis": {
    "scheduled_group_list_mode": "whitelist",
    "scheduled_group_list": [
      "_umoGroup:tech_groups"
    ]
  }
}
```

### 3. 增量分析群列表

```json
{
  "incremental": {
    "incremental_group_list_mode": "whitelist",
    "incremental_group_list": [
      "_umoGroup:tech_groups"
    ]
  }
}
```

## 工作原理

### 消息处理

当一条消息来自某个 UMO（例如 `onebot:GroupMessage:111111`）时：

1. **权限检查**: 系统会检查：
   - 该 UMO 是否直接在白名单/黑名单中
   - 该 UMO 是否属于某个在白名单/黑名单中的 UMO Group

2. **分析执行**: 如果该 UMO 属于 UMO Group `tech_groups`，则：
   - 消息会被当作来自该群组的消息进行处理
   - 同时也会被当作来自 `tech_groups` 的消息进行处理

3. **报告发送**: 分析完成后：
   - 如果该 UMO 属于一个或多个 UMO Group，报告会发送到所有匹配 Group 的 `output_umo`（去重）
   - 如果该 UMO 或其所在的 Group 在 `dual_send_source_umos` 中，也会额外发送到原始的 UMO
   - 如果未命中任何 Group，则发送到原始群组（保持向后兼容）

### 兼容性

UMO Group 功能完全向后兼容：
- 不配置 UMO Group 时，插件行为与之前完全一致
- 现有的 UMO 配置仍然有效
- UMO 和 UMO Group 可以混合使用

## 高级用法

### 多层次管理

您可以为不同的群组类型创建不同的 UMO Group：

```json
{
  "umo_groups": {
    "groups": [
      {
        "group_id": "tech_groups",
        "source_umos": ["onebot:GroupMessage:111111", "onebot:GroupMessage:222222"],
        "output_umo": "onebot:GroupMessage:999991"
      },
      {
        "group_id": "gaming_groups",
        "source_umos": ["onebot:GroupMessage:333333", "onebot:GroupMessage:444444"],
        "output_umo": "onebot:GroupMessage:999992"
      },
      {
        "group_id": "all_managed",
        "source_umos": ["onebot:GroupMessage:555555", "telegram:GroupMessage:666666"],
        "output_umo": "onebot:GroupMessage:999993"
      }
    ]
  }
}
```

然后在基础权限中：

```json
{
  "basic": {
    "group_list_mode": "whitelist",
    "group_list": [
      "_umoGroup:tech_groups",
      "_umoGroup:gaming_groups"
    ]
  }
}
```

### 黑名单模式

在黑名单模式下，也可以使用 UMO Group：

```json
{
  "basic": {
    "group_list_mode": "blacklist",
    "group_list": [
      "_umoGroup:restricted_groups"
    ]
  }
}
```

这样，`restricted_groups` 中的所有 source_umos 都会被排除。

### 双重发送（同时发到 Group 与自身）

当某个群既需要聚合到管理群，又要保留自己的报告时，可以在 `dual_send_source_umos` 中声明：

```json
{
  "umo_groups": {
    "groups": [
      {
        "group_id": "tech_groups",
        "source_umos": ["onebot:GroupMessage:111111"],
        "output_umo": "onebot:GroupMessage:999991"
      }
    ],
    "dual_send_source_umos": [
      "onebot:GroupMessage:111111",
      "_umoGroup:tech_groups"
    ]
  }
}
```

- 命中列表的 UMO 会在发送到 `output_umo` 的同时，再发送一份到自身
- 支持填写完整 UMO、简单群号或 `_umoGroup:ID`，方便批量开启

## 注意事项

1. **Group ID 唯一性**: 每个 UMO Group 的 `group_id` 必须唯一
2. **UMO 格式**: Source UMOs 和 Output UMO 都必须使用完整的 UMO 格式（`平台:类型:ID`）
3. **Output UMO 有效性**: 确保 output_umo 指向一个 Bot 有权限发送消息的群组
4. **不支持循环引用**: UMO Group 不支持嵌套或循环引用
5. **多重成员关系会广播**: 同一个 UMO 属于多个 UMO Group 时，会向所有匹配的 `output_umo` 发送（去重），请确认是否符合预期

## 获取 UMO

如果您不确定某个群组的 UMO，可以：

1. 在目标群组中发送 `/sid` 命令（如果 AstrBot 支持）
2. 查看 AstrBot 的日志，其中包含 UMO 信息
3. UMO 格式通常为：
   - QQ (OneBot): `onebot:GroupMessage:群号`
   - Telegram: `telegram:GroupMessage:群组ID`
   - 其他平台类似

## 故障排除

### 报告没有发送到指定的 output_umo

检查：
1. output_umo 的格式是否正确
2. Bot 是否在 output_umo 指定的群组中
3. Bot 是否有该群组的发送权限

### UMO Group 似乎没有生效

检查：
1. group_id 是否拼写正确（使用 `_umoGroup:ID` 格式）
2. source_umos 中的 UMO 格式是否正确
3. 查看日志中是否有相关错误信息

### 无法在配置界面看到 UMO Group 设置

确保您的 AstrBot 插件版本支持 UMO Group 功能（需要 v4.9.12 或更高版本）。

## 示例场景

### 场景 1: 公司多个技术交流群统一管理

有 3 个技术交流群（前端群、后端群、运维群），希望：
- 每天生成一份聚合报告
- 报告发送到管理群

配置：
```json
{
  "umo_groups": {
    "groups": [
      {
        "group_id": "tech_all",
        "source_umos": [
          "onebot:GroupMessage:10001",
          "onebot:GroupMessage:10002",
          "onebot:GroupMessage:10003"
        ],
        "output_umo": "onebot:GroupMessage:90001"
      }
    ]
  },
  "auto_analysis": {
    "scheduled_group_list": ["_umoGroup:tech_all"]
  }
}
```

### 场景 2: 跨平台群组管理

同时管理 QQ 群和 Telegram 群：

```json
{
  "umo_groups": {
    "groups": [
      {
        "group_id": "community",
        "source_umos": [
          "onebot:GroupMessage:123456",
          "telegram:GroupMessage:-1001234567890"
        ],
        "output_umo": "onebot:GroupMessage:999999"
      }
    ]
  }
}
```

## 总结

UMO Group 功能提供了灵活而强大的群组管理能力，使得多群组的统一分析和管理变得简单高效。通过合理配置，您可以：

- 简化多群组的权限管理
- 实现跨群组的统一分析
- 灵活控制报告的输出目标

如有任何问题，欢迎在 GitHub Issues 中反馈。
