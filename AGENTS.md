# AstrBot QQ 群日常分析插件开发规范与 Agent 规则

本项目是 AstrBot 的 QQ 群聊日常总结与分析插件（`astrbot_plugin_qq_group_daily_analysis`）。

> [!IMPORTANT]
> **开发前必读**：请在进行任何架构重构、功能扩展或代码修改前，务必参考项目根目录的权威指南 [`CONTRIBUTING.md`](CONTRIBUTING.md)。
> 本文件为面向 AI Coding Agent 的核心准则精炼与指引索引。

---

## 1. 指南索引与权威来源

详尽规范请查阅 [`CONTRIBUTING.md`](CONTRIBUTING.md)：
* **后端规范与类型体操**：见 `CONTRIBUTING.md` 第 2.1 节（内联优先、强制中文 Google Docstring、Pyright 严格模式、Zero `Any`、DDD 领域分层）；
* **WebUI 前端规范**：见 `CONTRIBUTING.md` 第 2.2 节（FSD 分层、MVVM 状态解耦、Zero `any`、单 Bundle 产物）；
* **报告模板系统与离线调试**：见 `CONTRIBUTING.md` 第 3 节 及 `docs/REPORT_TEMPLATE_GUIDE.md`（7 件套组件、模板变量表、`scripts/debug_render.py` 离线渲染器）；
* **提交信息与 PR 流程**：见 `CONTRIBUTING.md` 第 4 与第 5 节。

---

## 2. 语言与文档规范

1. **中文注释与文档字符串 (Docstrings)**：
   - 仓库内所有代码注释、文档字符串必须使用 **中文** 编写。
   - 函数和方法的 Docstring 严格遵循 **Google 风格**（包含 `Args:`, `Returns:`, `Raises:`）。
2. **中文 Commit Message**：
   - Git 提交信息必须遵循 Conventional Commits 规范，正文说明使用 **中文**。
   - 示例：`feat: 支持 Telegram 消息分页拉取`、`fix: 修复 OneBot 动态代理属性误判问题`、`refactor: 优化 WebUI 路由响应类型定义`。
3. **中文日志与终端输出**：
   - 插件业务日志及 WebUI 界面提示文字统一使用 **中文**。

---

## 3. 门禁与代码质量规范

1. **类型安全与 Zero `Any` 政策**：
   - 严格避免随意使用 `Any` 类型。使用具体模型、TypedDict、Protocol、Union 或 `object` 配合类型守卫（`isinstance` / `callable` 等）。
   - 杜绝非必要的 `# type: ignore`，优先通过精准的类型注解解决类型推导问题。
2. **静态检查与格式化**：
   - 提交前必须通过：
     ```bash
     uv run ruff check .
     uv run ruff format . --check
     npx pyright src main.py
     ```
   - 保持 **0 errors, 0 warnings**。
3. **自动化测试**：
   - 保持所有单元测试与集成测试（Pytest）100% 通过，添加新功能或重构时需补充相应测试用例，严禁测试回归：
     ```bash
     uv run pytest
     ```

---

## 4. 架构与设计原则

1. **领域驱动设计 (DDD)**：
   - 保持分层清晰：`domain`（核心业务实体与值对象）、`application`（用例服务）、`infrastructure`（平台适配、持久化、WebUI 路由）、`interfaces`（契约协议）。
2. **KISS 原则与实用主义 (Inline-First)**：
   - 优先在线性主流程中实现紧凑逻辑，避免无意义的过度抽象，非必要不设立单次使用的 Helper 函数。
3. **文件与报告规则**：
   - 严禁在仓库中生成如 `xxx_SUMMARY.md` 等冗余报告文件。
