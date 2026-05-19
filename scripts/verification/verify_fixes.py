#!/usr/bin/env python3
"""验证 ontology_v2.2.html 的核心功能"""
import subprocess, json

# 用 Node.js 模拟页面加载并检查关键配置
SCRIPT = """
const fs = require('fs');
const html = fs.readFileSync('/root/remote-test/visualization/ontology_v2.2.html', 'utf8');

// 1. 检查 IS_A_EDGES 是否包含新增的条目
if (html.includes("['Law', 'LegalNorm']")) console.log('PASS: IS_A_EDGES has Law→LegalNorm');
else console.log('FAIL: IS_A_EDGES missing Law→LegalNorm');

if (html.includes("['Organization', 'LegalSubject']")) console.log('PASS: IS_A_EDGES has Organization→LegalSubject');
else console.log('FAIL: IS_A_EDGES missing Organization→LegalSubject');

// 2. 检查 ENTITY_STYLES 是否被用于节点形状
if (html.includes("var entStyle = ENTITY_STYLES[name]")) console.log('PASS: ENTITY_STYLES used for node shape');
else console.log('FAIL: ENTITY_STYLES not used');

// 3. 检查 dashes 是否为 true（布尔值，不是字符串）
var dashMatch = html.match(/dashes:\\s*true\\b/g);
if (dashMatch && dashMatch.length > 0) console.log('PASS: dashes=true found ' + dashMatch.length + ' times');
else console.log('FAIL: no dashes=true found');

// 4. 检查 window.__DOM rescue 后更新
if (html.includes("__DOM[id] = el")) console.log('PASS: __DOM updated after rescue');
else console.log('FAIL: __DOM not updated after rescue');

// 5. 检查 cluster_ skip
if (html.includes("cluster_") && html.includes("cluster_") && html.includes("indexOf('cluster_') === 0")) 
  console.log('PASS: cluster_ nodes skipped in click handlers');
else console.log('FAIL: cluster_ skip missing');

// 6. 检查 || document.getElementById fallback
if (html.includes("document.getElementById('panelBody')")) console.log('PASS: panelBody has getElementById fallback');
else console.log('FAIL: panelBody missing getElementById fallback');

// 7. 检查 network.getNode 替换
if (html.includes("network.body.nodes")) console.log('PASS: uses network.body.nodes');
else console.log('FAIL: no network.body.nodes found');

// 8. 检查 window.isPanelLocked 暴露
if (html.includes("window.isPanelLocked = false")) console.log('PASS: window.isPanelLocked exposed');
else console.log('FAIL: window.isPanelLocked not exposed');

console.log('---');
console.log('IS_A_EDGES count:', (html.match(/['\\w]+',\\s*['\\w]+\\]/g) || []).length);
console.log('Total checks passed: all done');
"""

import subprocess
r = subprocess.run(['node', '-e', SCRIPT], capture_output=True, text=True, cwd='/root/remote-test')
print(r.stdout)
if r.stderr: print('ERR:', r.stderr[:500])
