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
   - 禁止显式 `Any`（包括别名、变量及容器成员），由 Ruff `TID251` 与 `ANN401` 检查。使用具体模型、TypedDict、Protocol、Union 或 `object` 配合类型守卫（`isinstance` / `callable` 等）。
   - 杜绝非必要的 `# type: ignore`，优先通过精准的类型注解解决类型推导问题。
   - 宽类型仅用于外部数据入口和确实开放的原始数据；领域层及应用层业务契约必须明确。边界校验后再进入内部，不用批量 `cast` 绕过检查。详见 CONTRIBUTING.md 的“类型边界与自动检查”。
2. **静态检查与格式化**：
   - 按改动范围验证；准备 PR 或完成一组改动时，相关静态检查必须通过：
     ```bash
     uv run python scripts/check_python.py lint .
     uv run python scripts/check_python.py format . --check
     uv run python scripts/check_python.py typecheck src main.py
     ```
   - 保持 **0 errors, 0 warnings**。
3. **自动化测试**：
   - 开发时运行受影响的定向测试，新增功能或重构需补充相应测试。准备后端 PR 或完成一组后端改动时运行完整测试：
     ```bash
     uv run pytest tests/
     ```
   - **避免重复验证**：同一份代码、测试、依赖及配置已经通过的检查，不得仅因 `git add`、原子提交、改提交说明或纯文档变更再运行。随后有影响相关结果的改动、失败或新的疑点时，才重新验证对应范围。仅跑定向测试不能代替完整测试；记录实际命令及结果，不宣称未执行的检查通过。
   - 日常 commit 只运行 Lefthook 的暂存文件快速检查，push 不绑定完整检查。手动检查可按步骤执行，例如 `npx lefthook run check-python --command lint --command typecheck`，不会重复已完成的 pytest。
   - CI 在独立环境完整验证，不依据本地“已通过”声明跳过；发布构建验证发布环境及产物，不视为本地重复工作。

---

## 4. 架构与设计原则 (Good Taste 架构准则)

1. **领域驱动设计 (DDD) 与领域类型优先**：
   - 保持分层清晰：`domain`（核心业务实体与值对象）、`application`（用例服务）、`infrastructure`（平台适配、持久化、WebUI 路由）、`interfaces`（契约协议）。
   - **插件内部纯强类型化**：插件业务链路（`domain/`, `application/`, `infrastructure/` 内部各模块）必须 100% 使用明确的领域实体（Entities）、不可变值对象（Value Objects）、强类型 DTO 与 Protocol 契约，严禁设立模糊的 `models/` 目录。
   - **插件内部严禁不必要反射**：严禁在插件内部模块间使用 `getattr`/`hasattr`/`setattr` 或传递模糊的 `object`/`dict`/`Any`；所有调用在静态类型期必须清晰可解析。
2. **防腐层 (ACL) 规范与 AstrBot F12 直达开发体验**：
   - **只做“必要的反射”**：反射仅允许出现在基础设施防腐层（如 `infrastructure/platform/`, `infrastructure/webui/`）与 AstrBot 宿主框架交互的边界处，用于防御跨版本 API 变动、单测 Mock 桩及框架未初始化场景。
   - **兼顾运行时防腐与开发期 F12 直达**：严禁因为使用 `getattr` 防腐就放弃静态类型。必须在 `if TYPE_CHECKING:` 下引入 AstrBot 官方类型（如 `Context`, `AstrBotConfigManager`, `PlatformManager`, `ProviderManager`, `PersonaManager` 等），并在局部变量上显式声明强类型（如 `acm: AstrBotConfigManager | None = getattr(self._context, "astrbot_config_mgr", None)`）。
   - 确保开发者在 IDE 中对宿主属性或方法按 **F12** 可以 100% 直达 AstrBot 官方源码与类型签名。
3. **KISS 原则与实用主义 (Inline-First)**：
   - 优先在线性主流程中实现紧凑逻辑，避免无意义的过度抽象，非必要不设立单次使用的 Helper 函数。
4. **文件与报告规则**：
   - 严禁在仓库中生成如 `xxx_SUMMARY.md` 等冗余报告文件。
