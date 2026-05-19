import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { ENTITY_DATA, ENTITY_STYLES, TYPE_NAMES, ZH_LABELS } from '../../data/schema.js';
import { getOntologyRelationEdges } from '../../data/relationModel.js';
import { escapeHtml } from '../../shared/utils/formatter.js';

function buildInheritanceHtml() {
  const roots = Object.keys(ENTITY_DATA).filter(key => !ENTITY_DATA[key].is_a);
  let html = '';

  roots.forEach(root => {
    const rootZh = ZH_LABELS[root] || root;
    const rootStyle = ENTITY_STYLES[root] || {};
    html += `<div class="schema-tree-root">`;
    html += `<span class="schema-tree-dot" style="background:${rootStyle.color || '#cbd5e1'};border-color:${rootStyle.border || '#94a3b8'};"></span>`;
    html += `<span>${escapeHtml(rootZh)}</span>`;
    html += `<em>${escapeHtml(root)}</em>`;
    html += `</div>`;

    const children = Object.keys(ENTITY_DATA).filter(key => ENTITY_DATA[key].is_a === root);
    if (children.length) {
      html += `<div class="schema-tree-children">`;
      children.forEach(child => {
        const childZh = ZH_LABELS[child] || child;
        const childStyle = ENTITY_STYLES[child] || {};
        html += `<div class="schema-tree-child" data-type="${escapeHtml(child)}">`;
        html += `<span class="schema-tree-dot small" style="background:${childStyle.color || '#cbd5e1'};border-color:${childStyle.border || '#94a3b8'};"></span>`;
        html += `<span>${escapeHtml(childZh)}</span>`;
        html += `<em>${escapeHtml(child)}</em>`;
        html += `</div>`;
      });
      html += `</div>`;
    }
  });

  return html;
}

function buildSchemaNodes() {
  return TYPE_NAMES.map(typeName => {
    const style = ENTITY_STYLES[typeName] || {};
    const fontColor = ['LegalProvision', 'Law', 'GuidingCase'].includes(typeName) ? '#ffffff' : '#0f172a';
    return {
      id: typeName,
      label: typeName,
      shape: style.shape || 'ellipse',
      size: style.size || 18,
      title: ZH_LABELS[typeName] || typeName,
      color: {
        background: style.color || '#f8fafc',
        border: style.border || '#cbd5e1',
        highlight: {
          background: style.color || '#e2e8f0',
          border: style.border || '#94a3b8'
        }
      },
      font: {
        size: 11,
        color: fontColor,
        strokeWidth: 2,
        strokeColor: '#ffffff'
      }
    };
  });
}

function buildSchemaEdges() {
  return getOntologyRelationEdges().map(edge => ({
    id: edge.id,
    from: edge.fromType,
    to: edge.toType,
    label: edge.label,
    relationType: edge.relationType,
    edgeSource: edge.source,
    description: edge.description,
    arrows: 'to',
    dashes: edge.source === 'derived' ? [6, 4] : false,
    color: edge.source === 'derived' ? { color: '#6366f1' } : { color: '#94a3b8' },
    font: {
      size: 10,
      color: edge.source === 'derived' ? '#4338ca' : '#64748b',
      align: 'horizontal',
      strokeWidth: 2,
      strokeColor: '#ffffff'
    },
    smooth: { type: 'continuous' }
  }));
}

export class DatabaseSchemaPanel {
  constructor({ store, containerId }) {
    this.store = store;
    this.container = document.getElementById(containerId);
    this.network = null;
    this.nodes = new DataSet();
    this.edges = new DataSet();
    this.ensureUI();
    this.initGraph();
    this.bindEvents();
    this.store.subscribe(state => this.render(state));
    this.render(this.store.getState());
  }

  ensureUI() {
    if (!this.container || this.container.children.length) return;
    this.container.innerHTML = `
      <div class="db-schema-shell">
        <div class="db-schema-header" id="dbSchemaHeader">
          <div class="db-schema-title-group">
            <div class="db-schema-title">本体导航</div>
            <div class="db-schema-subtitle">切换本体图谱或继承树，并联动当前案例图</div>
          </div>
          <div class="db-schema-tabs">
            <button class="db-schema-tab active" data-tab="graph">本体图谱</button>
            <button class="db-schema-tab" data-tab="inheritance">继承树</button>
          </div>
        </div>
        <div class="db-schema-content">
          <div id="dbSchemaGraphPane" class="db-schema-pane active">
            <div id="dbSchemaGraph" class="db-schema-graph"></div>
          </div>
          <div id="dbSchemaInheritancePane" class="db-schema-pane">
            <div id="dbSchemaInheritance" class="db-schema-inheritance">${buildInheritanceHtml()}</div>
          </div>
        </div>
        <div id="dbSchemaFooter" class="db-schema-footer">选择本体类型后，会高亮当前单案结构图中的对应节点。实线表示本体原生关系，虚线表示自动补图关系。</div>
      </div>
    `;
  }

  initGraph() {
    const host = document.getElementById('dbSchemaGraph');
    if (!host) return;

    this.nodes.add(buildSchemaNodes());
    this.edges.add(buildSchemaEdges());
    this.network = new Network(host, { nodes: this.nodes, edges: this.edges }, {
      layout: { improvedLayout: true, randomSeed: 42 },
      physics: {
        enabled: true,
        solver: 'barnesHut',
        barnesHut: {
          gravitationalConstant: -2600,
          centralGravity: 0.26,
          springLength: 120,
          springConstant: 0.04,
          damping: 0.48
        },
        stabilization: { iterations: 180, fit: true }
      },
      interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true, navigationButtons: false },
      edges: { selectionWidth: 1.5 }
    });

    this.network.on('stabilizationIterationsDone', () => {
      if (!this.network) return;
      this.network.setOptions({ physics: { enabled: false } });
      this.network.fit({ animation: true });
    });

    this.network.on('click', params => {
      if (!params.nodes.length) {
        this.store.update('graph', { selectedOntologyType: null });
        return;
      }
      const typeName = params.nodes[0];
      const current = this.store.getState().graph.selectedOntologyType;
      this.store.update('graph', { selectedOntologyType: current === typeName ? null : typeName });
    });

    this.network.on('hoverNode', params => {
      if (!params?.node) return;
      this.store.update('graph', { hoverOntologyType: params.node });
    });

    this.network.on('blurNode', () => {
      this.store.update('graph', { hoverOntologyType: null });
    });
  }

  bindEvents() {
    if (!this.container) return;
    this.container.addEventListener('click', event => {
      const tab = event.target.closest('.db-schema-tab');
      if (tab) {
        this.store.update('panels', { schemaTab: tab.getAttribute('data-tab') || 'graph' });
        return;
      }

      const inheritanceNode = event.target.closest('[data-type]');
      if (inheritanceNode) {
        const typeName = inheritanceNode.getAttribute('data-type');
        const current = this.store.getState().graph.selectedOntologyType;
        this.store.update('graph', { selectedOntologyType: current === typeName ? null : typeName });
      }
    });
  }

  render(state) {
    if (!this.container) return;
    const activeTab = state.panels.schemaTab || 'graph';
    const isOpen = Boolean(state.panels.schemaOpen);
    const selectedType = state.graph.selectedOntologyType;
    const hoverType = state.graph.hoverOntologyType;
    const activeType = selectedType || hoverType || null;
    const typeCounts = state.graph.renderedTypeCounts || {};

    this.container.classList.toggle('open', isOpen);

    this.container.querySelectorAll('.db-schema-tab').forEach(button => {
      button.classList.toggle('active', button.dataset.tab === activeTab);
    });
    this.container.querySelectorAll('.db-schema-pane').forEach(pane => pane.classList.remove('active'));
    const activePane = this.container.querySelector(activeTab === 'inheritance' ? '#dbSchemaInheritancePane' : '#dbSchemaGraphPane');
    if (activePane) activePane.classList.add('active');

    this.container.querySelectorAll('.schema-tree-child').forEach(node => {
      node.classList.toggle('active', node.getAttribute('data-type') === activeType);
    });

    if (this.network) {
      const updates = this.nodes.get().map(node => {
        const count = typeCounts[node.id] || 0;
        const baseLabel = count > 0 ? `${node.id} [${count}]` : node.id;
        const isActive = !!activeType && node.id === activeType;
        return {
          id: node.id,
          label: baseLabel,
          borderWidth: isActive ? 3 : 1.5,
          color: isActive
            ? { ...node.color, border: '#2563eb' }
            : node.color,
          font: {
            ...(node.font || {}),
            bold: count > 0 || isActive
          }
        };
      });
      this.nodes.update(updates);
      if (activeType && this.nodes.get(activeType)) {
        this.network.selectNodes([activeType], false);
      } else {
        this.network.unselectAll();
      }
    }

    const footer = document.getElementById('dbSchemaFooter');
    if (footer) {
      if (selectedType) {
        footer.textContent = `当前锁定本体类型：${selectedType}。点击空白或再次点击同一类型可取消。`;
      } else if (hoverType) {
        footer.textContent = `当前悬停本体类型：${hoverType}。`;
      } else {
        footer.textContent = '选择本体类型后，会高亮当前单案结构图中的对应节点。';
      }
    }
  }
}
