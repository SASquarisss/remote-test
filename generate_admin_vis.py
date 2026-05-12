#!/usr/bin/env python3
"""
Generate admin case knowledge graph visualization HTML.
Reads extracted_v2.2_admin_all.jsonl filtered by admin_cases_only.csv row_ids.
"""
import json
import csv
import os
import hashlib
from collections import defaultdict

PROJECT = '/root/remote-test'
JSONL_PATH = os.path.join(PROJECT, 'data_lake/extracted_v2.2_admin_all.jsonl')
CSV_PATH = os.path.join(PROJECT, 'data/raw/admin_cases_only.csv')
OUTPUT_PATH = os.path.join(PROJECT, 'visualization/admin_instances.html')
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

# Read admin row_ids from CSV
admin_ids = set()
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        admin_ids.add(row['id'])

# Read JSONL and filter admin cases, handling versions and dedup
cases_raw = []
with open(JSONL_PATH, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        rid = data.get('row_id')
        if rid and str(rid).strip() and rid in admin_ids and data.get('output') is not None:
            # Compute fingerprint for dedup
            fp = hashlib.sha256(
                json.dumps(data['output'], sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            raw_line = line.rstrip('\n')
            cases_raw.append({'row_id': rid, 'data': data, 'fingerprint': fp, 'raw': raw_line})

# Dedup by row_id + fingerprint
by_rid = defaultdict(list)
for c in cases_raw:
    by_rid[c['row_id']].append(c)

cases = []
raw_data = {}  # {row_id_v1: raw_json, row_id_v2: raw_json, ...}
for rid, entries in by_rid.items():
    # Group by fingerprint within same row_id
    by_fp = defaultdict(list)
    for e in entries:
        by_fp[e['fingerprint']].append(e)
    ver = 1
    for fp, fp_entries in by_fp.items():
        # Take the first entry per fingerprint (they're identical)
        entry = fp_entries[0]
        entry['version'] = ver
        compound_key = f"{rid}__v{ver}" if len(fp_entries) > 1 or len(by_fp) > 1 else str(rid)
        raw_data[compound_key] = entry['raw']
        cases.append(entry)
        ver += 1

print(f"Loaded {len(cases)} admin cases (from {len(cases_raw)} raw lines, {len(admin_ids)} admin IDs)")
print(f"Versions assigned: {sum(len(v) for v in by_fp.values())} entries -> {len(cases)} output cases")
print(f"Raw data entries: {len(raw_data)}")

# Build graph data per case
case_graphs = []
for case in cases:
    output = case['data']['output']
    guiding = output.get('guiding_case') or {}
    court_cases_list = output.get('court_cases') or []
    legal_subjects = output.get('legal_subjects') or []
    legal_provisions = output.get('legal_provisions') or []
    case_type = output.get('case_type') or {}

    row_id = case['row_id']
    case_name = guiding.get('guiding_case_name') or f'Case {row_id}'
    display_name = case_name if len(case_name) <= 30 else case_name[:28] + '…'

    nodes = []
    edges = []

    # Node: GuidingCase (central)
    gc_id = f"gc_{row_id}"
    keywords = guiding.get('key_words') or []
    guiding_points = guiding.get('guiding_points') or ''
    nodes.append({
        'id': gc_id,
        'label': display_name,
        'type': 'GuidingCase',
        'group': row_id,
        'title': f"<b>指导案例/典型案例</b><br/>名称: {case_name}<br/>案号: {guiding.get('storage_no','')}<br/>效力: {guiding.get('binding_force','')}<br/>层级: {guiding.get('case_level','')}<br/>关键词: {'; '.join(keywords)}<br/>裁判要旨: {guiding_points[:200]}...",
        'level': 0
    })

    # Node: CaseType / CaseSummary
    ct_id = f"ct_{row_id}"
    level2 = case_type.get('level2') or case_type.get('level1') or ''
    nodes.append({
        'id': ct_id,
        'label': level2[:20],
        'type': 'CaseSummary',
        'group': row_id,
        'title': f"<b>案件类型</b><br/>类别: {case_type.get('category','')}<br/>层级1: {case_type.get('level1','')}<br/>层级2: {level2}",
        'level': 1
    })
    edges.append({'from': gc_id, 'to': ct_id, 'label': 'classified_as'})

    # CourtCases nodes
    for i, cc in enumerate(court_cases_list):
        case_no = cc.get('case_number') or f'案号未提供_{i}'
        short_case_no = case_no if len(case_no) <= 25 else case_no[:23] + '…'
        cc_id = f"courtcase_{row_id}_{i}"
        court_name = (cc.get('court') or {}).get('name') or '未知法院'
        nodes.append({
            'id': cc_id,
            'label': short_case_no,
            'type': 'CourtCase',
            'group': row_id,
            'title': f"<b>法院案件</b><br/>案号: {case_no}<br/>法院: {court_name}<br/>法院层级: {(cc.get('court') or {}).get('court_level','')}<br/>审级: {cc.get('trial_level','')}<br/>程序: {cc.get('trial_procedure','')}<br/>案由: {cc.get('cause_of_action','')}<br/>状态: {cc.get('status','')}<br/>裁判日期: {cc.get('judgment_date','')}",
            'level': 1
        })
        edges.append({'from': gc_id, 'to': cc_id, 'label': 'has_court_case'})

    # LegalSubjects nodes
    for j, subj in enumerate(legal_subjects):
        subj_name = subj.get('name') or f'主体{j}'
        roles_list = subj.get('roles') or []
        role_strs = list(set(r.get('role_name','') for r in roles_list if r.get('role_name')))
        subj_id = f"subj_{row_id}_{j}"
        short_name = subj_name if len(subj_name) <= 20 else subj_name[:18] + '…'
        nodes.append({
            'id': subj_id,
            'label': short_name,
            'type': 'LegalSubject',
            'group': row_id,
            'title': f"<b>诉讼主体</b><br/>名称: {subj_name}<br/>类型: {subj.get('subject_type','')}<br/>组织性质: {subj.get('org_type','')}<br/>角色: {'; '.join(role_strs)}",
            'level': 2
        })
        edges.append({'from': gc_id, 'to': subj_id, 'label': 'has_subject'})
        # Connect to relevant court cases via roles
        for role in roles_list:
            role_case_no = role.get('case_number', '')
            if role_case_no:
                for k, cc in enumerate(court_cases_list):
                    if cc.get('case_number') == role_case_no:
                        rel_cc_id = f"courtcase_{row_id}_{k}"
                        edges.append({'from': subj_id, 'to': rel_cc_id, 'label': role.get('role_name','')})
                        break

    # LegalProvisions nodes
    for k, prov in enumerate(legal_provisions):
        statute = prov.get('statute', '')
        article = prov.get('article', '')
        item = prov.get('item', '')
        provision_label = f"{statute.split('法')[0] if statute else '法'}§{article}"
        if item:
            provision_label += f"-{item}"
        full_provision = f"{statute} 第{article}条"
        if item:
            full_provision += f" 第{item}项"
        if prov.get('paragraph'):
            full_provision += f" 第{prov['paragraph']}款"
        prov_id = f"prov_{row_id}_{k}"
        prov_content = prov.get('content') or ''
        nodes.append({
            'id': prov_id,
            'label': provision_label[:20],
            'type': 'LegalProvision',
            'group': 'law',
            'title': f"<b>法律条文</b><br/>{full_provision}<br/>内容: {prov_content[:200]}...<br/>引用位置: {prov.get('citation_position','')}<br/>引用目的: {prov.get('citation_purpose','')}",
            'level': 3
        })
        prov_case_no = prov.get('case_number', '')
        connected = False
        if prov_case_no:
            for m, cc in enumerate(court_cases_list):
                if cc.get('case_number') == prov_case_no:
                    rel_cc_id = f"courtcase_{row_id}_{m}"
                    edges.append({'from': prov_id, 'to': rel_cc_id, 'label': 'applied_in'})
                    connected = True
                    break
        if not connected:
            edges.append({'from': gc_id, 'to': prov_id, 'label': 'references'})

    # Evidence node
    ev_id = f"ev_{row_id}"
    nodes.append({
        'id': ev_id,
        'label': '证据材料',
        'type': 'Evidence',
        'group': row_id,
        'title': f"<b>证据</b><br/>案件: {case_name}",
        'level': 2
    })
    edges.append({'from': gc_id, 'to': ev_id, 'label': 'has_evidence'})

    # JudgmentResult node
    jr_id = f"jr_{row_id}"
    binding_force = guiding.get('binding_force', '')
    nodes.append({
        'id': jr_id,
        'label': '裁判结果',
        'type': 'JudgmentResult',
        'group': row_id,
        'title': f"<b>裁判结果</b><br/>效力: {binding_force}<br/>层级: {guiding.get('case_level','')}<br/>裁判要旨: {guiding_points[:300]}",
        'level': 2
    })
    edges.append({'from': gc_id, 'to': jr_id, 'label': 'has_result'})
    edges.append({'from': jr_id, 'to': ct_id, 'label': 'determines'})

    case_graphs.append({
        'row_id': row_id,
        'case_name': case_name,
        'case_type': level2,
        'version': case.get('version', 1),
        'nodes': nodes,
        'edges': edges
    })

print(f"Built {len(case_graphs)} case graphs")

# Generate HTML
html_parts = []
html_parts.append("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>行政案件解析结果图结构可视化</title>
<script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: #f5f7fa; color: #333; }
.header {
  background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
  color: white; padding: 18px 30px;
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.header h1 { font-size: 22px; font-weight: 600; }
.header .subtitle { font-size: 13px; opacity: 0.8; margin-top: 4px; }
.control-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 30px; background: white;
  border-bottom: 1px solid #e0e0e0; flex-wrap: wrap;
}
.control-bar label { font-weight: 600; font-size: 14px; white-space: nowrap; }
.control-bar select {
  padding: 7px 14px; border: 1px solid #ccc; border-radius: 6px;
  font-size: 14px; min-width: 300px; background: white; cursor: pointer;
}
.control-bar select:focus { border-color: #3f51b5; outline: none; box-shadow: 0 0 0 2px rgba(63,81,181,0.2); }
.btn-group { display: flex; gap: 6px; flex-wrap: wrap; }
.btn {
  padding: 6px 16px; border: 1px solid #ccc; border-radius: 6px;
  font-size: 13px; cursor: pointer; background: white; transition: all 0.15s;
}
.btn:hover { background: #f0f0f0; }
.btn.active { background: #3f51b5; color: white; border-color: #3f51b5; }
.btn.info { background: #e8eaf6; border-color: #3f51b5; color: #283593; }
.case-list-panel {
  position: fixed; right: 0; top: 0; width: 320px; height: 100vh;
  background: white; box-shadow: -2px 0 12px rgba(0,0,0,0.1);
  z-index: 10; transform: translateX(100%); transition: transform 0.3s ease;
  display: flex; flex-direction: column;
}
.case-list-panel.open { transform: translateX(0); }
.case-list-panel .panel-header {
  padding: 16px 20px; background: #283593; color: white;
  font-weight: 600; font-size: 16px;
  display: flex; justify-content: space-between; align-items: center;
}
.case-list-panel .panel-header .close-btn {
  background: none; border: none; color: white; font-size: 22px; cursor: pointer;
  line-height: 1;
}
.case-list-scroll { flex: 1; overflow-y: auto; padding: 8px 0; }
.case-list-item {
  padding: 12px 20px; border-bottom: 1px solid #f0f0f0;
  cursor: pointer; transition: background 0.1s;
}
.case-list-item:hover { background: #e8eaf6; }
.case-list-item .case-name { font-weight: 500; font-size: 14px; }
.case-list-item .case-meta { font-size: 12px; color: #999; margin-top: 3px; }
.case-list-item.active { background: #c5cae9; }
#mynetwork {
  width: 100%; height: calc(100vh - 130px);
  background: white;
}
/* Detail Panel (same style as ontology) */
#detailPanel {
  position: fixed; right: -420px; top: 130px; width: 400px;
  height: calc(100vh - 130px); z-index: 998;
  background: rgba(255,255,255,0.98); box-shadow: -4px 0 20px rgba(0,0,0,0.15);
  transition: right 0.3s ease; overflow-y: auto; overflow-x: hidden;
  font-size: 13px; color: #333; border-left: 1px solid #e0e0e0;
  display: flex; flex-direction: column;
}
#detailPanel.open { right: 0; }
#detailPanel .panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%);
  color: #fff; position: sticky; top: 0; z-index: 1;
}
#detailPanel .panel-header h2 { font-size: 15px; font-weight: 600; margin:0; }
#detailPanel .panel-close {
  background: none; border: none; color: #fff; font-size: 20px;
  cursor: pointer; padding: 0 4px; opacity: 0.7; line-height: 1;
}
#detailPanel .panel-close:hover { opacity: 1; }
#detailPanel .panel-body { padding: 14px 18px 80px; flex: 1; }
#detailPanel .panel-section { margin-bottom: 16px; }
#detailPanel .panel-section-title {
  font-size: 12px; font-weight: 600; color: #888; text-transform: uppercase;
  letter-spacing: 0.5px; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #eee;
}
#detailPanel .field-row { display: flex; align-items: baseline; gap: 6px; padding: 3px 0; font-size: 13px; }
#detailPanel .desc-text { font-size: 13px; color: #555; line-height: 1.6; padding: 6px 0; }
#detailPanel .empty-hint { color: #bbb; font-style: italic; font-size: 12px; padding: 4px 0; }
#detailPanel.edge-mode .panel-header { background: linear-gradient(135deg, #2c3e50 0%, #34495e 50%); }
#detailPanel::-webkit-scrollbar { width: 6px; }
#detailPanel::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }

/* Legend — tree style */
.legend {
  position: fixed; top: 140px; left: 16px; z-index: 999;
  background: rgba(255,255,255,0.96); border-radius: 10px;
  padding: 12px 14px; box-shadow: 0 2px 12px rgba(0,0,0,0.15);
  font-size: 13px; line-height: 1.6; border: 1px solid #e8e8e8;
  max-height: calc(100vh - 160px); overflow-y: auto;
}
.legend::-webkit-scrollbar { width: 4px; }
.legend::-webkit-scrollbar-thumb { background: #ddd; border-radius: 2px; }
.legend-title { font-weight: 600; margin-bottom: 6px; font-size: 14px; color: #333; }
.legend-root { font-weight: 600; font-size: 13px; margin: 5px 0 2px 0; display: flex; align-items: center; gap: 6px; }
.legend-root .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; border: 1px solid rgba(0,0,0,0.15); flex-shrink: 0; }
.legend-children { padding-left: 20px; }
.legend-child { font-size: 12px; color: #555; padding: 1px 0; display: flex; align-items: center; gap: 6px; }
.legend-child .cdot { width: 8px; height: 8px; border-radius: 4px; display: inline-block; flex-shrink: 0; }

/* Version selector */
.version-control { display: none; align-items: center; gap: 6px; }
.version-control label { font-weight: 600; font-size: 13px; white-space: nowrap; }
.version-control select { padding: 5px 10px; border: 1px solid #bbb; border-radius: 5px; font-size: 13px; }

/* Raw Data Panel */
#rawDataPanel {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 997;
  background: rgba(255,255,255,0.97); border-top: 1px solid #ddd;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.08);
  max-height: 0; overflow: hidden; transition: max-height 0.3s ease;
}
#rawDataPanel.open { max-height: 240px; overflow-y: auto; }
#rawDataPanel .raw-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 18px; background: #f5f5f5; border-bottom: 1px solid #eee;
  cursor: pointer; font-size: 13px; font-weight: 600; color: #555;
  position: sticky; top: 0;
}
#rawDataPanel .raw-content {
  padding: 10px 18px 16px; font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px; color: #333; white-space: pre-wrap; word-break: break-all;
  line-height: 1.5; max-height: 180px; overflow-y: auto;
}
.stats { font-size: 13px; color: #666; }
.loading {
  display: flex; align-items: center; justify-content: center;
  height: 400px; font-size: 18px; color: #999;
}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>&#x2696;&#xFE0F; 行政案件解析结果 &middot; 知识图谱可视化</h1>
    <div class="subtitle">共 <span id="totalCases">0</span> 个行政案例 &middot; 力导向图结构</div>
  </div>
  <button class="btn" style="background:rgba(255,255,255,0.15);color:white;border-color:rgba(255,255,255,0.3);" onclick="toggleCaseList()">
    &#x1F4CB; 案件列表
  </button>
</div>

<div class="control-bar">
  <label for="caseSelect">&#x1F50D; 选择案例：</label>
  <select id="caseSelect" onchange="filterByCase(this.value)">
    <option value="all">&#x1F4CC; 全部案例（默认同色系区分）</option>
  </select>
  <div class="btn-group">
    <button class="btn active" onclick="setLayout(this,'force')">&#x26A1; 力导向</button>
    <button class="btn" onclick="setLayout(this,'hierarchical')">&#x1F4D0; 层级布局</button>
    <button class="btn info" onclick="fitView()">&#x1F532; 适应视图</button>
  </div>
  <span class="stats" id="stats"></span>
  <div class="version-control" id="versionWrapper">
    <label>版本：</label>
    <select id="versionSelect" onchange="switchVersion(this.value)"></select>
  </div>
</div>

<div id="mynetwork">
  <div class="loading">正在加载数据...</div>
</div>

<div class="legend">
  <div class="legend-title">📋 实体类型</div>
</div>

<!-- Detail Panel -->
<div id="detailPanel">
  <div class="panel-header">
    <h2 id="panelTitle">📋 详细信息</h2>
    <button class="panel-close" id="panelClose" title="关闭">✕</button>
  </div>
  <div class="panel-body" id="panelBody">
    <div class="empty-hint">悬停或点击节点/边查看详细信息</div>
  </div>
</div>

<!-- Raw Data Panel -->
<div id="rawDataPanel" class="open">
  <div class="raw-header" onclick="toggleRawData()">
    <span>📄 原始数据</span>
    <span id="rawDataLabel">收起</span>
  </div>
  <div class="raw-content" id="rawContent">选择案例后显示原始JSON数据</div>
</div>

<!-- Case List Panel -->
<div class="case-list-panel" id="caseListPanel">
  <div class="panel-header">
    <span>&#x1F4CB; 案件列表</span>
    <button class="close-btn" onclick="toggleCaseList()">&times;</button>
  </div>
  <div class="case-list-scroll" id="caseListScroll"></div>
</div>

<script>
""")

# Embed all graph data as JSON + raw data
all_graphs_json = json.dumps(case_graphs, ensure_ascii=False)
all_raw_json = json.dumps(raw_data, ensure_ascii=False)
html_parts.append(f"const ALL_GRAPHS = {all_graphs_json};\n")
html_parts.append(f"const RAW_DATA = {all_raw_json};\n\n")

html_parts.append("""
let network = null;
let nodesDataset = null;
let edgesDataset = null;
let currentFilter = 'all';
let isPanelLocked = false;
let currentSelection = null;

// ===== Color scheme from ontology (matched by entity type → root class) =====
const ROOT_COLORS = {
  'LegalNorm':      { bg: '#2980b9', border: '#1a5276' },
  'JudicialEntity': { bg: '#d35400', border: '#a04000' },
  'LegalSubject':   { bg: '#27ae60', border: '#1e8449' },
  'Person':         { bg: '#16a085', border: '#0e6655' },
};

// Admin entity type → ontology root class
const ADMIN_TYPE_ROOT = {
  'GuidingCase':    'LegalNorm',
  'LegalProvision': 'LegalNorm',
  'CourtCase':      'JudicialEntity',
  'CaseSummary':    'JudicialEntity',
  'Evidence':       'JudicialEntity',
  'JudgmentResult': 'JudicialEntity',
  'LegalSubject':   'LegalSubject',
};

// Node shapes by type (keep distinguishing)
const ADMIN_SHAPES = {
  'GuidingCase':    'hexagon',
  'CourtCase':      'box',
  'CaseSummary':    'ellipse',
  'JudgmentResult': 'diamond',
  'Evidence':       'ellipse',
  'LegalSubject':   'ellipse',
  'LegalProvision': 'ellipse',
};

function getAdminColor(typeName) {
  const root = ADMIN_TYPE_ROOT[typeName];
  const c = ROOT_COLORS[root];
  return c || { bg: '#7f8c8d', border: '#5d6d7e' };
}

function lightenColor(hex, percent) {
  const num = parseInt(hex.slice(1), 16);
  const amt = Math.round(2.55 * percent);
  const R = Math.min(255, (num >> 16) + amt);
  const G = Math.min(255, ((num >> 8) & 0x00FF) + amt);
  const B = Math.min(255, (num & 0x0000FF) + amt);
  return '#' + ((1 << 24) + (R << 16) + (G << 8) + B).toString(16).slice(1);
}

// Build vis data
function buildVisData(filterCaseId) {
  const visNodes = [];
  const visEdges = [];
  const nodeSet = new Set();
  const edgeSet = new Set();

  let filtered = ALL_GRAPHS;
  if (filterCaseId && filterCaseId !== 'all') {
    filtered = ALL_GRAPHS.filter(g => {
      const key = g.version ? g.row_id + '__v' + g.version : g.row_id;
      return key === filterCaseId || g.row_id === filterCaseId;
    });
  }

  for (const g of filtered) {
    for (const n of g.nodes) {
      if (nodeSet.has(n.id)) continue;
      nodeSet.add(n.id);
      const c = getAdminColor(n.type);
      const isLawGroup = n.group === 'law';
      const bg = isLawGroup ? c.bg : lightenColor(c.bg, (n.level || 0) >= 2 ? 40 : 0);
      visNodes.push({
        id: n.id,
        label: n.label,
        title: n.title,
        shape: ADMIN_SHAPES[n.type] || 'ellipse',
        size: n.level === 0 ? 35 : n.level === 1 ? 26 : 20,
        color: { background: bg, border: c.border },
        font: { color: '#fff', size: n.level === 0 ? 14 : 12, face: 'Microsoft YaHei, PingFang SC, sans-serif' },
        borderWidth: 2,
        group: n.group,
        nodeType: n.type,
      });
    }
    for (const e of g.edges) {
      const key = e.from + '|' + e.to + '|' + e.label;
      if (edgeSet.has(key)) continue;
      edgeSet.add(key);
      const ec = '#7f8c8d';
      visEdges.push({
        from: e.from, to: e.to, label: e.label,
        color: { color: ec, highlight: '#333', hover: '#333', opacity: 0.7 },
        font: { size: 10, color: '#555', strokeWidth: 2, strokeColor: '#fff' },
        width: 1.5, smooth: { type: 'continuous' },
        arrows: { to: { enabled: true, scaleFactor: 0.6 } },
      });
    }
  }
  return { nodes: visNodes, edges: visEdges };
}

function initNetwork(filterCaseId) {
  const container = document.getElementById('mynetwork');
  container.innerHTML = '';

  const data = buildVisData(filterCaseId);
  if (data.nodes.length === 0) {
    container.innerHTML = '<div class="loading">&#x274C; 无数据</div>';
    document.getElementById('stats').textContent = '0 nodes, 0 edges';
    return;
  }
  nodesDataset = new vis.DataSet(data.nodes);
  edgesDataset = new vis.DataSet(data.edges);
  const networkData = { nodes: nodesDataset, edges: edgesDataset };

  const options = {
    physics: {
      enabled: true, solver: 'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.005, springLength: 180, springConstant: 0.08, damping: 0.4 },
      stabilization: { iterations: 150, fit: true },
      minVelocity: 0.5,
    },
    interaction: { hover: true, tooltipDelay: 100, navigationButtons: true, keyboard: true, zoomView: true, dragView: true },
    edges: { smooth: { type: 'continuous' }, font: { size: 10, color: '#555', face: 'Microsoft YaHei' } },
    nodes: { font: { face: 'Microsoft YaHei, PingFang SC, sans-serif' }, borderWidth: 2, shadow: { enabled: true, size: 3, x: 0, y: 0 } },
    layout: { improvedLayout: true, randomSeed: 42 },
  };

  network = new vis.Network(container, networkData, options);

  // Freeze physics after stabilization
  network.on('stabilizationIterationsDone', function() {
    network.setOptions({ physics: { enabled: false } });
    network.fit({ animation: true });
  });

  document.getElementById('stats').textContent = data.nodes.length + ' nodes, ' + data.edges.length + ' edges';
  document.getElementById('totalCases').textContent = filtered.length;
  updateCaseListHighlight(filterCaseId);
}

network.on('hoverNode', function(params) {
  if (isPanelLocked) return;
  if (currentSelection === 'node:' + params.node) return;
  showAdminEntityDetail(params.node, params.pointer.DOM);
});

network.on('hoverEdge', function(params) {
  if (isPanelLocked) return;
  if (currentSelection === 'edge:' + params.edge) return;
  showAdminEdgeDetail(params.edge);
});

network.on('click', function(params) {
  if (params.nodes.length > 0) {
    showAdminEntityDetail(params.nodes[0], null);
  } else if (params.edges.length > 0) {
    showAdminEdgeDetail(params.edges[0]);
  } else {
    if (isPanelLocked) hideAdminPanel();
  }
});

// ===== Detail Panel =====
var detailPanel = document.getElementById('detailPanel');
var panelTitle = document.getElementById('panelTitle');
var panelBody = document.getElementById('panelBody');
var panelClose = document.getElementById('panelClose');

panelClose.addEventListener('click', function(e) { e.stopPropagation(); hideAdminPanel(); });
document.addEventListener('click', function(e) {
  if (isPanelLocked && !detailPanel.contains(e.target) && e.target !== panelClose) hideAdminPanel();
});
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && detailPanel.classList.contains('open')) hideAdminPanel();
});
detailPanel.addEventListener('mousedown', function(e) { e.stopPropagation(); });

function showAdminEntityDetail(nodeId, pointer) {
  // Find the ALL_GRAPHS entry for this node
  var nodeData = null;
  var caseInfo = null;
  for (var i = 0; i < ALL_GRAPHS.length; i++) {
    var g = ALL_GRAPHS[i];
    for (var j = 0; j < g.nodes.length; j++) {
      if (g.nodes[j].id === nodeId) {
        nodeData = g.nodes[j];
        caseInfo = g;
        break;
      }
    }
    if (nodeData) break;
  }
  if (!nodeData) {
    panelBody.innerHTML = '<div class="empty-hint">节点信息不可用</div>';
    return;
  }

  detailPanel.classList.remove('edge-mode');
  panelTitle.textContent = '📋 ' + (nodeData.type || '节点');
  var html = '';
  html += '<div class="panel-section"><div class="panel-section-title">📌 类型</div>';
  html += '<div class="desc-text">' + (nodeData.type || '未知') + '</div></div>';

  html += '<div class="panel-section"><div class="panel-section-title">📌 标签</div>';
  html += '<div class="desc-text">' + (nodeData.label || '') + '</div></div>';

  if (caseInfo) {
    html += '<div class="panel-section"><div class="panel-section-title">📌 所属案例</div>';
    html += '<div class="desc-text">' + (caseInfo.case_name || '') + ' (#' + caseInfo.row_id + ')</div></div>';
  }

  // Show title content (rich HTML tooltip)
  if (nodeData.title) {
    var plainTitle = nodeData.title.replace(/<[^>]*>/g, '');
    html += '<div class="panel-section"><div class="panel-section-title">📌 详细信息</div>';
    html += '<div class="desc-text" style="font-size:12px;white-space:pre-wrap;">' + plainTitle + '</div></div>';
  }

  panelBody.innerHTML = html;
  detailPanel.classList.add('open');
  isPanelLocked = true;
  currentSelection = 'node:' + nodeId;
}

function showAdminEdgeDetail(edgeId) {
  var allEdges = edgesDataset ? edgesDataset.get(edgeId) : null;
  if (!allEdges) return;
  detailPanel.classList.add('edge-mode');
  panelTitle.textContent = '🔗 ' + (allEdges.label || '关系边');
  var html = '';
  html += '<div class="panel-section"><div class="panel-section-title">📌 关系</div>';
  html += '<div class="desc-text">' + (allEdges.label || '') + '</div></div>';

  html += '<div class="panel-section"><div class="panel-section-title">📌 方向</div>';
  html += '<div class="field-row"><span style="font-weight:500;">' + allEdges.from + '</span> → <span style="font-weight:500;">' + allEdges.to + '</span></div></div>';

  panelBody.innerHTML = html;
  detailPanel.classList.add('open');
  isPanelLocked = true;
  currentSelection = 'edge:' + edgeId;
}

function hideAdminPanel() {
  detailPanel.classList.remove('open');
  isPanelLocked = false;
  currentSelection = null;
}

// ===== Version-aware filter =====
function filterByCase(value) {
  currentFilter = value;
  document.getElementById('caseSelect').value = value;
  // Extract row_id from compound key
  var rid = value.split('__')[0];
  initNetwork(value === 'all' ? null : value);

  // Show/hide version selector
  var verWrapper = document.getElementById('versionWrapper');
  if (verWrapper) {
    verWrapper.style.display = 'none';
  }
  if (value && value !== 'all') {
    // Count versions for this row_id
    var versions = [];
    for (var i = 0; i < ALL_GRAPHS.length; i++) {
      if (ALL_GRAPHS[i].row_id === rid) versions.push(ALL_GRAPHS[i]);
    }
    if (versions.length > 1 && verWrapper) {
      verWrapper.style.display = 'inline-flex';
      var verSelect = document.getElementById('versionSelect');
      versionSelect.innerHTML = '';
      for (var v = 0; v < versions.length; v++) {
        var opt = document.createElement('option');
        opt.value = rid + '__v' + (v + 1);
        opt.textContent = 'v' + (v + 1);
        if (opt.value === value) opt.selected = true;
        verSelect.appendChild(opt);
      }
    }
  }

  // Show raw data
  showRawData(value);
}

function switchVersion(val) {
  filterByCase(val);
}

// ===== Legend (tree style, matching ontology) =====
function buildAdminLegend() {
  var roots = ['LegalNorm', 'JudicialEntity', 'LegalSubject'];
  var rootNames = {'LegalNorm':'规范层', 'JudicialEntity':'司法实体层', 'LegalSubject':'主体层'};
  var rootColors = {'LegalNorm':'#2980b9', 'JudicialEntity':'#d35400', 'LegalSubject':'#27ae60'};
  var children = {
    'LegalNorm': ['GuidingCase', 'LegalProvision'],
    'JudicialEntity': ['CourtCase', 'CaseSummary', 'Evidence', 'JudgmentResult'],
    'LegalSubject': ['LegalSubject'],
  };
  var html = '';
  roots.forEach(function(root) {
    var c = rootColors[root];
    var label = root + ' (' + (rootNames[root] || '') + ')';
    html += '<div class="legend-root">';
    html += '<span class="dot" style="background:' + c + ';"></span>';
    html += '<span>' + label + '</span></div>';
    html += '<div class="legend-children">';
    var kids = children[root] || [];
    kids.sort();
    kids.forEach(function(k) {
      var kc = ROOT_COLORS[root] || {bg:'#7f8c8d'};
      var shape = ADMIN_SHAPES[k] || 'ellipse';
      var shapeIcon = shape === 'hexagon' ? '⬡' : shape === 'box' ? '▢' : shape === 'diamond' ? '◇' : '○';
      html += '<div class="legend-child">';
      html += '<span class="cdot" style="background:' + kc.bg + ';"></span>';
      html += '<span>' + shapeIcon + ' ' + k + '</span>';
      html += '</div>';
    });
    html += '</div>';
  });
  document.querySelector('.legend').innerHTML = '<div class="legend-title">📋 实体类型</div>' + html;
}

// ===== Raw Data Panel =====
var rawDataOpen = true;
function toggleRawData() {
  rawDataOpen = !rawDataOpen;
  var panel = document.getElementById('rawDataPanel');
  panel.classList.toggle('open', rawDataOpen);
  document.getElementById('rawDataLabel').textContent = rawDataOpen ? '收起' : '展开';
}
function showRawData(filterVal) {
  var content = document.getElementById('rawContent');
  if (!filterVal || filterVal === 'all') {
    content.textContent = '选择单个案例后显示原始JSON数据';
    return;
  }
  var raw = RAW_DATA[filterVal];
  if (raw) {
    try {
      var parsed = JSON.parse(raw);
      content.textContent = JSON.stringify(parsed, null, 2);
    } catch(e) {
      content.textContent = raw;
    }
  } else {
    content.textContent = '未找到该版本的原始数据';
  }
}

// ===== Legacy UI functions =====
function setLayout(btn, mode) {
  document.querySelectorAll('.btn-group .btn').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  if (!network) return;
  if (mode === 'force') {
    network.setOptions({ physics: { enabled: true, solver: 'forceAtlas2Based' }, layout: { improvedLayout: true, hierarchical: { enabled: false } } });
  } else {
    network.setOptions({ physics: { enabled: false }, layout: { improvedLayout: true, hierarchical: { enabled: true, direction: 'LR', sortMethod: 'directed', nodeSpacing: 150, levelSeparation: 200 } } });
  }
}
function fitView() { if (network) network.fit({ animation: true }); }
function toggleCaseList() { document.getElementById('caseListPanel').classList.toggle('open'); }
function updateCaseListHighlight(filterCaseId) {
  document.querySelectorAll('.case-list-item').forEach(function(el) {
    el.classList.toggle('active', el.dataset.rowId === filterCaseId || (!filterCaseId || filterCaseId === 'all'));
  });
}
function selectFromList(rowId) { filterByCase(rowId); if (rowId !== 'all') document.getElementById('caseListPanel').classList.remove('open'); }

// Populate
function populateSelectors() {
  const select = document.getElementById('caseSelect');
  const listScroll = document.getElementById('caseListScroll');
  let listHtml = '<div class=\"case-list-item\" data-row-id=\"all\" onclick=\"selectFromList(\\'all\\')\"><div class=\"case-name\">&#x1F4CC; 全部案例</div><div class=\"case-meta\">显示所有行政案例</div></div>';

  const sorted = ALL_GRAPHS.slice().sort(function(a, b) { return parseInt(a.row_id) - parseInt(b.row_id); });

  // Track seen row_ids to avoid duplicate names in list (but keep versioned compound keys)
  var seen = {};
  for (let i = 0; i < sorted.length; i++) {
    const g = sorted[i];
    const valKey = g.version ? g.row_id + '__v' + g.version : g.row_id;
    const displayName = g.version ? '[' + g.row_id + '] ' + g.case_name + ' (v' + g.version + ')' : '[' + g.row_id + '] ' + g.case_name;
    
    const opt = document.createElement('option');
    opt.value = valKey;
    opt.textContent = displayName;
    select.appendChild(opt);

    // Only add to list if we haven't seen this row_id before (dedup list display)
    if (!seen[g.row_id]) {
      seen[g.row_id] = true;
      listHtml += '<div class=\"case-list-item\" data-row-id=\"' + g.row_id + '\" onclick=\"selectFromList(\\'' + g.row_id + '\\')\">' +
        '<div class=\"case-name\">' + g.case_name + '</div>' +
        '<div class=\"case-meta\">#' + g.row_id + ' &middot; ' + (g.case_type || '') + '</div></div>';
    }
  }
  listScroll.innerHTML = listHtml;
}

buildAdminLegend();
populateSelectors();
initNetwork(null);

window.addEventListener('resize', function() { if (network) network.fit({ animation: false }); });

</script>
</body>
</html>
""")

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write(''.join(html_parts))

print(f"HTML generated: {OUTPUT_PATH}")
print(f"File size: {os.path.getsize(OUTPUT_PATH):,} bytes")
