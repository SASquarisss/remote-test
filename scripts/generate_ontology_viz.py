#!/usr/bin/env python3
"""
Legal Ontology Visualizer
=========================
Reads legal_ontology_v2.yaml + legal_ontology_v2.zh.yaml and generates
an interactive HTML visualization (vis-network, drag-enabled, bilingual).

Usage:
    python scripts/generate_ontology_viz.py
    # -> outputs ontology_viz.html at repo root
"""

import json
import yaml
from pathlib import Path
from collections import deque

REPO = Path(__file__).resolve().parent.parent
YAML_EN = REPO / "ontology/schemas/legal_ontology_v2.yaml"
YAML_ZH = REPO / "ontology/schemas/legal_ontology_v2.zh.yaml"
OUT_HTML = REPO / "ontology_viz.html"

# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------
def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def extract_zh_desc(yaml_zh: dict, key: str) -> str:
    """Extract Chinese description from zh YAML (handling inline comments)."""
    types = yaml_zh.get("types", {})
    if key in types:
        d = types[key].get("description", "")
        if d:
            return d.strip('"').split("  #")[0].strip('"')
    relations = yaml_zh.get("relations", {})
    if key in relations:
        d = relations[key].get("description", "")
        if d:
            return d.strip('"').split("  #")[0].strip('"')
    return ""

# ---------------------------------------------------------------------------
# Color palette (clean, same semantic group same color)
# ---------------------------------------------------------------------------
GROUP_COLORS = {
    "legal_norm":   "#2980b9",   # 规范层: Law, Provision, GuidingCase...
    "judicial_ent": "#d35400",   # 案件层: CourtCase, JudgmentResult...
    "legal_role":   "#8e44ad",   # 角色/辖区
    "subject_org":  "#27ae60",   # 主体-组织
    "subject_ppl":  "#16a085",   # 主体-自然人
    "root":         "#2c3e50",   # 顶层抽象
}

SEMANTIC_ROOT_MAP = {
    "LegalNorm":      "legal_norm",
    "JudicialEntity": "judicial_ent",
    "LegalSubject":   "subject_org",
    "Person":         "subject_ppl",
}

def get_semantic_group(node_id: str, nodes: dict) -> str:
    """Walk is_a chain to find semantic root."""
    visited = set()
    cur = node_id
    while cur and cur not in visited:
        visited.add(cur)
        if cur in SEMANTIC_ROOT_MAP:
            return SEMANTIC_ROOT_MAP[cur]
        cur = nodes.get(cur, {}).get("is_a")
    # fallback by heuristic
    if "Court" in node_id or "Procuratorate" in node_id or "LawFirm" in node_id or "ExpertInstitution" in node_id or "Organization" == node_id:
        return "subject_org"
    if "Judge" in node_id or "Attorney" in node_id or "Clerk" in node_id or "Prosecutor" in node_id or "Person" == node_id:
        return "subject_ppl"
    if "LegalRole" == node_id or "District" == node_id:
        return "legal_role"
    return "root"


def build_graph(yaml_en: dict, yaml_zh: dict):
    nodes = {}
    edges = []

    types = yaml_en.get("types", {})
    relations = yaml_en.get("relations", {})

    # --- nodes from types ---
    for name, spec in types.items():
        if name == "typically_applies":
            continue
        is_a = spec.get("is_a")
        desc_en = (spec.get("description") or "").strip('"')
        desc_zh = extract_zh_desc(yaml_zh, name)
        label = f"{name}\n{desc_zh}" if desc_zh else name
        nodes[name] = {
            "id": name,
            "label": label,
            "title": f"<b>{name}</b><br/>{desc_en}",
            "group": "type",
            "is_a": is_a,
        }

    # --- assign semantic groups & colors ---
    for name, d in nodes.items():
        group = get_semantic_group(name, nodes)
        d["color"] = GROUP_COLORS.get(group, GROUP_COLORS["root"])
        d["semantic_group"] = group

    # --- compute display level for hierarchical layout ---
    # BFS from known roots, but keep different roots in different columns
    roots = list(SEMANTIC_ROOT_MAP.keys())
    level_map = {r: 0 for r in roots}
    q = deque(roots)
    while q:
        cur = q.popleft()
        for name, d in nodes.items():
            if d["is_a"] == cur and name not in level_map:
                level_map[name] = level_map[cur] + 1
                q.append(name)
    for name, d in nodes.items():
        d["level"] = level_map.get(name, 0)

    # --- edges: inheritance (is_a) ---
    for name, d in nodes.items():
        if d["is_a"] and d["is_a"] in nodes:
            edges.append({
                "from": d["is_a"],
                "to": name,
                "label": "is_a",
                "dashes": True,
                "color": {"color": "#bdc3c7", "opacity": 0.6},
                "arrows": "to",
                "width": 1,
            })

    # --- edges: relations ---
    for rel_name, rel_spec in relations.items():
        frm = rel_spec.get("from")
        to = rel_spec.get("to")
        if not frm or not to:
            continue
        targets = to if isinstance(to, list) else [to]
        desc_zh = extract_zh_desc(yaml_zh, rel_name)
        label = f"{rel_name}\n{desc_zh}" if desc_zh else rel_name
        for tgt in targets:
            if tgt not in nodes:
                nodes[tgt] = {
                    "id": tgt, "label": tgt, "title": tgt,
                    "group": "stub", "level": 0,
                    "color": GROUP_COLORS["root"], "semantic_group": "root"
                }
            edges.append({
                "from": frm,
                "to": tgt,
                "label": label,
                "dashes": False,
                "color": {"color": "#7f8c8d", "opacity": 0.7},
                "arrows": "to",
                "width": 2,
            })

    return list(nodes.values()), edges

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Legal Ontology v2.0 Visualization</title>
<script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f8f9fa; color: #2c3e50; overflow: hidden; }
  #header { position: fixed; top: 0; left: 0; right: 0; height: 48px; background: #fff; border-bottom: 1px solid #e9ecef; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; z-index: 10; }
  #header h1 { font-size: 16px; font-weight: 600; letter-spacing: 0.5px; }
  #header .legend { display: flex; gap: 16px; font-size: 12px; }
  #header .legend span { display: flex; align-items: center; gap: 6px; }
  #header .legend .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  #controls { position: fixed; top: 64px; right: 16px; z-index: 10; display: flex; flex-direction: column; gap: 8px; }
  #controls button { background: #fff; border: 1px solid #dee2e6; border-radius: 6px; padding: 6px 12px; font-size: 12px; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.05); transition: all .2s; }
  #controls button:hover { background: #f1f3f5; }
  #network { width: 100vw; height: 100vh; padding-top: 48px; }
  #tooltip { position: fixed; bottom: 16px; left: 16px; background: rgba(255,255,255,0.95); border: 1px solid #e9ecef; border-radius: 8px; padding: 12px 16px; font-size: 12px; max-width: 320px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); z-index: 10; display: none; }
</style>
</head>
<body>

<div id="header">
  <h1>📖 Legal Ontology v2.0 法律本体论可视化</h1>
  <div class="legend">
    <span><i class="dot" style="background:#2c3e50"></i>顶层抽象</span>
    <span><i class="dot" style="background:#2980b9"></i>规范层</span>
    <span><i class="dot" style="background:#27ae60"></i>主体-组织</span>
    <span><i class="dot" style="background:#16a085"></i>主体-自然人</span>
    <span><i class="dot" style="background:#d35400"></i>案件层</span>
    <span><i class="dot" style="background:#8e44ad"></i>深层/其他</span>
  </div>
</div>

<div id="controls">
  <button onclick="fitNetwork()">全局视图</button>
  <button onclick="togglePhysics()">开关物理引擎</button>
  <button onclick="toggleHierarchical()">开关层级布局</button>
</div>

<div id="network"></div>
<div id="tooltip"></div>

<script>
const nodesData = {nodes};
const edgesData = {edges};

const container = document.getElementById('network');

const nodes = new vis.DataSet(nodesData.map(n => ({{
  id: n.id,
  label: n.label,
  title: n.title,
  color: {{
    background: n.color,
    border: n.color,
    highlight: { background: n.color, border: '#2c3e50' }
  }},
  font: {{ color: '#fff', size: 13, face: 'Segoe UI, Microsoft YaHei, sans-serif', multi: 'html', strokeWidth: 0 }},
  shape: 'box',
  margin: {{ top: 8, bottom: 8, left: 12, right: 12 }},
  borderWidth: 0,
  shadow: {{ enabled: true, color: 'rgba(0,0,0,0.15)', size: 8, x: 2, y: 2 }},
  level: n.level,
  mass: n.level === 0 ? 3 : (n.level === 1 ? 2 : 1)
}})));

const edges = new vis.DataSet(edgesData.map(e => ({{
  from: e.from,
  to: e.to,
  label: e.label,
  dashes: e.dashes,
  color: e.color,
  arrows: e.arrows,
  width: e.width,
  font: {{ size: 10, color: '#7f8c8d', align: 'middle', background: 'rgba(255,255,255,0.8)', strokeWidth: 0 }},
  smooth: {{ type: 'cubicBezier', forceDirection: 'vertical', roundness: 0.4 }}
}})));

let hierarchical = true;
let physics = false;

const options = {{
  layout: {{
    hierarchical: {{
      enabled: hierarchical,
      direction: 'UD',
      sortMethod: 'directed',
      levelSeparation: 140,
      nodeSpacing: 180,
      treeSpacing: 240,
      blockShifting: true,
      edgeMinimization: true,
      parentCentralization: true
    }}
  }},
  physics: {{
    enabled: physics,
    hierarchicalRepulsion: {{
      centralGravity: 0.0,
      springLength: 140,
      springConstant: 0.01,
      nodeDistance: 160,
      damping: 0.09
    }},
    solver: 'hierarchicalRepulsion'
  }},
  interaction: {{
    hover: true,
    tooltipDelay: 200,
    dragNodes: true,
    dragView: true,
    zoomView: true
  }}
}};

const network = new vis.Network(container, {{ nodes, edges }}, options);

function fitNetwork() {{ network.fit({{ animation: {{ duration: 500, easingFunction: 'easeInOutQuad' }} }}); }}
function togglePhysics() {{
  physics = !physics;
  network.setOptions({{ physics: {{ enabled: physics }} }});
}}
function toggleHierarchical() {{
  hierarchical = !hierarchical;
  network.setOptions({{ layout: {{ hierarchical: {{ enabled: hierarchical }} }} }});
}}

// tooltip on hover
network.on("hoverNode", function (params) {{
  const node = nodes.get(params.node);
  const tooltip = document.getElementById('tooltip');
  tooltip.innerHTML = node.title;
  tooltip.style.display = 'block';
}});
network.on("blurNode", function () {{
  document.getElementById('tooltip').style.display = 'none';
}});

// fit once loaded
network.once("afterDrawing", fitNetwork);
</script>

</body>
</html>
"""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    yaml_en = load_yaml(YAML_EN)
    yaml_zh = load_yaml(YAML_ZH)

    node_list, edge_list = build_graph(yaml_en, yaml_zh)

    html = HTML_TEMPLATE.replace("{nodes}", json.dumps(node_list, ensure_ascii=False))
    html = html.replace("{edges}", json.dumps(edge_list, ensure_ascii=False))

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated: {OUT_HTML}")
    print(f"  Nodes: {len(node_list)}")
    print(f"  Edges: {len(edge_list)}")

if __name__ == "__main__":
    main()
