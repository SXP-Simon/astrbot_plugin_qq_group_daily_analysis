#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

// ============================================================================
// 1. DDD 架构分层、业务子领域与前端 FSD 架构 Scope 结构化分类定义
// ============================================================================
const SCOPE_CATEGORIES = {
  '🏛️ 后端 DDD 架构分层 (Backend DDD Architectural Layers)': {
    domain: '领域层核心 (Entities, Value Objects, 仓储抽象契约, 领域事件)',
    app: '应用层 (用例编排, Application Services, Handlers, DTO)',
    application: '应用层完整别名 (同 app)',
    infra: '基础设施层 (平台适配器, 防腐层 ACL, 数据库/存储, LLM 驱动)',
    infrastructure: '基础设施层完整别名 (同 infra)',
    'infra/webui': 'Web 控制台后端路由与通信适配 (src/infrastructure/webui/)',
    'infra/routes': '后端 WebAPI 路由处理器别名 (同 infra/webui)',
    'infra/api': '后端 WebAPI 接口协议适配别名 (同 infra/webui)',
  },
  '🎯 后端业务子领域 (Backend Sub-domains)': {
    analysis: '分析子域 (LLM 分析器, 文本聚合, 情绪/质量/统计分析)',
    comic: '漫画子域 (分镜解析, 提示词引擎, 图像生成与相册流转)',
    reporting: '报告渲染子域 (HTML/Image 渲染引擎, 主题模板, 排版系统)',
    render: '渲染引擎别名 (同 reporting)',
    platform: '多平台通信子域 (OneBot, QQOfficial, Telegram, Discord 适配)',
    scheduler: '调度与恢复子域 (Cron 任务, 增量分析, 熔断恢复, TaskGuard)',
    config: '配置子域 (配置项管理, 动态热重载, Schema 校验)',
  },
  '🎨 前端 FSD 架构分层与切片 (Frontend Feature-Sliced Design)': {
    dashboard: '前端 Dashboard 全栈 (dashboard/ 源码与 pages/ 静态构建产物)',
    webui: '前端 WebUI 控制台全栈别名 (同 dashboard，支持 build(webui) 打包构建)',
    'webui/app': 'FSD App 层 (应用根入口, Providers, 全局主题与样式)',
    'webui/pages': 'FSD 页面层 (Overview, Traces, Reports, Config, Logs 等整页编排)',
    'webui/widgets': 'FSD 小部件层 (ActiveTaskBoard, TrendCharts, TraceDrawer, ConfigForm 等)',
    'webui/features': 'FSD 特征交互层 (TriggerTask, CancelTask, RerenderReport, InstallTemplate 等)',
    'webui/entities': 'FSD 业务实体层 (Task, Trace, Report, Config, Group 状态与数据模型)',
    'webui/shared': 'FSD 共享基建层 (UI 基础组件 StatusTag/MetricCard, API Client, Hooks, 工具库)',
    'webui/tasks': 'FSD 任务业务切片 (对应 entities/task, features/trigger-task, widgets/active-task-board)',
    'webui/traces': 'FSD 追踪业务切片 (对应 entities/trace, widgets/trace-table, widgets/trace-drawer)',
    'webui/reports': 'FSD 报告业务切片 (对应 entities/report, features/rerender-report, widgets/report-preview-modal)',
    'webui/charts': 'FSD 图表业务切片 (对应 widgets/trend-charts, widgets/token-chart-widget)',
    'webui/config': 'FSD 配置业务切片 (对应 entities/config, widgets/config-form, features/install-template)',
  },
  '🛠️ 工程与基建 (Engineering & Infrastructure)': {
    'ci/github-actions': 'GitHub Actions 工作流与 CI 配置',
    'ci/lefthook': 'Lefthook 本地 Git Hooks 门禁配置',
    'ci/workflow': 'CI/CD 工作流与自动化流水线',
    'ci/scripts': '工程构建/检查/校验脚本',
    'ci/pipeline': '持续集成流水线与代码质量门禁',
    'test/unit': '单元测试与桩代码',
    'test/e2e': '端到端集成测试',
    'test/infra': '测试基建与持久化 Mock 桩',
    'test/webui': 'WebUI 路由与前端桥接单测',
    deps: '依赖管理 (第三方库版本升级, uv/pip/pnpm 依赖锁)',
    docs: '文档 (架构设计, 接口文档, 开发者指南)',
    'docs/release': '版本发布说明与更新日志 (CHANGELOG.md, metadata.yaml)',
    'docs/arch': 'DDD/FSD 架构设计文档',
    core: '核心协议与规范 (基础常量, 全局上下文, 通用基建)',
    spec: '设计规范与契约定义',
  },
};

// 扁平化所有明确注册的合法 Scope
const ALLOWED_SCOPES = Object.values(SCOPE_CATEGORIES).flatMap((cat) => Object.keys(cat));

// 合法层级前缀（用于支持复合层级/子域表达，如 domain/analysis, infra/platform, app/comic, webui/widgets, test/unit, ci/scripts, docs/release）
const ALLOWED_LAYER_PREFIXES = ['domain', 'app', 'application', 'infra', 'infrastructure', 'webui', 'test', 'tests', 'ci', 'docs'];
const ALLOWED_SUBDOMAINS = [
  'analysis', 'comic', 'reporting', 'render', 'platform', 'scheduler', 'config',
  'app', 'pages', 'widgets', 'features', 'entities', 'shared',
  'dashboard', 'tasks', 'traces', 'reports', 'charts', 'settings', 'templates', 'logs', 'components', 'common',
  'unit', 'e2e', 'infra', 'mocks', 'github-actions', 'lefthook', 'workflow', 'scripts', 'pipeline', 'pre-commit', 'gate', 'arch', 'release'
];

function isScopeValid(scope) {
  if (!scope) return false;
  if (ALLOWED_SCOPES.includes(scope)) return true;
  // 支持复合形式：<layer>/<subdomain>
  if (scope.includes('/')) {
    const [layer, sub] = scope.split('/');
    if (ALLOWED_LAYER_PREFIXES.includes(layer) && ALLOWED_SUBDOMAINS.includes(sub)) {
      return true;
    }
  }
  // 支持直接传入合法的 DDD/FSD 子域或工程子模块
  if (ALLOWED_SUBDOMAINS.includes(scope)) {
    return true;
  }
  return false;
}

// 路径匹配规则集（精确对齐 DDD 与 FSD 物理目录）
const SCOPE_PATH_RULES = [
  {
    matchScope: (s) => s === 'domain' || s.startsWith('domain/'),
    matchFile: (f) => f.startsWith('src/domain/'),
    name: 'domain 领域层 (src/domain/)',
  },
  {
    matchScope: (s) => s === 'app' || s === 'application' || s.startsWith('app/') || s.startsWith('application/'),
    matchFile: (f) => f.startsWith('src/application/'),
    name: 'app 应用层 (src/application/)',
  },
  {
    matchScope: (s) => s === 'platform' || s === 'infra/platform',
    matchFile: (f) => f.startsWith('src/infrastructure/platform/'),
    name: 'platform 平台通信子域 (src/infrastructure/platform/)',
  },
  {
    matchScope: (s) => s === 'webui/pages' || s === 'pages',
    matchFile: (f) => f.startsWith('dashboard/src/pages/'),
    name: 'webui/pages 页面层 (dashboard/src/pages/)',
  },
  {
    matchScope: (s) => s === 'webui/widgets' || s === 'widgets',
    matchFile: (f) => f.startsWith('dashboard/src/widgets/'),
    name: 'webui/widgets 小部件层 (dashboard/src/widgets/)',
  },
  {
    matchScope: (s) => s === 'webui/features' || s === 'features',
    matchFile: (f) => f.startsWith('dashboard/src/features/'),
    name: 'webui/features 特征交互层 (dashboard/src/features/)',
  },
  {
    matchScope: (s) => s === 'webui/entities' || s === 'entities',
    matchFile: (f) => f.startsWith('dashboard/src/entities/'),
    name: 'webui/entities 业务实体层 (dashboard/src/entities/)',
  },
  {
    matchScope: (s) => s === 'webui/shared' || s === 'shared',
    matchFile: (f) => f.startsWith('dashboard/src/shared/'),
    name: 'webui/shared 共享基建层 (dashboard/src/shared/)',
  },
  {
    matchScope: (s) => s === 'webui/app',
    matchFile: (f) => f.startsWith('dashboard/src/app/'),
    name: 'webui/app 应用入口层 (dashboard/src/app/)',
  },
  {
    matchScope: (s) => s === 'webui/tasks' || s === 'tasks',
    matchFile: (f) => f.includes('task') && f.startsWith('dashboard/'),
    name: 'webui/tasks 任务业务切片 (dashboard/src/**/task*)',
  },
  {
    matchScope: (s) => s === 'webui/traces' || s === 'traces',
    matchFile: (f) => f.includes('trace') && f.startsWith('dashboard/'),
    name: 'webui/traces 追踪业务切片 (dashboard/src/**/trace*)',
  },
  {
    matchScope: (s) => s === 'webui/reports' || s === 'reports',
    matchFile: (f) => f.includes('report') && f.startsWith('dashboard/'),
    name: 'webui/reports 报告业务切片 (dashboard/src/**/report*)',
  },
  {
    matchScope: (s) => s === 'webui/charts' || s === 'charts',
    matchFile: (f) => (f.includes('chart') || f.includes('trend')) && f.startsWith('dashboard/'),
    name: 'webui/charts 图表业务切片 (dashboard/src/**/trend-charts*, token-chart*)',
  },
  {
    matchScope: (s) => s === 'webui/config',
    matchFile: (f) => f.includes('config') && f.startsWith('dashboard/'),
    name: 'webui/config 配置业务切片 (dashboard/src/**/config*)',
  },
  {
    matchScope: (s) =>
      s === 'infra/webui' ||
      s === 'infra/routes' ||
      s === 'infra/api' ||
      s === 'routes' ||
      s === 'api' ||
      s === 'openapi',
    matchFile: (f) =>
      f.startsWith('src/infrastructure/webui/') ||
      f === 'openapi.json' ||
      f === 'dashboard/src/shared/api/generated/schema.d.ts',
    name: 'infra/webui 后端 Web 控制台路由与适配层 (src/infrastructure/webui/, openapi.json)',
  },
  {
    matchScope: (s) => s === 'webui' || s.startsWith('webui/') || s === 'dashboard' || s === 'frontend',
    matchFile: (f) =>
      f.startsWith('dashboard/') ||
      f.startsWith('pages/') ||
      f === 'openapi.json',
    name: 'dashboard/webui 前端控制台 (dashboard/, pages/, openapi.json)',
  },
  {
    matchScope: (s) => s === 'infra' || s === 'infrastructure' || s.startsWith('infra/'),
    matchFile: (f) => f.startsWith('src/infrastructure/'),
    name: 'infra 基础设施层 (src/infrastructure/)',
  },
  {
    matchScope: (s) => s === 'analysis' || s.endsWith('/analysis'),
    matchFile: (f) =>
      f.startsWith('src/infrastructure/analysis/') ||
      f.startsWith('src/domain/value_objects/analysis_results.py') ||
      f.startsWith('src/application/services/analysis_') ||
      f.startsWith('src/application/handlers/analysis_') ||
      f.startsWith('src/domain/repositories/analysis_'),
    name: 'analysis 分析子域',
  },
  {
    matchScope: (s) => s === 'comic' || s.endsWith('/comic'),
    matchFile: (f) =>
      f.startsWith('src/infrastructure/analysis/analyzers/comic_') ||
      f.startsWith('src/application/services/comic_') ||
      f.startsWith('src/application/handlers/comic_') ||
      f.startsWith('src/domain/repositories/comic_') ||
      (f.startsWith('src/') && f.includes('comic')),
    name: 'comic 漫画子域',
  },
  {
    matchScope: (s) => s === 'reporting' || s === 'render' || s.endsWith('/reporting') || s.endsWith('/render'),
    matchFile: (f) => f.startsWith('src/infrastructure/reporting/'),
    name: 'reporting/render 渲染子域 (src/infrastructure/reporting/)',
  },
  {
    matchScope: (s) => s === 'scheduler' || s.endsWith('/scheduler'),
    matchFile: (f) => f.startsWith('src/infrastructure/scheduler/'),
    name: 'scheduler 调度子域 (src/infrastructure/scheduler/)',
  },
  {
    matchScope: (s) => s === 'config' || s.endsWith('/config'),
    matchFile: (f) => f.startsWith('src/infrastructure/config/') || f === '_conf_schema.json',
    name: 'config 配置子域',
  },
  {
    matchScope: (s) => s === 'test' || s === 'tests' || s.startsWith('test/') || s === 'unit' || s === 'e2e' || s === 'mocks',
    matchFile: (f) => f.startsWith('tests/'),
    name: 'test 测试套件 (tests/)',
  },
  {
    matchScope: (s) =>
      s === 'ci' ||
      s.startsWith('ci/') ||
      s === 'scripts' ||
      s === 'lefthook' ||
      s === 'workflow' ||
      s === 'pipeline',
    matchFile: (f) =>
      f.startsWith('.github/') ||
      f.startsWith('scripts/') ||
      f.startsWith('src/utils/') ||
      f === 'lefthook.yml' ||
      f === '.gitignore' ||
      f === 'pyrightconfig.json' ||
      f === 'ruff.toml' ||
      f === '.pre-commit-config.yaml' ||
      f === 'openapi.json',
    name: 'ci 持续集成与门禁 (.github/, scripts/, lefthook.yml, pyrightconfig.json, openapi.json, src/utils/)',
  },
  {
    matchScope: (s) => s === 'deps',
    matchFile: (f) =>
      f.endsWith('pyproject.toml') ||
      f.endsWith('pnpm-lock.yaml') ||
      f.endsWith('package.json') ||
      f.endsWith('uv.lock') ||
      f.endsWith('requirements.txt') ||
      f.endsWith('requirements-dev.txt'),
    name: 'deps 依赖文件 (package.json, pnpm-lock.yaml, pyproject.toml, uv.lock)',
  },
  {
    matchScope: (s) => s === 'docs',
    matchFile: (f) => f.startsWith('docs/') || f.endsWith('.md') || f === 'metadata.yaml',
    name: 'docs 文档 (docs/, *.md, metadata.yaml)',
  },
  {
    matchScope: (s) => s === 'core' || s === 'spec' || s === 'shared' || s === 'utils' || s === 'logger',
    matchFile: (f) =>
      f.startsWith('src/shared/') ||
      f.startsWith('src/utils/') ||
      f.startsWith('scripts/') ||
      f === 'main.py' ||
      f === 'ruff.toml' ||
      f === 'metadata.yaml' ||
      f === 'openapi.json',
    name: 'core/spec 核心协议与基建 (src/shared/, src/utils/, scripts/, main.py)',
  },
];

// ============================================================================
// 2. 检查单条 Commit 消息的核心校验函数
// ============================================================================
function isMergeOrReleaseCommit(firstLine, commitSha = null) {
  // 1. 匹配标准 Merge commit 头
  if (/^Merge (branch|remote-tracking branch|pull request|\w+ into \w+)/i.test(firstLine)) {
    return true;
  }
  // 2. 匹配版本发布/自动化机器人提交 (支持 [vX.Y.Z], vX.Y.Z, chore(release): bump version, release: 等)
  if (
    /^chore(?:\([^)]+\))?:\s*(?:bump version|release)/i.test(firstLine) ||
    /^\[?v\d+\.\d+(?:\.\d+)?(?:-[a-z0-9.]+)?\]?/i.test(firstLine) ||
    /^release(?:\([^)]+\))?:/i.test(firstLine)
  ) {
    return true;
  }
  // 3. 检查 Git 中是否包含多于 1 个 Parent Commit (Merge Commit)
  if (commitSha) {
    try {
      execSync(`git rev-parse --verify --quiet "${commitSha}^2"`, { stdio: 'ignore' });
      return true; // 存在第2个父节点，确认为 Merge commit
    } catch {
      // 非 Merge commit
    }
  }
  return false;
}

function verifyCommit({ rawMessage, touchedFiles = [], commitSha = null, commitAuthor = null }) {
  const cleanLines = rawMessage
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'));

  const header = cleanLines[0] || '';

  // 若为 Merge commit 或版本 Bump commit，直接放行
  if (isMergeOrReleaseCommit(header, commitSha)) {
    return {
      isSkipped: true,
      skipReason: 'Merge / Release Commit 已自动豁免三点论校验',
      header,
      errors: [],
    };
  }

  const fullText = cleanLines.join('\n');
  const nonWhitespaceCount = fullText.replace(/\s+/g, '').length;
  const headerMatch = header.match(/^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(?:\(([^)]+)\))?:\s*(.+)/);

  const errors = [];

  // 1. Header 与 Scope 校验
  if (!headerMatch) {
    errors.push('【Header 格式不规范】须符合 Conventional Commits 格式，例如: feat(domain/analysis): 增强分析值对象类型约束');
  } else {
    const type = headerMatch[1].toLowerCase();
    const rawScope = headerMatch[2] || '';
    const scope = rawScope.trim().toLowerCase();

    // 1.1 禁止同名/同义冗余 Scope（如 ci(ci)、test(test)、feat(feat)、fix(fix) 等）
    const isRedundant =
      scope === type ||
      (type === 'test' && (scope === 'test' || scope === 'tests')) ||
      (type === 'ci' && scope === 'ci') ||
      (type === 'chore' && scope === 'chore') ||
      (type === 'docs' && scope === 'docs') ||
      (type === 'fix' && scope === 'fix') ||
      (type === 'feat' && scope === 'feat');

    if (isRedundant) {
      errors.push(
        `【禁止同名冗余 Scope "${type}(${rawScope})"】\n` +
        `     Type 与 Scope 重复会导致提交信息丢失关键模块上下文（如 "${type}(${rawScope})" 属于无意义套套逻辑）。\n` +
        `     💡 必须使用具体的业务子域、DDD 架构层级或工程切片作为 Scope：\n` +
        `        • 单测提交推荐: test(webui), test(domain), test(analysis), test(platform), test(scheduler), test(infra) 等\n` +
        `        • CI 门禁提交推荐: ci(github-actions), ci(lefthook), ci(workflow), ci(scripts), ci(pipeline) 等\n` +
        `        • 其它规范: 请准确指向实际被测试/修改的具体业务与架构层级。`
      );
    } else if (!scope) {
      errors.push('【缺失改动 Scope】根据原子化提交原则，必须在括号内注明所属模块，例如: feat(domain): ... 或 feat(webui/widgets): ...');
    } else if (!isScopeValid(scope)) {
      let scopeHelp = `【Scope "${rawScope}" 超出允许范围】请选用以下与 DDD 分层、业务子领域或前端 FSD 对应的 Scope：\n`;
      for (const [catName, scopes] of Object.entries(SCOPE_CATEGORIES)) {
        scopeHelp += `\n     ${catName}:\n`;
        for (const [sKey, sDesc] of Object.entries(scopes)) {
          scopeHelp += `       • ${sKey.padEnd(18)} -> ${sDesc}\n`;
        }
      }
      scopeHelp += `\n     💡 支持复合层级表达，如: domain/analysis, infra/platform, app/comic, webui/widgets, test/unit, ci/scripts`;
      errors.push(scopeHelp.trimEnd());
    } else if (touchedFiles.length > 0) {
      // 2. 匹配 Scope 与实际文件路径（严格原子化校验）
      const isPureTestCommit = touchedFiles.every((file) => file.startsWith('tests/'));
      const isPureCiCommit = touchedFiles.every(
        (file) =>
          file.startsWith('.github/') ||
          file.startsWith('scripts/') ||
          file === 'lefthook.yml' ||
          file === 'pyrightconfig.json' ||
          file === 'ruff.toml' ||
          file === '.pre-commit-config.yaml'
      );

      if (isPureTestCommit && (type === 'test' || scope.startsWith('test/') || isScopeValid(scope))) {
        // 如果是纯单测文件改动，允许声明被测业务模块的 Scope (如 test(webui)) 或 test/unit 复合 Scope
      } else if (isPureCiCommit && (type === 'ci' || scope.startsWith('ci/'))) {
        // 如果是纯 CI 脚本/配置文件改动，允许使用 CI 系列具体 Scope (如 ci(lefthook), ci(scripts))
      } else {
        const matchedRule = SCOPE_PATH_RULES.find((r) => r.matchScope(scope));
        if (matchedRule) {
          const hasMatchingFile = touchedFiles.some((file) => matchedRule.matchFile(file));
          if (!hasMatchingFile) {
            errors.push(
              `【Scope 与修改文件路径不匹配】\n` +
              `     您声明的 Scope 为 "${rawScope}"（预期涉及: ${matchedRule.name}），\n` +
              `     但本次涉及的文件全部属于其他路径：\n` +
              `     -> ${touchedFiles.slice(0, 5).join(', ')}${touchedFiles.length > 5 ? ' 等' : ''}\n` +
              `     💡 请修正 Header 中的 Scope 声明，使其与实际修改的文件模块相符。`
            );
          } else {
            // 严格原子化校验：除了配套的单测/文档文件（以及前端源码提交配套的 pages/ 构建产物）外，所有生产代码必须完全匹配该 Scope！
            const isFrontendScope =
              scope === 'dashboard' ||
              scope === 'webui' ||
              scope.startsWith('webui/') ||
              scope === 'pages' ||
              scope === 'widgets' ||
              scope === 'features' ||
              scope === 'entities' ||
              scope === 'shared' ||
              scope === 'tasks' ||
              scope === 'traces' ||
              scope === 'reports' ||
              scope === 'charts';

            const unmatchedProductionFiles = touchedFiles.filter((file) => {
              // 允许随行提交配套的单元测试与文档说明
              if (file.startsWith('tests/') || file.startsWith('docs/') || file.endsWith('.md')) {
                return false;
              }
              // 如果是前端相关 Scope，允许随行提交打包编译生成的 pages/ 静态产物
              if (isFrontendScope && file.startsWith('pages/')) {
                return false;
              }
              return !matchedRule.matchFile(file);
            });

            if (unmatchedProductionFiles.length > 0) {
              errors.push(
                `【跨模块/非原子化提交拦截】\n` +
                `     您声明的 Scope 为 "${rawScope}"（对应路径范围: ${matchedRule.name}），\n` +
                `     但本次提交混入了不属于该 Scope 的异构文件（存在跨层级/跨子域混杂，破坏了原子化）：\n` +
                `     -> ${unmatchedProductionFiles.slice(0, 5).join('\n     -> ')}${unmatchedProductionFiles.length > 5 ? '\n     -> ...等' : ''}\n` +
                `     💡 必须保持原子化提交：请使用 git add 仅暂存同一架构模块的文件，将跨层级/跨子域改动拆分为独立的 Commit。`
              );
            }
          }
        }
      }
    }
  }

  // 3. 检查三点论关键词 (深度兼容中英双语、Markdown 列表符号、标题、粗体 **、方括号与前缀编号)
  const hasProblem =
    /(?:^|\n)\s*(?:[-*•#>_~]|\d+[.、]|\(\d+\)|【|\[|\*{1,3}|#{1,6})*[^\n]*?(?:问题|痛点|Problem|Issue|Root\s*Cause)[^\n]*(?:[：:]|\n)/i.test(fullText);
  const hasSolution =
    /(?:^|\n)\s*(?:[-*•#>_~]|\d+[.、]|\(\d+\)|【|\[|\*{1,3}|#{1,6})*[^\n]*?(?:解决措施|解决方案|措施|修改方法|Solution|Fix|Approach|Resolution)[^\n]*(?:[：:]|\n)/i.test(fullText);
  const hasEffect =
    /(?:^|\n)\s*(?:[-*•#>_~]|\d+[.、]|\(\d+\)|【|\[|\*{1,3}|#{1,6})*[^\n]*?(?:效果|收益|预期效果|影响|Effect|Impact|Result|Outcome|Value)[^\n]*(?:[：:]|\n)/i.test(fullText);

  if (!hasProblem) {
    errors.push('【缺失“问题”说明】Body 必须包含以“问题：”/“Problem:”开头并阐述具体原因的段落');
  }

  if (!hasSolution) {
    errors.push('【缺失“解决措施”说明】Body 必须包含以“解决措施：”/“Solution:”开头并阐述修改方法的段落');
  }

  if (!hasEffect) {
    errors.push('【缺失“效果”说明】Body 必须包含以“效果：”/“Effect:”/“Result:”开头并说明预期结果/量化数据的段落');
  }

  if (nonWhitespaceCount < 40) {
    errors.push(`【字数不足门禁】提交内容去空格后当前仅 ${nonWhitespaceCount} 字，要求不少于 40 字`);
  }

  return {
    isSkipped: false,
    header,
    commitSha,
    commitAuthor,
    errors,
  };
}

// ============================================================================
// 3. 友好的终端输出与 GitHub Actions Annotation
// ============================================================================
function printFailureGuide(failedResults) {
  console.error('\n' + '='.repeat(74));
  console.error('\x1b[31;1m[FAIL] Git Commit 门禁校验未通过，已阻止合并/提交：\x1b[0m');

  failedResults.forEach((res, i) => {
    const shaTag = res.commitSha ? ` [${res.commitSha.slice(0, 7)}]` : '';
    console.error(`\n\x1b[31;1m❌ 提交 #${i + 1}${shaTag}: ${res.header}\x1b[0m`);
    res.errors.forEach((err, idx) => {
      console.error(`  \x1b[33m${idx + 1}. ${err}\x1b[0m`);
    });

    // GitHub Actions Workflow Error Annotation 输出
    if (process.env.GITHUB_ACTIONS === 'true') {
      const singleLineMsg = res.errors.map((e) => e.split('\n')[0]).join(' | ');
      console.error(`::error title=Commit Lint Failed${shaTag}::${singleLineMsg.replace(/"/g, "'")}`);
    }
  });

  console.error('\n' + '-'.repeat(74));
  console.error('\x1b[36;1m💡【STAR 原则与问题导向提交指南 (Problem-Oriented Commit Guide)】\x1b[0m');
  console.error('\x1b[90m  提交信息应清晰回答：为什么改(痛点根因) -> 怎么改(设计手段) -> 带来什么价值(量化收益)。\x1b[0m');
  console.error('\x1b[90m  避免无信息量的流水账（如“修改了某文件”），应注重技术决策与实际工程影响。\x1b[0m\n');

  console.error('\x1b[33;1m📐 编写结构要点：\x1b[0m');
  console.error('  \x1b[33m• 问题：\x1b[0m阐明业务/架构痛点、触发场景与根本原因（如并发竞态、内存膨胀、类型黑洞、阻塞延迟等）。');
  console.error('  \x1b[33m• 解决措施：\x1b[0m阐述架构设计意图、核心技术方案与防腐隔离手段（说明为什么选该方案，如何根治）。');
  console.error('  \x1b[33m• 效果：\x1b[0m提供量化的工程/业务指标、性能提升幅度或确定性收益（如耗时下降、内存优化、覆盖率、0报错等）。\n');

  console.error('\x1b[32;1m📚 高质量提交范例（供参考与代入）：\x1b[0m');
  console.error('\x1b[32m');
  console.error('【示例 1 - 领域层/后端架构】');
  console.error('feat(domain/analysis): 重塑群分析聚合根与增量快照状态机');
  console.error('');
  console.error('问题：高并发分析场景下，无状态的散装字典导致历史游标与聚合统计产生脏读，且 LLM 重试时发生状态污染与内存无序膨胀。');
  console.error('解决措施：建立 GroupAnalysisAggregate 聚合根并引入不可变增量快照状态机，结合 Checkpoint 防腐隔离重试逻辑与领域状态。');
  console.error('效果：消除并发读写冲突，内存峰值下降 45%，异常断点恢复成功率达 100%，Pyright 严格类型检查 0 报错。');
  console.error('');
  console.error('【示例 2 - 前端 FSD 小部件/性能优化】');
  console.error('perf(webui/widgets): 重构 TrendCharts 趋势看板，引入 Web Worker 与分片渲染');
  console.error('');
  console.error('问题：单群历史消息超 50,000 条时，控制台全量挂载 ECharts 与交互表格造成主线程阻塞超 1.8s，低端设备频繁卡顿掉帧。');
  console.error('解决措施：基于 Web Worker 异步计算词频权重，看板图表采用 requestAnimationFrame 分片渲染，并对历史数据表接入虚拟滚动。');
  console.error('效果：页面首次可交互时间 (TTI) 由 2.1s 缩短至 280ms (提升 86%)，滚动 FPS 稳定在 60 帧，前端编译与打包全绿。');
  console.error('');
  console.error('【示例 3 - 平台适配/网络容灾】');
  console.error('fix(infra/platform): 统一跨平台头像拉取重试熔断与 Negative Cache 机制');
  console.error('');
  console.error('问题：三方平台 CDN 在弱网或限流下频繁抛出 429 与连接超时，导致主分析链路被级联阻塞长达 30 秒以上。');
  console.error('解决措施：在 PlatformAdapter 抽象层引入指数退避并发限流器，并对失败 OpenID 建立 10 分钟负缓存 (Negative Cache) 实施熔断。');
  console.error('效果：彻底切断外部抖动对核心链路的阻塞传播，单次报告生成 P99 耗时从 35s 下降至 6.2s，网络异常率下降 98%。');
  console.error('\x1b[0m');
  console.error('='.repeat(74) + '\n');
}

// ============================================================================
// 4. 主执行入口 (支持 PR Squash 模式 / 本地 Hook 模式 / CI Commit 范围模式)
// ============================================================================
function main() {
  const args = process.argv.slice(2);
  const isCiMode = args.includes('--ci') || args.includes('-ci');
  const rangeIndex = args.indexOf('--range');
  let commitRange = rangeIndex !== -1 && args[rangeIndex + 1] ? args[rangeIndex + 1] : null;

  const prTitleIndex = args.indexOf('--pr-title');
  const prBodyIndex = args.indexOf('--pr-body');
  const msgTextIndex = args.indexOf('--msg');

  // 模式 A: PR 标题与描述校验模式 (针对 GitHub PR Squash Merge 工作流)
  if (prTitleIndex !== -1 && args[prTitleIndex + 1]) {
    const prTitle = args[prTitleIndex + 1];
    const prBody = prBodyIndex !== -1 && args[prBodyIndex + 1] ? args[prBodyIndex + 1] : '';
    const rawMessage = `${prTitle}\n\n${prBody}`;

    console.log(`\x1b[36m🔍 [PR Squash Lint] 正在检查 PR 标题与描述规范...\x1b[0m`);
    const result = verifyCommit({ rawMessage });
    if (result.isSkipped) {
      console.log(`\x1b[90m[SKIP] ${result.header} (${result.skipReason})\x1b[0m`);
      process.exit(0);
    }
    if (result.errors.length > 0) {
      printFailureGuide([result]);
      process.exit(1);
    }
    console.log(`\x1b[32;1m[PASS] Pull Request 标题与描述规范校验通过！Squash Merge 将生成合规主干提交。\x1b[0m`);
    process.exit(0);
  }

  // 模式 B: 直接传入消息文本模式
  if (msgTextIndex !== -1 && args[msgTextIndex + 1]) {
    const rawMessage = args[msgTextIndex + 1];
    const result = verifyCommit({ rawMessage });
    if (result.isSkipped) {
      console.log(`\x1b[90m[SKIP] ${result.header} (${result.skipReason})\x1b[0m`);
      process.exit(0);
    }
    if (result.errors.length > 0) {
      printFailureGuide([result]);
      process.exit(1);
    }
    console.log('\x1b[32;1m[PASS] Commit 消息文本规范校验通过！\x1b[0m');
    process.exit(0);
  }

  // 模式 C: CI 或范围校验模式 (检查多条 commit)
  if (isCiMode || commitRange) {
    if (!commitRange) {
      if (process.env.GITHUB_EVENT_NAME === 'pull_request' && process.env.GITHUB_BASE_REF) {
        commitRange = `origin/${process.env.GITHUB_BASE_REF}...HEAD`;
      } else if (process.env.GITHUB_EVENT_BEFORE && !/^0+$/.test(process.env.GITHUB_EVENT_BEFORE)) {
        commitRange = `${process.env.GITHUB_EVENT_BEFORE}...${process.env.GITHUB_SHA || 'HEAD'}`;
      } else {
        commitRange = 'HEAD~1..HEAD';
      }
    }

    console.log(`\x1b[36m🔍 [CI Commit Lint] 正在检查提交范围: ${commitRange}\x1b[0m`);

    let commitShas = [];
    try {
      const output = execSync(`git log --format="%H" ${commitRange}`, { encoding: 'utf-8' }).trim();
      if (output) {
        commitShas = output.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
      }
    } catch {
      // 容错：如果 range 解析失败（如浅克隆单提交），尝试检查 HEAD
      try {
        const headSha = execSync('git rev-parse HEAD', { encoding: 'utf-8' }).trim();
        commitShas = [headSha];
      } catch (err) {
        console.error('\x1b[31m[Commit Lint Error] 无法从 git 中获取提交记录: ' + err.message + '\x1b[0m');
        process.exit(1);
      }
    }

    if (commitShas.length === 0) {
      console.log('\x1b[32m[PASS] 未发现需要校验的新提交。\x1b[0m');
      process.exit(0);
    }

    const failedResults = [];
    let checkedCount = 0;
    let skippedCount = 0;

    for (const sha of commitShas) {
      try {
        const rawMessage = execSync(`git log -1 --format="%B" ${sha}`, { encoding: 'utf-8' });
        const commitAuthor = execSync(`git log -1 --format="%an" ${sha}`, { encoding: 'utf-8' }).trim();
        const touchedFilesRaw = execSync(`git diff-tree --no-commit-id --name-only -r ${sha}`, { encoding: 'utf-8' }).trim();
        const touchedFiles = touchedFilesRaw ? touchedFilesRaw.split(/\r?\n/).map((f) => f.trim().replace(/\\/g, '/')).filter(Boolean) : [];

        const result = verifyCommit({ rawMessage, touchedFiles, commitSha: sha, commitAuthor });
        if (result.isSkipped) {
          skippedCount++;
          console.log(`\x1b[90m  • [${sha.slice(0, 7)}] [SKIP] ${result.header} (${result.skipReason})\x1b[0m`);
        } else if (result.errors.length > 0) {
          failedResults.push(result);
        } else {
          checkedCount++;
          console.log(`\x1b[32m  ✔ [${sha.slice(0, 7)}] ${result.header}\x1b[0m`);
        }
      } catch (e) {
        console.warn(`\x1b[33m  ⚠ 无法解析提交 ${sha.slice(0, 7)}: ${e.message}\x1b[0m`);
      }
    }

    if (failedResults.length > 0) {
      printFailureGuide(failedResults);
      process.exit(1);
    }

    console.log(`\n\x1b[32;1m[PASS] 所有提交均通过规范校验！(已检查: ${checkedCount} 个常规提交, 已放行: ${skippedCount} 个合并/发布提交)\x1b[0m`);
    process.exit(0);
  }

  // 模式 B: 本地 Hook 模式 (传入 COMMIT_EDITMSG 路径)
  const msgPath = args[0];
  if (!msgPath) {
    console.error('\x1b[31m[Commit Lint Error] 未能获取 commit 信息路径。用法: node verify-commit.js <commit-msg-path> 或 node verify-commit.js --ci\x1b[0m');
    process.exit(1);
  }

  const rawMessage = fs.readFileSync(path.resolve(msgPath), 'utf-8');
  let stagedFiles = [];
  try {
    const stagedFilesRaw = execSync('git diff --cached --name-only', { encoding: 'utf-8' }).trim();
    if (stagedFilesRaw) {
      stagedFiles = stagedFilesRaw.split(/\r?\n/).map((f) => f.trim().replace(/\\/g, '/')).filter(Boolean);
    }
  } catch {
    // 忽略异常
  }

  const result = verifyCommit({ rawMessage, touchedFiles: stagedFiles });
  if (result.isSkipped) {
    console.log(`\x1b[90m[SKIP] ${result.header} (${result.skipReason})\x1b[0m`);
    process.exit(0);
  }

  if (result.errors.length > 0) {
    printFailureGuide([result]);
    process.exit(1);
  }

  console.log('\x1b[32;1m[PASS] Git 提交规范校验通过（原子化 Scope + 路径一致性 + 中文三点论 + 40字门禁已达标）\x1b[0m');
  process.exit(0);
}

main();
