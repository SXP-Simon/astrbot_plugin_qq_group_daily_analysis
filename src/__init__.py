"""
QQ群日常分析插件 - 源代码包

本包包含插件的核心实现，采用 DDD (领域驱动设计) 架构：
- application: 应用层 - 编排领域服务，处理用例
- domain: 领域层 - 核心业务逻辑，平台无关
- infrastructure: 基础设施层 - 外部服务适配
- shared: 共享组件 - 跨层使用的工具和常量

遗留模块（渐进式迁移中）：
- analysis: 分析器实现
- core: 核心组件
- reports: 报告生成
- scheduler: 定时任务
- utils: 工具函数
- visualization: 可视化组件
"""
