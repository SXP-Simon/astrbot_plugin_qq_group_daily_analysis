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

  console.error('\n' + '-'.repeat(72));
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
  console.error('feat(domain): 重塑群分析聚合根与增量快照状态机');
  console.error('');
  console.error('问题：高并发分析场景下，无状态的散装字典导致历史游标与聚合统计产生脏读，且 LLM 重试时发生状态污染与内存无序膨胀。');
  console.error('解决措施：建立 GroupAnalysisAggregate 聚合根并引入不可变增量快照状态机，结合 Checkpoint 防腐隔离重试逻辑与领域状态。');
  console.error('效果：消除并发读写冲突，内存峰值下降 45%，异常断点恢复成功率达 100%，Pyright 严格类型检查 0 报错。');
  console.error('');
  console.error('【示例 2 - 展现层/WebUI 性能优化】');
  console.error('perf(webui): 重构历史词云与趋势看板，引入虚拟列表与分片渲染');
  console.error('');
  console.error('问题：单群历史消息超 50,000 条时，控制台全量挂载 ECharts 与交互表格造成主线程阻塞超 1.8s，低端设备频繁卡顿掉帧。');
  console.error('解决措施：基于 Web Worker 异步计算词频权重，看板图表采用 requestAnimationFrame 分片渲染，并对历史数据表接入虚拟滚动。');
  console.error('效果：页面首次可交互时间 (TTI) 由 2.1s 缩短至 280ms (提升 86%)，滚动 FPS 稳定在 60 帧，前端编译与打包全绿。');
  console.error('');
  console.error('【示例 3 - 平台适配/网络容灾】');
  console.error('fix(platform): 统一跨平台头像拉取重试熔断与 Negative Cache 机制');
  console.error('');
  console.error('问题：三方平台 CDN 在弱网或限流下频繁抛出 429 与连接超时，导致主分析链路被级联阻塞长达 30 秒以上。');
  console.error('解决措施：在 PlatformAdapter 抽象层引入指数退避并发限流器，并对失败 OpenID 建立 10 分钟负缓存 (Negative Cache) 实施熔断。');
  console.error('效果：彻底切断外部抖动对核心链路的阻塞传播，单次报告生成 P99 耗时从 35s 下降至 6.2s，网络异常率下降 98%。');
  console.error('\x1b[0m');
  console.error('='.repeat(72) + '\n');
  process.exit(1);
}

console.log('\x1b[32;1m[PASS] Git 提交规范校验通过（原子化 Scope + 中文三点论 + 40字门禁已达标）\x1b[0m');
process.exit(0);
