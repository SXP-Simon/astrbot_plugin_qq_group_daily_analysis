# GitHub Actions 工作流说明

## 自动发布工作流 (auto-release.yml)

### 功能概述

此工作流会自动检测 `metadata.yaml` 文件中的 `version` 字段变化，当检测到版本号更新时，自动创建一个新的 GitHub Release。

### 触发条件

- 当向 `main` 分支推送提交时
- 且该提交修改了 `metadata.yaml` 文件

### 工作流程

1. **检查版本变化**
   - 提取当前 `metadata.yaml` 中的版本号
   - 对比上一次提交的版本号
   - 判断版本是否发生变化

2. **生成变更日志**
   - 如果版本已更新，自动生成变更日志
   - 根据提交信息的前缀自动分类：
     - `feat:` / `feature:` → ✨ Feature（新功能）
     - `fix:` → 🐛 Fix（修复）
     - `docs:` → 📚 Docs（文档）
     - `refactor:` / `style:` / `perf:` / `test:` / `chore:` → 🔧 其他改进
     - 其他 → 📌 普通提交

3. **创建 Release**
   - 使用新版本号作为标签名
   - 附带自动生成的变更日志
   - 提供版本对比链接

### 使用方法

1. **更新版本号**
   
   编辑 `metadata.yaml` 文件，修改 `version` 字段：
   ```yaml
   version: v0.5.3  # 从 v0.5.2 更新到 v0.5.3
   ```

2. **提交并推送**
   ```bash
   git add metadata.yaml
   git commit -m "chore: bump version to v0.5.3"
   git push origin main
   ```

3. **自动发布**
   
   工作流会自动触发并创建 Release，无需手动操作。

### 最佳实践

#### 提交信息格式

为了获得更好的变更日志，建议使用语义化的提交信息格式：

```
<type>: <description>

[optional body]
```

**类型示例：**
- `feat:` 添加新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `refactor:` 代码重构
- `perf:` 性能优化
- `test:` 测试相关
- `chore:` 构建/工具/依赖更新

**示例：**
```bash
git commit -m "feat: 添加向量搜索功能"
git commit -m "fix: 修复内存泄漏问题"
git commit -m "docs: 更新 API 文档"
```

#### 版本号规范

建议遵循语义化版本控制 (Semantic Versioning)：

- `vX.Y.Z` 格式
- `X`：主版本号（重大变更）
- `Y`：次版本号（新功能）
- `Z`：修订号（bug 修复）

**示例：**
- `v0.5.2` → `v0.5.3`（bug 修复）
- `v0.5.3` → `v0.6.0`（新功能）
- `v0.6.0` → `v1.0.0`（重大变更）

### 权限要求

工作流需要以下权限：
- `contents: write` - 用于创建 Release 和标签

这些权限已在工作流文件中配置，GitHub Actions 会自动提供。

### 注意事项

1. 确保每次更新版本号时，版本号是递增的
2. 避免在同一次提交中多次修改版本号
3. 如果 Release 创建失败，检查：
   - 该版本标签是否已存在
   - 仓库是否启用了 GitHub Actions
   - 权限设置是否正确

### 查看工作流运行状态

在 GitHub 仓库页面：
1. 点击 "Actions" 标签
2. 查看 "Auto Release on Version Update" 工作流
3. 点击具体的运行记录查看详细日志

### 手动触发（可选）

如需手动创建 Release，可以：
1. 在 GitHub 仓库页面点击 "Releases"
2. 点击 "Draft a new release"
3. 手动填写版本信息和变更日志

但推荐使用自动化工作流以保持一致性。