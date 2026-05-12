#!/usr/bin/env python3
"""
Generate admin case knowledge graph visualization HTML.
Reads extracted_v2.2_admin_all.jsonl filtered by admin_cases_only.csv row_ids.
"""
import json
import csv
import os

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

# Read JSONL and filter admin cases
cases = []
with open(JSONL_PATH, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        if data['row_id'] in admin_ids and data.get('output') is not None:
            cases.append(data)

print(f"Loaded {len(cases)} admin cases with output data")

# Build graph data per case
case_graphs = []
for case in cases:
    output = case['output']
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
.legend {
  position: fixed; bottom: 20px; left: 20px; background: rgba(255,255,255,0.95);
  border-radius: 8px; padding: 12px 16px; box-shadow: 0 2px 10px rgba(0,0,0,0.12);
  font-size: 13px; z-index: 5;
}
.legend-item { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
.legend-color {
  width: 14px; height: 14px; border-radius: 50%; border: 1px solid rgba(0,0,0,0.1);
  flex-shrink: 0;
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
</div>

<div id="mynetwork">
  <div class="loading">正在加载数据...</div>
</div>

<div class="legend">
  <div style="font-weight:600;margin-bottom:4px;font-size:14px;">图例</div>
  <div class="legend-item"><span class="legend-color" style="background:#e91e63;"></span> 指导案例/典型案例</div>
  <div class="legend-item"><span class="legend-color" style="background:#4caf50;"></span> 法院案件</div>
  <div class="legend-item"><span class="legend-color" style="background:#ff9800;"></span> 诉讼主体</div>
  <div class="legend-item"><span class="legend-color" style="background:#2196f3;"></span> 法律条文</div>
  <div class="legend-item"><span class="legend-color" style="background:#9c27b0;"></span> 裁判结果</div>
  <div class="legend-item"><span class="legend-color" style="background:#00bcd4;"></span> 证据</div>
  <div class="legend-item"><span class="legend-color" style="background:#607d8b;"></span> 案件类型</div>
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

# Embed all graph data as JSON
all_graphs_json = json.dumps(case_graphs, ensure_ascii=False)
html_parts.append(f"const ALL_GRAPHS = {all_graphs_json};\n\n")

html_parts.append("""
let network = null;
let nodesDataset = null;
let edgesDataset = null;
let currentFilter = 'all';

// Node type colors
const TYPE_COLORS = {
  'GuidingCase': { background: '#e91e63', border: '#c2185b', shape: 'hexagon', size: 35 },
  'CourtCase': { background: '#4caf50', border: '#388e3c', shape: 'box', size: 25 },
  'LegalSubject': { background: '#ff9800', border: '#f57c00', shape: 'ellipse', size: 22 },
  'LegalProvision': { background: '#2196f3', border: '#1976d2', shape: 'ellipse', size: 20 },
  'JudgmentResult': { background: '#9c27b0', border: '#7b1fa2', shape: 'diamond', size: 24 },
  'Evidence': { background: '#00bcd4', border: '#0097a7', shape: 'ellipse', size: 20 },
  'CaseSummary': { background: '#607d8b', border: '#455a64', shape: 'ellipse', size: 20 },
};

// Edge colors
const EDGE_COLORS = {
  'has_court_case': '#4caf50',
  'has_subject': '#ff9800',
  'references': '#2196f3',
  'applied_in': '#2196f3',
  'has_evidence': '#00bcd4',
  'has_result': '#9c27b0',
  'determines': '#9c27b0',
  'classified_as': '#607d8b',
};

// Case-specific color generation
function getCaseColor(rowId) {
  if (rowId === 'law') return { bg: '#2196f3', border: '#1565c0' };
  // Use row_id numeric value to pick from palette
  const palettes = [
    ['#e91e63','#c2185b'], ['#9c27b0','#7b1fa2'], ['#3f51b5','#303f9f'],
    ['#009688','#00796b'], ['#ff5722','#e64a19'], ['#795548','#5d4037'],
    ['#607d8b','#455a64'], ['#d81b60','#ad1457'], ['#8e24aa','#6a1b9a'],
    ['#3949ab','#283593'], ['#00897b','#00695c'], ['#f4511e','#d84315'],
    ['#6d4c41','#4e342e'], ['#546e7a','#37474f'], ['#c62828','#b71c1c'],
    ['#2e7d32','#1b5e20'], ['#1565c0','#0d47a1'], ['#6a1b9a','#4a148c'],
    ['#e65100','#bf360c'], ['#004d40','#00332c'], ['#311b92','#1a237e'],
    ['#880e4f','#4a0024'], ['#0d47a1','#002f6c'], ['#004d40','#00251a'],
    ['#1a237e','#000051'], ['#b71c1c','#7f0000'], ['#1b5e20','#003300'],
    ['#4a148c','#12005e'], ['#01579b','#00344d'], ['#bf360c','#870000'],
    ['#33691e','#1b3d00'], ['#827717','#4d4b00'], ['#e65100','#ac3a00'],
    ['#3e2723','#1b0000'], ['#004d40','#001b14'], ['#0d47a1','#002171'],
    ['#880e4f','#4d0024'],
  ];
  const idx = (parseInt(rowId) || 0) % palettes.length;
  return { bg: palettes[idx][0], border: palettes[idx][1] };
}

function lightenColor(hex, percent) {
  const num = parseInt(hex.slice(1), 16);
  const amt = Math.round(2.55 * percent);
  const R = Math.min(255, (num >> 16) + amt);
  const G = Math.min(255, ((num >> 8) & 0x00FF) + amt);
  const B = Math.min(255, (num & 0x0000FF) + amt);
  return `#${((1 << 24) + (R << 16) + (G << 8) + B).toString(16).slice(1)}`;
}

// Build vis data
function buildVisData(filterCaseId) {
  const visNodes = [];
  const visEdges = [];
  const nodeSet = new Set();
  const edgeSet = new Set();

  let filtered = ALL_GRAPHS;
  if (filterCaseId && filterCaseId !== 'all') {
    filtered = ALL_GRAPHS.filter(g => g.row_id === filterCaseId);
  }

  for (const g of filtered) {
    for (const n of g.nodes) {
      if (nodeSet.has(n.id)) continue;
      nodeSet.add(n.id);

      const tc = TYPE_COLORS[n.type] || { background: '#999', border: '#666', shape: 'ellipse', size: 20 };
      let color;
      if (n.group === 'law') {
        color = { background: '#2196f3', border: '#1565c0', highlight: { background: '#42a5f5', border: '#0d47a1' } };
      } else {
        const cc = getCaseColor(n.group);
        const isLight = (n.level || 0) >= 2;
        const bg = isLight ? lightenColor(cc.bg, 50) : cc.bg;
        color = {
          background: bg,
          border: cc.border,
          highlight: { background: lightenColor(cc.bg, isLight ? 30 : 20), border: cc.border }
        };
      }

      let size = tc.size || 20;
      if (n.level === 0) size = 40;
      else if (n.level === 1) size = 28;

      visNodes.push({
        id: n.id,
        label: n.label,
        title: n.title,
        shape: tc.shape,
        size: size,
        color: color,
        font: { color: '#222', size: 12, face: 'PingFang SC, Microsoft YaHei, sans-serif' },
        borderWidth: 2,
        borderWidthSelected: 3,
        group: n.group,
        nodeType: n.type,
      });
    }

    for (const e of g.edges) {
      const key = e.from + '|' + e.to + '|' + e.label;
      if (edgeSet.has(key)) continue;
      edgeSet.add(key);

      const ec = EDGE_COLORS[e.label] || '#999';
      visEdges.push({
        from: e.from,
        to: e.to,
        label: e.label,
        color: { color: ec, highlight: '#333', hover: '#333', opacity: 0.7 },
        font: { size: 10, color: '#666', strokeWidth: 2, strokeColor: '#fff' },
        width: 1.5,
        smooth: { type: 'continuous' },
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
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -40,
        centralGravity: 0.005,
        springLength: 180,
        springConstant: 0.08,
        damping: 0.4,
      },
      stabilization: { iterations: 150 },
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      navigationButtons: true,
      keyboard: true,
      multiselect: true,
    },
    edges: {
      smooth: { type: 'continuous' },
      arrows: { to: { enabled: true, scaleFactor: 0.6 } },
    },
    nodes: {
      font: { face: 'PingFang SC, Microsoft YaHei, sans-serif' },
    },
    layout: { improvedLayout: true },
  };

  network = new vis.Network(container, networkData, options);

  document.getElementById('stats').textContent =
    data.nodes.length + ' nodes, ' + data.edges.length + ' edges';
  document.getElementById('totalCases').textContent = filtered.length;

  updateCaseListHighlight(filterCaseId);
}

function filterByCase(value) {
  currentFilter = value;
  document.getElementById('caseSelect').value = value;
  initNetwork(value === 'all' ? null : value);
}

function setLayout(btn, mode) {
  document.querySelectorAll('.btn-group .btn').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  if (!network) return;
  if (mode === 'force') {
    network.setOptions({
      physics: { enabled: true, solver: 'forceAtlas2Based' },
      layout: { improvedLayout: true, hierarchical: { enabled: false } },
    });
  } else {
    network.setOptions({
      physics: { enabled: false },
      layout: {
        improvedLayout: true,
        hierarchical: {
          enabled: true,
          direction: 'LR',
          sortMethod: 'directed',
          nodeSpacing: 150,
          levelSeparation: 200,
        },
      },
    });
  }
}

function fitView() {
  if (network) network.fit({ animation: true });
}

function toggleCaseList() {
  document.getElementById('caseListPanel').classList.toggle('open');
}

function updateCaseListHighlight(filterCaseId) {
  document.querySelectorAll('.case-list-item').forEach(function(el) {
    el.classList.toggle('active', el.dataset.rowId === filterCaseId || (!filterCaseId || filterCaseId === 'all'));
  });
}

function selectFromList(rowId) {
  filterByCase(rowId);
  if (rowId !== 'all') {
    document.getElementById('caseListPanel').classList.remove('open');
  }
}

// Populate
function populateSelectors() {
  const select = document.getElementById('caseSelect');
  const listScroll = document.getElementById('caseListScroll');
  let listHtml = '<div class="case-list-item" data-row-id="all" onclick="selectFromList(\'all\')"><div class="case-name">&#x1F4CC; 全部案例</div><div class="case-meta">显示所有行政案例</div></div>';

  const sorted = ALL_GRAPHS.slice().sort(function(a, b) { return parseInt(a.row_id) - parseInt(b.row_id); });

  for (let i = 0; i < sorted.length; i++) {
    const g = sorted[i];
    const opt = document.createElement('option');
    opt.value = g.row_id;
    opt.textContent = '[' + g.row_id + '] ' + g.case_name;
    select.appendChild(opt);

    listHtml += '<div class="case-list-item" data-row-id="' + g.row_id + '" onclick="selectFromList(\'' + g.row_id + '\')">' +
      '<div class="case-name">' + g.case_name + '</div>' +
      '<div class="case-meta">#' + g.row_id + ' &middot; ' + (g.case_type || '') + '</div></div>';
  }

  listScroll.innerHTML = listHtml;
}

populateSelectors();
initNetwork(null);

window.addEventListener('resize', function() {
  if (network) network.fit({ animation: false });
});

</script>
</body>
</html>
""")

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write(''.join(html_parts))

print(f"HTML generated: {OUTPUT_PATH}")
print(f"File size: {os.path.getsize(OUTPUT_PATH):,} bytes")
