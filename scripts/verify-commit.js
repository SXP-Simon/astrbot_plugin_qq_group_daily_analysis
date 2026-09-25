#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const msgPath = process.argv[2];
if (!msgPath) {
  console.error('\x1b[31m[Commit Lint Error] 未能获取 commit 信息路径。\x1b[0m');
  process.exit(1);
}

const rawMessage = fs.readFileSync(path.resolve(msgPath), 'utf-8');

// 过滤掉 Git 自动生成的注释行 (# 开头的行)
const cleanLines = rawMessage
  .split('\n')
  .map((line) => line.trim())
  .filter((line) => line && !line.startsWith('#'));

const fullText = cleanLines.join('\n');
const nonWhitespaceCount = fullText.replace(/\s+/g, '').length;

// 1. 提取 Header 并校验 Scope 范围
const header = cleanLines[0] || '';
const headerMatch = header.match(/^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(?:\(([^)]+)\))?:\s*(.+)/);

// 1. DDD 架构分层与业务子领域 Scope 规范定义
const SCOPE_CATEGORIES = {
  '🏛️ 架构分层 (DDD Architectural Layers)': {
    domain: '领域层 (Entities, Value Objects, 仓储抽象契约, 领域事件)',
    app: '应用层 (用例编排, Application Services, Handlers, DTO)',
    application: '应用层完整别名 (同 app)',
    infra: '基础设施层 (平台适配器, 防腐层 ACL, 数据库/存储, LLM 驱动)',
    infrastructure: '基础设施层完整别名 (同 infra)',
    webui: '展现层/WebUI (前端页面组件, RESTful API 路由, 控制台交互)',
  },
  '🎯 业务子领域 (Core Sub-domains)': {
    analysis: '分析子域 (LLM 分析器, 文本聚合, 情绪/质量/统计分析)',
    comic: '漫画子域 (分镜解析, 提示词引擎, 图像生成与相册流转)',
    reporting: '报告渲染子域 (HTML/Image 渲染引擎, 主题模板, 排版系统)',
    render: '渲染引擎别名 (同 reporting)',
    platform: '多平台通信子域 (OneBot, QQOfficial, Telegram, Discord 适配)',
    scheduler: '调度与恢复子域 (Cron 任务, 增量分析, 熔断恢复, TaskGuard)',
    config: '配置子域 (配置项管理, 动态热重载, Schema 校验)',
  },
  '🛠️ 工程与基建 (Engineering & Infrastructure)': {
    test: '测试 (单元测试, 集成测试, Mock 桩代码)',
    tests: '测试别名 (同 test)',
    ci: '持续集成与门禁 (Git hooks, GitHub Actions, Linter 脚本)',
    deps: '依赖管理 (第三方库版本升级, uv/pip 依赖锁)',
    docs: '文档 (架构设计, 接口文档, 开发者指南)',
    core: '核心协议与规范 (基础常量, 全局上下文, 通用基建)',
    spec: '设计规范与契约定义',
  },
};

// 扁平化所有合法 Scope
const ALLOWED_SCOPES = Object.values(SCOPE_CATEGORIES).flatMap((cat) => Object.keys(cat));

const errors = [];

if (!headerMatch) {
  errors.push('【Header 格式不规范】须符合 Conventional Commits 格式，例如: feat(domain): 增强值对象类型约束');
} else {
  const scope = headerMatch[2];
  if (!scope) {
    errors.push('【缺失改动 Scope】根据原子化提交原则，必须在括号内注明所属模块，例如: feat(domain): ...');
  } else if (!ALLOWED_SCOPES.includes(scope)) {
    let scopeHelp = `【Scope "${scope}" 超出允许范围】请选用以下与 DDD 分层及子域对应的 Scope：\n`;
    for (const [catName, scopes] of Object.entries(SCOPE_CATEGORIES)) {
      scopeHelp += `\n     ${catName}:\n`;
      for (const [sKey, sDesc] of Object.entries(scopes)) {
        scopeHelp += `       • ${sKey.padEnd(14)} -> ${sDesc}\n`;
      }
    }
    errors.push(scopeHelp.trimEnd());
  }
}

// 2. 检查三点论关键词
const hasProblem = /(?:^|\n)\s*问题[：:]\s*\S+/.test(fullText);
const hasSolution = /(?:^|\n)\s*解决措施[：:]\s*\S+/.test(fullText);
const hasEffect = /(?:^|\n)\s*效果[：:]\s*\S+/.test(fullText);

if (!hasProblem) {
  errors.push('【缺失“问题”说明】Body 必须包含以“问题：”或“问题:”开头并阐述具体原因的段落');
}

if (!hasSolution) {
  errors.push('【缺失“解决措施”说明】Body 必须包含以“解决措施：”或“解决措施:”开头并阐述修改方法的段落');
}

if (!hasEffect) {
  errors.push('【缺失“效果”说明】Body 必须包含以“效果：”或“效果:”开头并说明预期结果/量化数据的段落');
}

if (nonWhitespaceCount < 40) {
  errors.push(`【字数不足门禁】提交内容去空格后当前仅 ${nonWhitespaceCount} 字，要求不少于 40 字`);
}

if (errors.length > 0) {
  console.error('\n' + '='.repeat(70));
  console.error('\x1b[31;1m[FAIL] Git Commit 门禁校验未通过，已阻止本次提交：\x1b[0m');
  errors.forEach((err, idx) => {
    console.error(`  \x1b[33m${idx + 1}. ${err}\x1b[0m`);
  });

  console.error('\n' + '-'.repeat(70));
  console.error('\x1b[36;1m[GUIDE] 标准原子化三点论提交模板（供参考）：\x1b[0m');
  console.error('\x1b[32m');
  console.error('【后端示例】:');
  console.error('feat(domain): 强化每日分析领域值对象与仓储契约');
  console.error('');
  console.error('问题：历史代码中大量使用散装字典 dict[str, object]，导致 IDE 无法进行 F12 跳转和属性推导，存在类型安全盲区。');
  console.error('解决措施：引入 AnalysisResultPayload、ComicStoryboard 等领域值对象，并在仓储接口与应用服务全链路打通强类型流转。');
  console.error('效果：实现 100% IDE 智能感知与 F12 准确跳转，消除所有 getattr 反射调用，静态检查 0 错误且全量单测通过。');
  console.error('');
  console.error('【WebUI / 前端示例】:');
  console.error('feat(webui): 优化任务面板实时状态轮询与图表挂载生命周期');
  console.error('');
  console.error('问题：控制台任务列表存在状态刷新不及时与 ECharts 多次重绘抖动问题，且配置表单缺少客户端 Schema 校验。');
  console.error('解决措施：在 dashboard 模块引入自适应轮询机制与 ECharts 防抖渲染，并使用 Zod 补全表单校验与 TypeScript 类型。');
  console.error('效果：消除页面卡顿与无效请求，前端 tsc/eslint 0 报错，vite 生产打包构建正常且样式响应灵敏。');
  console.error('\x1b[0m');
  console.error('='.repeat(70) + '\n');
  process.exit(1);
}

console.log('\x1b[32;1m[PASS] Git 提交规范校验通过（原子化 Scope + 中文三点论 + 40字门禁已达标）\x1b[0m');
process.exit(0);
