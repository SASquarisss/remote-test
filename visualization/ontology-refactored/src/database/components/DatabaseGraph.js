import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { buildDatabaseGraphData, getFilteredCases, getVisibleCases } from '../model/selectors.js';
import { ENTITY_DATA } from '../../data/schema.js';

function matchesOntologyType(nodeType, ontologyType) {
  if (!nodeType || !ontologyType) return false;
  if (nodeType === ontologyType) return true;

  let current = ENTITY_DATA[nodeType];
  while (current && current.is_a) {
    if (current.is_a === ontologyType) return true;
    current = ENTITY_DATA[current.is_a];
  }
  return false;
}

export class DatabaseGraph {
  constructor({ store, containerId, onStatsChange }) {
    this.store = store;
    this.container = document.getElementById(containerId);
    this.onStatsChange = onStatsChange;
    this.nodes = new DataSet();
    this.edges = new DataSet();
    this.network = null;
    this.lastMode = null;
    this.lastGraphSignature = '';
    this.currentGraphNodes = [];
    this.currentGraphEdges = [];
    this.lastAppliedOntologyType = null;
    this.fitTimer = null;
    this.manualNodePositions = new Map();
    this.init();
    this.store.subscribe(state => this.render(state));
  }

  init() {
    if (!this.container) return;
    this.network = new Network(this.container, { nodes: this.nodes, edges: this.edges }, {
      layout: { improvedLayout: true, randomSeed: 42 },
      physics: {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -60,
          centralGravity: 0.015,
          springLength: 160,
          springConstant: 0.08,
          damping: 0.5
        },
        stabilization: { iterations: 120, fit: true }
      },
      interaction: { hover: true, tooltipDelay: 100, navigationButtons: true, keyboard: true },
      nodes: {
        shadow: { enabled: true, size: 4, x: 0, y: 2 },
        font: { face: 'Microsoft YaHei, PingFang SC, sans-serif' }
      },
      edges: {
        smooth: { type: 'continuous' },
        font: { align: 'horizontal' }
      }
    });

    this.network.on('stabilizationIterationsDone', () => {
      if (!this.network) return;
      this.network.setOptions({ physics: { enabled: false } });
      this.network.fit({ animation: true });
    });

    this.network.on('dragEnd', params => {
      if (!this.network || !params.nodes.length) return;
      const positions = this.network.getPositions(params.nodes);
      const updates = params.nodes.map(nodeId => {
        const position = positions[nodeId];
        if (!position) return null;
        this.manualNodePositions.set(nodeId, position);
        return {
          id: nodeId,
          x: position.x,
          y: position.y,
          fixed: { x: true, y: true }
        };
      }).filter(Boolean);

      if (updates.length) {
        this.nodes.update(updates);
        this.currentGraphNodes = this.currentGraphNodes.map(node => {
          const position = positions[node.id];
          return position
            ? { ...node, x: position.x, y: position.y, fixed: { x: true, y: true } }
            : node;
        });
        this.network.setOptions({ physics: { enabled: false } });
      }
    });

    this.network.on('click', params => {
      if (params.nodes.length > 0) {
        const node = this.nodes.get(params.nodes[0]);
        if (!node) return;
        if (node.nodeType === 'SourceRoot') {
          this.store.update('selection', {
            activeNodeId: node.id,
            activeEdgeId: null,
            activeCaseKey: null,
            activeItem: { kind: 'source', id: node.id, label: node.label, caseCount: node.caseCount || 0 }
          });
          this.store.update('panels', { detailOpen: true });
          return;
        }

        this.store.update('selection', {
          activeNodeId: node.id,
          activeEdgeId: null,
          activeCaseKey: node.caseKey || this.store.getState().selection.activeCaseKey,
          activeItem: node.nodeType === 'CaseEntry' ? { kind: 'case', ...node } : { kind: 'node', ...node }
        });
        this.store.update('panels', { detailOpen: true });
        return;
      }

      if (params.edges.length > 0) {
        const edge = this.edges.get(params.edges[0]);
        if (!edge) return;
        this.store.update('selection', {
          activeEdgeId: edge.id,
          activeNodeId: null,
          activeCaseKey: edge.caseKey || this.store.getState().selection.activeCaseKey,
          activeItem: { kind: 'edge', ...edge }
        });
        this.store.update('panels', { detailOpen: true });
        return;
      }

      this.store.update('selection', {
        activeNodeId: null,
        activeEdgeId: null,
        activeItem: null
      });
      this.store.update('panels', { detailOpen: false });
    });
  }

  buildGraphSignature(graphData) {
    const nodeIds = (graphData.nodes || []).map(node => node.id).join('|');
    const edgeIds = (graphData.edges || []).map(edge => edge.id).join('|');
    return `${graphData.mode || 'overview'}::${nodeIds}::${edgeIds}`;
  }

  updateRenderedTypeCounts() {
    const typeCounts = {};
    this.currentGraphNodes.forEach(node => {
      if (node.nodeType) {
        typeCounts[node.nodeType] = (typeCounts[node.nodeType] || 0) + 1;
      }
    });

    if (JSON.stringify(this.store.getState().graph.renderedTypeCounts || {}) !== JSON.stringify(typeCounts)) {
      this.store.update('graph', { renderedTypeCounts: typeCounts });
    }
  }

  applyOntologyHighlight(activeOntologyType) {
    if (!this.currentGraphNodes.length) return;

    const mode = this.lastMode || 'overview';
    const baseNodes = this.currentGraphNodes;
    const baseEdges = this.currentGraphEdges;

    if (mode !== 'detail' || !activeOntologyType) {
      this.nodes.update(baseNodes.map(node => ({
        id: node.id,
        color: node.color,
        font: node.font
      })));
      this.edges.update(baseEdges.map(edge => ({
        id: edge.id,
        color: edge.color,
        font: edge.font,
        width: edge.width
      })));
      this.lastAppliedOntologyType = activeOntologyType || null;
      return;
    }

    const matchedNodeIds = new Set(
      baseNodes.filter(node => matchesOntologyType(node.nodeType, activeOntologyType)).map(node => node.id)
    );

    this.nodes.update(baseNodes.map(node => {
      const matched = matchedNodeIds.has(node.id);
      return {
        id: node.id,
        color: matched
          ? node.color
          : {
              ...(node.color || {}),
              background: 'rgba(226, 232, 240, 0.28)',
              border: 'rgba(148, 163, 184, 0.55)'
            },
        font: {
          ...(node.font || {}),
          color: matched ? (node.font?.color || '#0f172a') : 'rgba(71, 85, 105, 0.45)'
        }
      };
    }));

    this.edges.update(baseEdges.map(edge => {
      const matched = matchedNodeIds.has(edge.from) || matchedNodeIds.has(edge.to);
      return {
        id: edge.id,
        color: matched ? (edge.color || { color: '#94a3b8' }) : { color: 'rgba(203, 213, 225, 0.28)' },
        font: {
          ...(edge.font || {}),
          color: matched ? (edge.font?.color || '#64748b') : 'rgba(100, 116, 139, 0.35)'
        }
      };
    }));

    this.lastAppliedOntologyType = activeOntologyType;
  }

  render(state) {
    const filteredCases = getFilteredCases(state.data.casesIndex, state.filters);
    const visibleCases = getVisibleCases(filteredCases, state.graph.browseMode);
    const graphData = buildDatabaseGraphData(state);
    const activeOntologyType = state.graph.selectedOntologyType || state.graph.hoverOntologyType;
    const previousMode = this.lastMode;
    const graphSignature = this.buildGraphSignature(graphData);
    const graphChanged = graphSignature !== this.lastGraphSignature;

    if (graphChanged) {
      this.lastGraphSignature = graphSignature;
      this.lastMode = graphData.mode || 'overview';
      this.currentGraphNodes = graphData.nodes.map(node => {
        const position = this.manualNodePositions.get(node.id);
        return position
          ? { ...node, x: position.x, y: position.y, fixed: { x: true, y: true } }
          : node;
      });
      this.currentGraphEdges = graphData.edges;
      this.nodes.clear();
      this.edges.clear();
      this.nodes.add(this.currentGraphNodes);
      this.edges.add(this.currentGraphEdges);
      this.updateRenderedTypeCounts();
    }

    if (graphChanged || this.lastAppliedOntologyType !== (activeOntologyType || null)) {
      this.applyOntologyHighlight(activeOntologyType || null);
    }

    const nextMode = graphData.mode || 'overview';
    if (this.network && graphChanged && nextMode !== previousMode) {
      this.network.setOptions({ physics: { enabled: true } });
      clearTimeout(this.fitTimer);
      this.fitTimer = setTimeout(() => {
        if (!this.network) return;
        this.network.fit({ animation: true });
      }, 50);
    }

    const stats = {
      cases: state.data.casesIndex.length,
      visible: visibleCases.length,
      sources: new Set(filteredCases.map(item => item.meta?.source || item.source)).size
    };
    if (this.onStatsChange) this.onStatsChange(stats);
  }
}
