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
    this.hoveredNodeId = null;
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
        solver: 'barnesHut',
        barnesHut: {
          gravitationalConstant: -12000,
          centralGravity: 0.05,
          springLength: 350,
          springConstant: 0.04,
          damping: 0.2,
          avoidOverlap: 1
        },
        stabilization: {
          enabled: true,
          iterations: 150,
          updateInterval: 25
        }
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        hideEdgesOnDrag: true,
        zoomView: true,
        dragView: true,
        navigationButtons: true,
        keyboard: false
      },
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
      if (this.shouldFitOnStabilize) {
        this.network.fit({ animation: true });
        this.shouldFitOnStabilize = false;
      }
    });
    
    // 增加对 stabilze 结束事件的兜底监听
    this.network.on('stabilized', () => {
      if (!this.network) return;
      this.network.setOptions({ physics: { enabled: false } });
      if (this.shouldFitOnStabilize) {
        this.network.fit({ animation: true });
        this.shouldFitOnStabilize = false;
      }
    });

    this.network.on('dragStart', params => {
      if (!this.network || !params.nodes.length) return;
      const updates = params.nodes.map(nodeId => ({
        id: nodeId,
        fixed: { x: false, y: false }
      }));
      this.nodes.update(updates);
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

        if (node.nodeType === 'AggregateGroup' && node.representedNodes) {
          const state = this.store.getState();
          const currentExpanded = state.graphConfig?.expandedNodes || new Set();
          const newExpanded = new Set(currentExpanded);
          if (newExpanded.has(node.id)) {
            newExpanded.delete(node.id);
          } else {
            newExpanded.add(node.id);
          }
          this.store.update('graphConfig', { expandedNodes: newExpanded });
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

    this.network.on('doubleClick', params => {
      if (params.nodes.length > 0) {
        const node = this.nodes.get(params.nodes[0]);
        if (!node) return;
        if (node.nodeType === 'AggregateGroup' && node.representedNodes) {
          const state = this.store.getState();
          const currentExpanded = state.graphConfig?.expandedNodes || new Set();
          const newExpanded = new Set(currentExpanded);
          newExpanded.add(node.id);
          this.store.update('graphConfig', { expandedNodes: newExpanded });
        }
      }
    });

    this.network.on('hoverNode', params => {
      this.hoveredNodeId = params.node;
      this.applySpotlightDimming();
    });

    this.network.on('blurNode', () => {
      this.hoveredNodeId = null;
      this.applySpotlightDimming();
    });

    this.container.addEventListener('wheel', (e) => {
      // 允许直接滚轮缩放图谱，同时阻止页面级滚动，防止图谱缩放时页面跟着乱跑
      e.preventDefault();
    }, { passive: false });
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

  applySpotlightDimming() {
    if (!this.currentGraphNodes.length) return;

    const baseNodes = this.currentGraphNodes;
    const baseEdges = this.currentGraphEdges;

    if (!this.hoveredNodeId) {
      // 恢复高亮和暗化
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
      return;
    }

    const hoveredNode = baseNodes.find(n => n.id === this.hoveredNodeId);
    if (!hoveredNode) return;

    const highlightNodeIds = new Set([this.hoveredNodeId]);
    const highlightEdgeIds = new Set();

    // 如果悬停在共有节点（T0），高亮与其相连的所有边和节点
    if (hoveredNode.isShared) {
      baseEdges.forEach(edge => {
        if (edge.from === this.hoveredNodeId || edge.to === this.hoveredNodeId) {
          highlightEdgeIds.add(edge.id);
          highlightNodeIds.add(edge.from);
          highlightNodeIds.add(edge.to);
        }
      });
    } 
    // 如果悬停在专属节点或案件节点（T1/T2），高亮整个案件的子图
    else if (hoveredNode.caseKey) {
      const targetCaseKey = hoveredNode.caseKey;
      baseNodes.forEach(n => {
        if (n.caseKey === targetCaseKey) {
          highlightNodeIds.add(n.id);
        }
      });
      baseEdges.forEach(edge => {
        const fromNode = baseNodes.find(n => n.id === edge.from);
        const toNode = baseNodes.find(n => n.id === edge.to);
        // 如果边的两端至少有一端是该案件的专属节点，或者两端都在高亮集合中
        if ((fromNode?.caseKey === targetCaseKey || toNode?.caseKey === targetCaseKey) || 
            (highlightNodeIds.has(edge.from) && highlightNodeIds.has(edge.to))) {
          highlightEdgeIds.add(edge.id);
          highlightNodeIds.add(edge.from);
          highlightNodeIds.add(edge.to);
        }
      });
    }

    this.nodes.update(baseNodes.map(node => {
      const isHighlighted = highlightNodeIds.has(node.id);
      return {
        id: node.id,
        color: isHighlighted
          ? node.color
          : {
              ...(node.color || {}),
              background: 'rgba(226, 232, 240, 0.15)',
              border: 'rgba(148, 163, 184, 0.25)'
            },
        font: {
          ...(node.font || {}),
          color: isHighlighted ? (node.font?.color || '#0f172a') : 'rgba(71, 85, 105, 0.25)'
        }
      };
    }));

    this.edges.update(baseEdges.map(edge => {
      const isHighlighted = highlightEdgeIds.has(edge.id);
      return {
        id: edge.id,
        color: isHighlighted ? (edge.color || { color: '#94a3b8' }) : { color: 'rgba(203, 213, 225, 0.15)' },
        font: {
          ...(edge.font || {}),
          color: isHighlighted ? (edge.font?.color || '#64748b') : 'rgba(100, 116, 139, 0.15)'
        }
      };
    }));
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
        // 多选模式下如果 node 设置了 fixed（如 T0, T1），直接采信预设坐标
        if (node.fixed) return node;

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
      
      // 当图谱数据发生改变（如双击折叠/展开、切换案件）时，重新激活物理引擎使其稳定
      if (this.network) {
        this.network.setOptions({ physics: { enabled: true } });
        // 强制触发 stabilize
        this.network.stabilize(150);
      }
    }

    if (graphChanged) {
      this.applySpotlightDimming();
    }

    const casesSig = (state.selection.selectedCaseKeys || []).join(',') + '|' + state.selection.activeCaseKey;
    const casesChanged = this.lastCasesSignature !== casesSig;
    this.lastCasesSignature = casesSig;

    const nextMode = graphData.mode || 'overview';
    if (this.network && graphChanged && (nextMode !== previousMode || casesChanged)) {
      clearTimeout(this.fitTimer);
      this.fitTimer = setTimeout(() => {
        if (!this.network) return;
        this.network.fit({ animation: true });
      }, 100);
      this.shouldFitOnStabilize = true;
    }

    const stats = {
      cases: state.data.casesIndex.length,
      visible: visibleCases.length,
      sources: new Set(filteredCases.map(item => item.meta?.source || item.source)).size
    };
    if (this.onStatsChange) this.onStatsChange(stats);
  }
}
