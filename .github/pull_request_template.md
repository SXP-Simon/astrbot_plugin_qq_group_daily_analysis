## 📝 变更说明 (Summary)
<!-- 请简要描述此 PR 的主要目的与核心变更 -->

### 🎯 变更背景与三段论描述
<!-- 提示：新特性/新模板/重构请如实阐述业务背景与设计动机；缺陷修复请阐明真实故障根因。无需硬编造假问题！ -->
- **背景/问题 (Background/Problem)**：
- **实现方案/解决措施 (Implementation/Action)**：
- **效果/收益 (Result/Value)**：

---

## 🔗 关联 Issue (Related Issue)
<!-- 如果有关联的 issue，请填写例如 Closes #123 或 Fixes #456 -->
- Closes #
- Fixes #

---

## 📦 变更类型 (Type of Change)
<!-- 请勾选适用的选项（将 [ ] 替换为 [x]） -->
- [ ] ✨ `feat`: 新增功能 / 新增 WebUI 模块 / 新增报告模板
- [ ] 🐛 `fix`: 修复 Bug / 异常处理
- [ ] 📚 `docs`: 文档或注释更新
- [ ] 💄 `style` / ♻️ `refactor`: 代码重构 / UI 样式调整
- [ ] ⚡ `perf`: 性能优化
- [ ] 🧪 `test`: 增加或修改单元测试 / 冒烟测试
- [ ] 🔧 `chore` / 👷 `ci`: 构建流程 / 工作流 / 依赖包版本变动

---

## 📋 提交前自检清单 (Checklist)
<!-- 请在提交前逐一确认已完成自检 -->
- [ ] **提交规范**：Git Commit Message 与 PR 描述符合 Conventional Commits 标准（包含中文“背景(或问题)/方案/效果”三段论，且描述客观详实）
- [ ] **跨端契约一致性**（若涉及后端 API 变更）：已运行 `python scripts/export_openapi.py` 并同步更新前端类型（`pnpm generate:types`）
- [ ] **前端验证**（若涉及 WebUI）：已在 `dashboard/` 目录下运行 `pnpm test` 与 `pnpm build` 确认无报错
- [ ] **后端质量**（若涉及 Python 代码）：已通过 `ruff check`、`ruff format` 与 `pytest` 校验
- [ ] **本地门禁自检**：本地执行 `npx lefthook run pre-commit` 全项通过
