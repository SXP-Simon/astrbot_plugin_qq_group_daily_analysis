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

const ALLOWED_SCOPES = [
  'domain',
  'app',
  'application',
  'infra',
  'infrastructure',
  'platform',
  'reporting',
  'scheduler',
  'webui',
  'config',
  'comic',
  'analysis',
  'tests',
  'ci',
  'deps',
  'docs',
  'core',
  'render',
  'spec'
];

const errors = [];

if (!headerMatch) {
  errors.push('【Header 格式不规范】须符合 Conventional Commits 格式，例如: feat(reporting): 优化官方 Markdown 卡片渲染');
} else {
  const scope = headerMatch[2];
  if (!scope) {
    errors.push('【缺失改动 Scope】根据原子化提交原则，必须在括号内注明所属模块，例如: feat(domain): ...');
  } else if (!ALLOWED_SCOPES.includes(scope)) {
    errors.push(`【Scope 超出允许范围】"${scope}" 不属于合法模块。允许的 Scope 列表:\n     -> ${ALLOWED_SCOPES.join(', ')}`);
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
  console.error('feat(domain): 强化每日分析领域值对象与仓储契约');
  console.error('');
  console.error('问题：历史代码中大量使用散装字典 dict[str, object]，导致 IDE 无法进行 F12 跳转和属性推导，存在类型安全盲区。');
  console.error('解决措施：引入 AnalysisResultPayload、ComicStoryboard 等领域值对象，并在仓储接口与应用服务全链路打通强类型流转。');
  console.error('效果：实现 100% IDE 智能感知与 F12 准确跳转，消除所有 getattr 反射调用，静态检查 0 错误且全量单测通过。');
  console.error('\x1b[0m');
  console.error('='.repeat(70) + '\n');
  process.exit(1);
}

console.log('\x1b[32;1m[PASS] Git 提交规范校验通过（原子化 Scope + 中文三点论 + 40字门禁已达标）\x1b[0m');
process.exit(0);
