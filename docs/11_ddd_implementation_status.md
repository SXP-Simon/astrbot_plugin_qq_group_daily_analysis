# 11. DDD 重构实施状态文档 (DDD Refactoring Implementation Status)

> **文档日期**: 2026-02-08
> **版本**: v1.0
> **状态**: 实施中

---

## 1. 实施概述

### 1.1 架构决策记录 (ADR)

#### ADR-001: 采用渐进式集成而非完全重构

**背景**: 原计划对所有分析器进行完全重构以使用 UnifiedMessage 格式。

**决策**: 采用渐进式集成方式：
- 新建 DDD 分层结构 (domain/infrastructure/application)
- 现有分析器代码保持不变
- 通过 MessageConverter 提供双向转换
- AnalysisOrchestrator 作为新旧代码的桥梁

**原因**:
1. 现有分析器代码已经稳定运行
2. 完全重构风险高，可能引入新 bug
3. 渐进式迁移允许逐步验证
4. 保持向后兼容性

**后果**:
- 正面：风险低，可逐步迁移
- 负面：短期内存在两套消息格式

---

## 2. 已实现的架构层

### 2.1 领域层 (Domain Layer) ✅

```
src/domain/
├── __init__.py
├── entities/
│   ├── __init__.py
│   ├── analysis_task.py      # 分析任务聚合根
│   └── analysis_result.py    # 分析结果实体
├── value_objects/
│   ├── __init__.py
│   ├── unified_message.py    # 统一消息格式 (核心)
│   ├── platform_capabilities.py  # 平台能力声明
│   └── unified_group.py      # 统一群组/成员信息
└── repositories/
    ├── __init__.py
    ├── message_repository.py # IMessageRepository, IMessageSender, IGroupInfoRepository
    └── avatar_repository.py  # IAvatarRepository
```

**关键设计**:
- `UnifiedMessage`: 不可变值对象，所有平台消息的统一抽象
- `PlatformCapabilities`: 声明式能力描述，支持运行时能力检查
- Repository 接口：定义平台无关的数据访问契约

### 2.2 基础设施层 (Infrastructure Layer) ✅

```
src/infrastructure/
├── __init__.py
└── platform/
    ├── __init__.py
    ├── base.py               # PlatformAdapter 基类
    ├── factory.py            # PlatformAdapterFactory 工厂
    └── adapters/
        ├── __init__.py
        └── onebot_adapter.py # OneBot v11 完整实现
```

**关键设计**:
- `PlatformAdapter`: 组合所有 Repository 接口的抽象基类
- `OneBotAdapter`: 完整实现消息获取、发送、群组信息、头像获取
- `PlatformAdapterFactory`: 注册表模式，支持动态添加新平台

**支持的平台**:
- ✅ OneBot v11 (aiocqhttp) - 完整实现
- 🔲 Telegram - 预留接口
- 🔲 Discord - 预留接口
- 🔲 Slack - 预留接口

### 2.3 应用层 (Application Layer) ✅

```
src/application/
├── __init__.py
├── analysis_orchestrator.py  # 分析流程编排器
└── message_converter.py      # 消息格式转换器
```

**关键设计**:
- `AnalysisOrchestrator`: 
  - 使用 PlatformAdapter 获取消息 (DDD 方式)
  - 提供 `fetch_messages_as_raw()` 兼容现有分析器
  - 封装平台能力检查逻辑
  
- `MessageConverter`:
  - `from_onebot_message()`: OneBot dict → UnifiedMessage
  - `to_onebot_message()`: UnifiedMessage → OneBot dict
  - `unified_to_analysis_text()`: 生成 LLM 分析用文本

---

## 3. 与原设计文档的差异

### 3.1 文档 09 vs 实际实现

| 原设计 | 实际实现 | 原因 |
|--------|----------|------|
| 完全重构分析器 | 保持现有分析器 | 风险控制 |
| main.py 使用 AstrMessageEvent | 保持 AiocqhttpMessageEvent | 渐进式迁移 |
| 所有分析使用 UnifiedMessage | 通过 Converter 兼容 | 向后兼容 |

### 3.2 后续迁移路径

1. **Phase 1 (当前)**: DDD 基础架构就位，现有代码不变
2. **Phase 2**: 新功能使用 DDD 架构开发
3. **Phase 3**: 逐步将现有分析器迁移到 UnifiedMessage
4. **Phase 4**: 移除 MessageConverter，完成迁移

---

## 4. 验证状态

### 4.1 Docker 容器验证 ✅

```bash
# 验证命令
docker exec astrbot python -c "
from src.domain.value_objects import UnifiedMessage, PlatformCapabilities
from src.infrastructure.platform import PlatformAdapterFactory
from src.application import AnalysisOrchestrator, MessageConverter
print('All imports successful!')
print(f'Supported platforms: {PlatformAdapterFactory.get_supported_platforms()}')
"

# 输出
All DDD layer imports successful!
Supported platforms: ['aiocqhttp', 'onebot']
```

### 4.2 待验证项

- [ ] 完整分析流程端到端测试
- [ ] OneBotAdapter 消息获取实际测试
- [ ] 报告生成与发送测试

---

## 5. 使用指南

### 5.1 新代码使用 DDD 架构

```python
from src.infrastructure.platform import PlatformAdapterFactory
from src.application import AnalysisOrchestrator, AnalysisConfig

# 创建适配器
adapter = PlatformAdapterFactory.create("aiocqhttp", bot_instance, config)

# 创建编排器
orchestrator = AnalysisOrchestrator(adapter, AnalysisConfig(days=1))

# 检查能力
if orchestrator.can_analyze():
    # 获取统一格式消息
    messages = await orchestrator.fetch_messages(group_id)
    
    # 或获取原始格式 (兼容现有分析器)
    raw_messages = await orchestrator.fetch_messages_as_raw(group_id)
```

### 5.2 现有代码保持不变

现有的 `MessageHandler`, `MessageAnalyzer`, `LLMAnalyzer` 等继续使用原始 dict 格式，无需修改。

---

## 6. Git 提交记录

| Commit | 描述 |
|--------|------|
| `c1d3bf5` | feat: add DDD architecture layers (domain, infrastructure, application) |

---

## 7. 下一步计划

1. 添加更多平台适配器 (Telegram, Discord)
2. 将 `main.py` 中的平台检测逻辑迁移到使用 `PlatformAdapterFactory`
3. 为新功能使用 `AnalysisOrchestrator` 作为入口
4. 编写单元测试覆盖 DDD 层
