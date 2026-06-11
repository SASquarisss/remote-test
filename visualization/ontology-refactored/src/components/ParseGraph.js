import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { store } from '../store/index.js';
import { bindCustomPan } from '../utils/pan.js';

const MAIN_LANE_X = {
  caseLane: -1420,
  subjectLane: -1080,
  evidenceLane: -680,
  factLane: -180,
  elementLane: 320,
  lawLane: 820,
  resultLane: 1260,
};

const MAIN_LANE_Y = {
  caseLane: 40,
  subjectLane: 60,
  evidenceLane: 70,
  factLane: 70,
  elementLane: 70,
  lawLane: 60,
  resultLane: 70,
};

const MAIN_LANE_SPACING = {
  caseLane: 280,
  subjectLane: 110,
  evidenceLane: 150,
  factLane: 165,
  elementLane: 135,
  lawLane: 150,
  resultLane: 170,
};

const AUXILIARY_LANE_X_JITTER = {
  GuidingCase: -120,
  CaseType: 120,
  CaseSummary: -80,
  JudgmentResult: 0,
  DisputeFocus: 0,
  Judge: -90,
  Attorney: 90,
  LegalRole: 0,
  LegalSubject: 90,
  Person: 0,
};

const EDGE_PRIORITY_MAP = {
  proves_fact: 'P0',
  matches_element: 'P0',
  element_of_provision: 'P0',
  judgment_cites: 'P1',
  leads_to: 'P1',
  resolved_by: 'P1',
  has_fact: 'P2',
  has_dispute_focus: 'P2',
  submitted_for: 'P2',
  has_summary: 'P2',
};

const STRUCTURAL_RELATION_TYPES = new Set(['has_fact', 'has_dispute_focus', 'submitted_for', 'has_summary']);

const CASE_CONTEXT_RELATION_TYPES = new Set([
  '证据',
  '事实',
  '裁判',
  '争议焦点',
  '审理',
  '审判',
  '案由',
  '一级案由',
  '二级案由',
  '上诉',
  '上诉人',
  '原审被告人',
  '同案犯',
  '原公诉机关',
  '货主',
  '代理',
  '关联',
  'appeals_to',
  'tried_by',
]);

const AGGREGATE_GROUP_CONFIG = {
  DisputeFocus: { key: 'focuses', label: '焦点', lane: 'resultLane' },
  JudgmentResult: { key: 'judgments', label: '裁判', lane: 'resultLane' },
  CaseSummary: { key: 'summary', label: '摘要', lane: 'resultLane' },
};

const ANALYSIS_MODE_META = {
  overview: {
    label: '全貌模式',
    theme: 'overview',
    summary: '查看案件整体结构，默认保留全量实体并对结构边降噪。',
  },
  subgraph: {
    label: '核心子图',
    theme: 'subgraph',
    summary: '仅保留核心链路骨架，快速检查证据到裁判的主流程。',
  },
  local_focus: {
    label: '局部展开',
    theme: 'local',
    summary: '围绕当前选中节点保留一跳关键邻域，适合局部阅读。',
  },
  evidence_chain: {
    label: '证据链',
    theme: 'evidence',
    summary: '突出 证据 -> 事实 -> 法条元素/法条 -> 裁判 的证据主链。',
  },
  judgment_basis: {
    label: '裁判依据链',
    theme: 'judgment',
    summary: '突出 事实/焦点 -> 法条元素 -> 法条 -> 裁判 的依据路径。',
  },
  trace_upstream: {
    label: '上游追踪',
    theme: 'upstream',
    summary: '从当前节点反向回溯关键来源路径。',
  },
  trace_downstream: {
    label: '下游追踪',
    theme: 'downstream',
    summary: '从当前节点向后追踪关键影响路径。',
  },
  playback: {
    label: '逻辑回放',
    theme: 'playback',
    summary: '按证据到裁判的顺序依次点亮逻辑流转步骤。',
  },
  xray: {
    label: '异常断链审查',
    theme: 'xray',
    summary: '突出孤立节点、无证据事实和潜在断链位置。',
  },
};

export class ParseGraph {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.layer = document.getElementById('parseGraphLayer');
    this.network = null;
    this.nodesDs = new DataSet();
    this.edgesDs = new DataSet();
    this.overlayHost = this.layer || this.container;
    this.viewMode = 'all';
    this.lastRenderedData = null;
    this.needsLayout = false;
    this.isMainView = false;
    this.layoutMode = store.getState().parseGraphLayoutMode || 'lane';
    this.semanticZoom = store.getState().parseGraphSemanticZoom || 'mid';
    this.localFocusMode = false;
    this.pathPreset = 'none';
    this.traceDirection = 'none';
    this.toolDescText = '请选择上方的分析模式。这些工具可以帮助你过滤冗余信息、检查逻辑断裂或一键排版案件结构。';
    this.traceSummaryText = '';
    this.currentAnalysisMode = 'overview';
    this.init();
    this.bindResizeObserver();
    this.bindVisibilityEvents();
  }

  mountToMainView() {
    if (!this.network || !this.layer) return;
    this.isMainView = true;
    this.layer.style.display = 'block';
    this.container.style.display = 'block';
    this.overlayHost = this.layer;
    this.scheduleRelayout({ fit: true, delay: 30 });
  }

  mountToTerminal() {
    if (!this.network || !this.layer) return;
    this.isMainView = false;
    this.layer.style.display = 'none';
    this.container.style.display = 'none';
    this.overlayHost = this.layer;
  }

  scheduleRelayout({ fit = false, delay = 60, preserveView = false } = {}) {
    if (!this.network) return;
    window.clearTimeout(this.relayoutTimer);
    this.relayoutTimer = window.setTimeout(() => {
      if (!this.network || !this.container || this.container.style.display === 'none') return;
      this.network.setSize('100%', '100%');
      this.network.redraw();
      this.renderZoneOverlay();
      if (fit) {
        this.network.fit({ animation: true });
      } else if (!preserveView) {
        this.network.moveTo({ scale: this.network.getScale() });
      }
    }, delay);
  }

  bindResizeObserver() {
    if (typeof ResizeObserver === 'undefined') return;
    this.resizeObserver?.disconnect?.();
    this.resizeObserver = new ResizeObserver(() => {
      if (!this.network || !this.lastRenderedData) return;
      if (!this.container || this.container.style.display === 'none') return;
      this.scheduleRelayout({ fit: false, delay: 30, preserveView: true });
    });
    if (this.container) {
      this.resizeObserver.observe(this.container);
    }
    if (this.layer) {
      this.resizeObserver.observe(this.layer);
    }
  }

  bindVisibilityEvents() {
    window.addEventListener('parse-graph-visible', (event) => {
      this.initGraphTools();
      this.renderAnalysisModeState(store.getState());
      if (!this.network || !this.lastRenderedData) return;
      const fit = Boolean(event?.detail?.fit);
      this.scheduleRelayout({ fit, delay: fit ? 40 : 20, preserveView: !fit });
    });
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState !== 'visible' || !this.lastRenderedData) return;
      this.scheduleRelayout({ fit: false, delay: 40, preserveView: true });
    });
  }

  init() {
    if (!this.container) return;
    
    const options = {
      physics: { enabled: false },
      interaction: { hover: true, tooltipDelay: 100, navigationButtons: true, keyboard: true, zoomView: false, dragView: false, dragNodes: true },
      edges: { smooth: { type: 'curvedCW', roundness: 0.1 }, font: { size: 9, color: '#64748b', align: 'horizontal', strokeWidth: 2, strokeColor: '#ffffff' }, selectionWidth: 2.2 },
      nodes: { font: { face: 'Microsoft YaHei, PingFang SC, sans-serif', multi: 'md' }, borderWidth: 2, shadow: { enabled: true, size: 3 } },
      layout: { improvedLayout: false, randomSeed: 42 },
    };
    
    this.network = new Network(this.container, { nodes: this.nodesDs, edges: this.edgesDs }, options);
    
    // Binding the click event specifically to ParseGraph scope
    this.network.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        // Skip cluster nodes for panel opening
        if (typeof nodeId === 'string' && nodeId.startsWith('cluster_')) return;
        const nodeData = this.nodesDs.get(nodeId);
        if (nodeData?.nodeType === 'AggregateGroup') {
          this.toggleAggregateGroup(nodeData.aggregateKey);
          return;
        }
        
        store.setState({
          selectedNodeId: nodeId,
          selectedEdgeId: null,
          selectedGraph: 'parse',
          isPanelOpen: true,
          parseNodeData: this.nodesDs.get(nodeId)
        });

        if (this.localFocusMode || this.traceDirection !== 'none') {
          this.updateView();
        }

        this.highlightNeighbors(nodeId);
      } else if (params.edges.length > 0) {
        const edgeId = params.edges[0];
        store.setState({
          selectedNodeId: null,
          selectedEdgeId: edgeId,
          selectedGraph: 'parse',
          isPanelOpen: true,
          parseEdgeData: this.edgesDs.get(edgeId)
        });
        this.clearNeighborHighlight();
      } else {
        store.setState({ isPanelOpen: false });
        this.network.unselectAll();
        this.clearNeighborHighlight();
      }
    });

    this.network.on('doubleClick', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        if (typeof nodeId === 'string' && nodeId.startsWith('cluster_')) {
          try {
            this.network.openCluster(nodeId);
            setTimeout(() => this.network.fit({ animation: true }), 50);
          } catch(e) {}
        }
      }
    });

    this.network.on('zoom', () => {
      if (this.zoomTimeout) clearTimeout(this.zoomTimeout);
      this.zoomTimeout = setTimeout(() => {
        this.renderZoneOverlay();
        this.updateSemanticZoom();
      }, 16);
    });

    // Native zoom and pan will work now that we reparent this.container instead of just the canvas.frame.
    // Ensure we trigger overlay render on drag.
    this.network.on('dragging', () => { this.renderZoneOverlay(); });

    // Use custom pan to fix dragging on empty space reliably
    bindCustomPan(this.network, this.network.canvas.frame, () => this.renderZoneOverlay());

    // Clamp scale to prevent graph disappearance
    this.network.canvas.frame.addEventListener('wheel', (e) => {
      if (this.network) {
        e.preventDefault();
        const scale = this.network.getScale();
        let newScale = e.deltaY > 0 ? scale * 0.9 : scale * 1.1;
        newScale = Math.max(0.15, Math.min(newScale, 3.5)); // Clamp scale
        
        // Prevent scaling if it doesn't change
        if (newScale !== scale) {
          this.network.moveTo({ scale: newScale });
        }
      }
    }, { passive: false });

    this.network.on('dragStart', (params) => {
      if (params.nodes.length === 0) {
        this.container.classList.add('panning');
      }
    });
    this.network.on('dragEnd', () => {
      this.container.classList.remove('panning');
      setTimeout(() => { this.renderZoneOverlay(); }, 0);
    });

    this.bindControls();

    store.subscribe(state => this.render(state));

    let lastLocateTarget = null;
    // Subscribe to store to locate nodes triggered from outside (e.g. Issues/Eval)
    store.subscribe((state) => {
      if (state.locateTarget && state.locateTarget !== lastLocateTarget && state.locateTarget.sourceGraph === 'parse') {
        lastLocateTarget = state.locateTarget;
        const typeKey = state.locateTarget.nodeType || state.locateTarget.typeKey;
        if (typeKey && this.network) {
          // Look for any node that matches this type
          const nodes = this.nodesDs.get({
            filter: function (item) {
              return item.group === typeKey || item.nodeType === typeKey || item.label === typeKey;
            }
          });
          
          if (nodes.length > 0) {
            const targetId = nodes[0].id;
            this.network.selectNodes([targetId]);
            this.network.focus(targetId, { scale: 1.2, animation: true });
            
            // Also notify DetailPanel
            store.setState({ 
              selectedNodeId: targetId, 
              selectedGraph: 'parse',
              parseNodeData: nodes[0],
              isPanelOpen: true 
            });
          }
        }
      }
      
      // Handle cross-graph linkage from Ontology Graph (click)
      if (state.selectedGraph === 'ontology' && state.selectedNodeId) {
        this.focusNodesByType(state.selectedNodeId);
      } else if (!state.selectedNodeId && state.selectedGraph !== 'parse') {
        this.clearTypeFocus();
      }
      
      // Handle hover from Ontology Graph
      if (state.hoverOntologyType) {
        this.previewNodesByType(state.hoverOntologyType);
      } else if (!state.hoverOntologyType && state.selectedGraph !== 'ontology') {
        this.clearTypeFocus();
      }

      if (state.locateTarget && state.locateTarget.timestamp !== this.lastLocateTimestamp) {
        this.lastLocateTimestamp = state.locateTarget.timestamp;
        if (state.locateTarget.sourceGraph === 'parse') {
          this.locateAndFlashNode(state.locateTarget.typeKey);
        }
      }
    });

    this.initGraphTools();
  }

  getRelationType(edge) {
    return edge?.relationType || edge?.relation_type || edge?.label || '';
  }

  getEdgePriority(edge) {
    const relationType = this.getRelationType(edge);
    return EDGE_PRIORITY_MAP[relationType] || 'P1';
  }

  isStructuralEdge(edge) {
    return STRUCTURAL_RELATION_TYPES.has(this.getRelationType(edge));
  }

  isCaseContextEdge(edge, rawNodeMap = null) {
    const relationType = this.getRelationType(edge);
    if (CASE_CONTEXT_RELATION_TYPES.has(relationType)) return true;
    if (!rawNodeMap) return false;
    const fromType = this.getNodeType(rawNodeMap.get(edge.from));
    const toType = this.getNodeType(rawNodeMap.get(edge.to));
    return relationType !== 'proves_fact'
      && relationType !== 'matches_element'
      && relationType !== 'element_of_provision'
      && relationType !== 'judgment_cites'
      && relationType !== 'leads_to'
      && relationType !== 'resolved_by'
      && (fromType === 'CourtCase' || toType === 'CourtCase')
      && (fromType === 'LegalSubject' || toType === 'LegalSubject' || fromType === 'Judge' || toType === 'Judge' || fromType === 'Attorney' || toType === 'Attorney' || fromType === 'CaseType' || toType === 'CaseType');
  }

  isAggregateNode(node) {
    return this.getNodeType(node) === 'AggregateGroup';
  }

  toggleAggregateGroup(aggregateKey) {
    const state = store.getState();
    const expandedGroups = { ...(state.parseGraphExpandedGroups || {}) };
    expandedGroups[aggregateKey] = !expandedGroups[aggregateKey];
    store.setState({
      parseGraphExpandedGroups: expandedGroups,
      selectedNodeId: null,
      selectedEdgeId: null,
      isPanelOpen: false,
    });
    this.lastRenderedData = null;
    this.render(store.getState());
  }

  initGraphTools() {
    // We will place the tools in the terminal's "图" tab instead of the main container
    const termGraphInfo = document.getElementById('termGraphInfo');
    if (termGraphInfo && !termGraphInfo.querySelector('.graph-tools-bar')) {
      termGraphInfo.innerHTML = ''; // clear any placeholder text
      const toolbar = document.createElement('div');
      toolbar.className = 'graph-tools-bar';
      toolbar.innerHTML = `
        <div class="graph-tools-header">📊 高级图谱分析与操作台</div>
        <div class="graph-tools-grid">
          <button id="btnSubgraph" class="tool-btn"><span class="icon">🎯</span> 核心子图透视</button>
          <button id="btnSmartLayout" class="tool-btn"><span class="icon">✨</span> 车道布局</button>
          <button id="btnLocalFocus" class="tool-btn"><span class="icon">🧭</span> 局部展开</button>
          <button id="btnEvidenceChain" class="tool-btn"><span class="icon">🧾</span> 证据链</button>
          <button id="btnJudgmentBasis" class="tool-btn"><span class="icon">⚖</span> 裁判依据链</button>
          <button id="btnTraceUpstream" class="tool-btn"><span class="icon">⬅</span> 上游追踪</button>
          <button id="btnTraceDownstream" class="tool-btn"><span class="icon">➡</span> 下游追踪</button>
          <button id="btnPlayback" class="tool-btn"><span class="icon">▶</span> 逻辑动态回放</button>
          <button id="btnXRay" class="tool-btn"><span class="icon">🩻</span> 异常断链审查</button>
          <button id="btnRestoreGraph" class="tool-btn" style="grid-column: span 2; justify-content: center; background: #f8fafc; color: #64748b; border-color: #cbd5e1;"><span class="icon">↺</span> 恢复初始状态</button>
        </div>
        <div class="graph-tools-desc" id="graphToolDesc"></div>
      `;
      termGraphInfo.appendChild(toolbar);
      
      this.toolDescEl = toolbar.querySelector('#graphToolDesc');
      this.ensureAnalysisModeElements();
      this.renderLayoutModeButton();
      this.renderToolDescription();
      this.syncToolButtonStates();

      toolbar.querySelector('#btnSubgraph').addEventListener('click', () => {
        this.toggleSubgraphMode();
        this.setToolDescription(this.subgraphMode ? '已开启核心子图透视：隐藏边缘节点，仅显示 证据 -> 事实 -> 焦点 -> 法条 的骨架链路。' : '已恢复全量图谱显示。');
      });
      toolbar.querySelector('#btnSmartLayout').addEventListener('click', () => {
        const next = this.toggleLayoutMode();
        this.setToolDescription(next === 'focus_orbit' ? '已切到焦点环布局：围绕争点核心组织法条半环与裁判半环。' : '已切回车道布局：恢复按区带展开的主图结构。');
      });
      toolbar.querySelector('#btnLocalFocus').addEventListener('click', () => {
        const changed = this.toggleLocalFocusMode();
        if (changed === false) {
          this.setToolDescription('请先点击一个节点，再使用局部展开。');
          return;
        }
        this.setToolDescription(this.localFocusMode ? '已开启局部展开：围绕当前节点仅保留一跳关键邻域。' : '已关闭局部展开，恢复主图全貌。');
      });
      toolbar.querySelector('#btnEvidenceChain').addEventListener('click', () => {
        const preset = this.togglePathPreset('evidence_chain');
        this.setToolDescription(preset === 'evidence_chain' ? '已切到证据链：突出 证据 -> 事实 -> 法条元素/法条 -> 裁判 相关主链。' : '已关闭证据链聚焦，恢复默认主图。');
      });
      toolbar.querySelector('#btnJudgmentBasis').addEventListener('click', () => {
        const preset = this.togglePathPreset('judgment_basis');
        this.setToolDescription(preset === 'judgment_basis' ? '已切到裁判依据链：突出 事实/焦点 -> 法条元素 -> 法条 -> 裁判 的裁判依据路径。' : '已关闭裁判依据链聚焦，恢复默认主图。');
      });
      toolbar.querySelector('#btnTraceUpstream').addEventListener('click', () => {
        const changed = this.toggleTraceDirection('upstream');
        if (changed === false) {
          this.setToolDescription('请先点击一个节点，再使用上游追踪。');
          return;
        }
        this.setToolDescription(this.traceDirection === 'upstream' ? '已开启上游追踪：从当前节点反向回溯关键来源路径。' : '已关闭上游追踪。');
      });
      toolbar.querySelector('#btnTraceDownstream').addEventListener('click', () => {
        const changed = this.toggleTraceDirection('downstream');
        if (changed === false) {
          this.setToolDescription('请先点击一个节点，再使用下游追踪。');
          return;
        }
        this.setToolDescription(this.traceDirection === 'downstream' ? '已开启下游追踪：从当前节点向后追踪关键影响路径。' : '已关闭下游追踪。');
      });
      toolbar.querySelector('#btnPlayback').addEventListener('click', () => {
        this.togglePlayback();
        this.setToolDescription(this.playbackInterval ? '正在播放逻辑推导动画：按照 证据->事实->焦点->法条 顺序点亮。' : '逻辑回放已停止。');
      });
      toolbar.querySelector('#btnXRay').addEventListener('click', () => {
        this.toggleXRayMode();
        this.setToolDescription(this.xrayMode ? '已开启 X 光审查：红色虚线高亮显示孤立节点、无证据事实和断链的争议焦点。' : '已关闭 X 光审查模式。');
      });
      toolbar.querySelector('#btnRestoreGraph').addEventListener('click', () => {
        this.subgraphMode = false;
        this.xrayMode = false;
        this.localFocusMode = false;
        this.pathPreset = 'none';
        this.traceDirection = 'none';
        this.traceSummaryText = '';
        store.setState({ parseGraphLayoutMode: 'lane' });
        if (this.playbackInterval) {
          clearInterval(this.playbackInterval);
          this.playbackInterval = null;
        }
        toolbar.querySelectorAll('.tool-btn').forEach(b => {
          b.classList.remove('active');
          b.style.background = ''; b.style.color = '';
        });
        
        this.lastRenderedData = null;
        this.render(store.getState());
        this.syncToolButtonStates();
        
        setTimeout(() => {
          this.network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
        }, 100);
        this.setToolDescription('已恢复图谱的初始完整状态和默认排版。');
      });
    }
  }

  renderToolDescription() {
    if (!this.toolDescEl) return;
    const parts = [this.toolDescText, this.traceSummaryText].filter(Boolean);
    this.toolDescEl.textContent = parts.join(' | ');
  }

  ensureAnalysisModeElements() {
    if (!this.toolModeEl || !this.toolModeEl.isConnected) {
      this.toolModeEl = document.getElementById('termGraphModeBar');
    }
    if (!this.toolModeBadgeEl || !this.toolModeBadgeEl.isConnected) {
      this.toolModeBadgeEl = document.getElementById('termGraphModeBadge');
    }
    if (!this.toolModeSummaryEl || !this.toolModeSummaryEl.isConnected) {
      this.toolModeSummaryEl = document.getElementById('termGraphModeSummary');
    }
    if (this.toolModeEl && (!this.changeLegendEl || !this.changeLegendEl.isConnected)) {
      let legend = document.getElementById('termGraphChangeLegend');
      if (!legend) {
        legend = document.createElement('div');
        legend.className = 'term-graph-change-legend';
        legend.id = 'termGraphChangeLegend';
        legend.innerHTML = `
          <span class="term-graph-change-title" id="termGraphChangeTitle">版本变化</span>
          <span class="term-graph-change-chip is-added"><span class="term-graph-change-dot">+</span>新增</span>
          <span class="term-graph-change-chip is-updated"><span class="term-graph-change-dot">●</span>更新</span>
          <span class="term-graph-change-chip is-explicit"><span class="term-graph-change-line"></span>显式</span>
          <span class="term-graph-change-chip is-derived"><span class="term-graph-change-line dashed"></span>派生</span>
        `;
        this.toolModeEl.appendChild(legend);
      }
      this.changeLegendEl = legend;
    }
    if (!this.changeLegendTitleEl || !this.changeLegendTitleEl.isConnected) {
      this.changeLegendTitleEl = document.getElementById('termGraphChangeTitle');
    }
  }

  getActiveAnalysisMode() {
    if (this.xrayMode) return 'xray';
    if (this.playbackInterval) return 'playback';
    if (this.traceDirection === 'upstream') return 'trace_upstream';
    if (this.traceDirection === 'downstream') return 'trace_downstream';
    if (this.pathPreset === 'evidence_chain') return 'evidence_chain';
    if (this.pathPreset === 'judgment_basis') return 'judgment_basis';
    if (this.localFocusMode) return 'local_focus';
    if (this.subgraphMode) return 'subgraph';
    return 'overview';
  }

  getHighlightVisualMeta(state = store.getState()) {
    const highlight = this.getActiveMergeHighlight(state);
    const previewActive = Boolean(state.parseEnhancementPreviewActive && state.parseEnhancementPreviewPatch);
    const hasHighlight = Boolean(
      highlight && (
        (highlight.addedNodeIds?.length || 0)
        + (highlight.updatedNodeIds?.length || 0)
        + (highlight.addedEdgeIds?.length || 0)
        + (highlight.updatedEdgeIds?.length || 0)
        + (highlight.addedDerivedEdgeIds?.length || 0)
        + (highlight.updatedDerivedEdgeIds?.length || 0)
      ) > 0
    );
    return { highlight, previewActive, hasHighlight };
  }

  renderChangeLegend(state = store.getState()) {
    this.ensureAnalysisModeElements();
    if (!this.changeLegendEl) return;
    const visualMeta = this.getHighlightVisualMeta(state);
    this.changeLegendEl.style.display = visualMeta.hasHighlight ? 'flex' : 'none';
    if (this.changeLegendTitleEl) {
      this.changeLegendTitleEl.textContent = visualMeta.previewActive ? '应用预览' : '版本变化';
    }
    if (this.toolModeEl) {
      this.toolModeEl.dataset.changeMode = visualMeta.previewActive ? 'preview' : (visualMeta.hasHighlight ? 'merged' : 'none');
    }
  }

  renderAnalysisModeState(state = store.getState()) {
    this.ensureAnalysisModeElements();
    this.currentAnalysisMode = this.getActiveAnalysisMode();
    const meta = ANALYSIS_MODE_META[this.currentAnalysisMode] || ANALYSIS_MODE_META.overview;
    const visualMeta = this.getHighlightVisualMeta(state);
    if (this.toolModeEl) {
      this.toolModeEl.dataset.mode = meta.theme;
    }
    if (this.toolModeBadgeEl) {
      this.toolModeBadgeEl.textContent = meta.label;
    }
    if (this.toolModeSummaryEl) {
      this.toolModeSummaryEl.textContent = visualMeta.hasHighlight
        ? `${meta.summary} ${visualMeta.previewActive ? '当前为应用预览。' : '当前显示版本变化。'}青蓝表示新增，橙色表示更新，实线表示显式关系，虚线表示派生关系，节点标签前的 + / ● 对应新增与更新。`
        : meta.summary;
    }
    this.renderChangeLegend(state);
  }

  setToolDescription(text) {
    this.toolDescText = text || '';
    this.renderToolDescription();
  }

  setTraceSummary(text) {
    this.traceSummaryText = text || '';
    this.renderToolDescription();
  }

  setToolButtonState(buttonId, active, background = '#2563eb') {
    const button = document.getElementById(buttonId);
    if (!button) return;
    button.classList.toggle('active', active);
    button.style.background = active ? background : '';
    button.style.color = active ? 'white' : '';
  }

  syncToolButtonStates() {
    this.renderLayoutModeButton();
    this.setToolButtonState('btnSmartLayout', this.getLayoutMode() === 'focus_orbit', '#7c3aed');
    this.setToolButtonState('btnLocalFocus', this.localFocusMode, '#0ea5e9');
    this.setToolButtonState('btnEvidenceChain', this.pathPreset === 'evidence_chain', '#7c3aed');
    this.setToolButtonState('btnJudgmentBasis', this.pathPreset === 'judgment_basis', '#dc2626');
    this.setToolButtonState('btnTraceUpstream', this.traceDirection === 'upstream', '#0f766e');
    this.setToolButtonState('btnTraceDownstream', this.traceDirection === 'downstream', '#ea580c');
    this.setToolButtonState('btnSubgraph', this.subgraphMode, '#2563eb');
    this.setToolButtonState('btnPlayback', Boolean(this.playbackInterval), '#f59e0b');
    this.setToolButtonState('btnXRay', this.xrayMode, '#dc2626');
    this.renderAnalysisModeState(store.getState());
  }

  toggleLocalFocusMode() {
    if (!this.localFocusMode && !store.getState().selectedNodeId) {
      return false;
    }
    this.localFocusMode = !this.localFocusMode;
    if (this.localFocusMode) {
      this.pathPreset = 'none';
    }
    this.syncToolButtonStates();
    this.updateView();
    setTimeout(() => this.network?.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } }), 60);
    return true;
  }

  togglePathPreset(preset) {
    this.pathPreset = this.pathPreset === preset ? 'none' : preset;
    if (this.pathPreset !== 'none') {
      this.localFocusMode = false;
    }
    this.syncToolButtonStates();
    this.updateView();
    setTimeout(() => this.network?.fit({ animation: { duration: 450, easingFunction: 'easeInOutQuad' } }), 60);
    return this.pathPreset;
  }

  toggleTraceDirection(direction) {
    if (!store.getState().selectedNodeId) {
      return false;
    }
    this.traceDirection = this.traceDirection === direction ? 'none' : direction;
    if (this.traceDirection !== 'none') {
      this.localFocusMode = false;
    }
    this.syncToolButtonStates();
    this.updateView();
    setTimeout(() => this.network?.fit({ animation: { duration: 420, easingFunction: 'easeInOutQuad' } }), 60);
    return true;
  }

  toggleSubgraphMode() {
    this.subgraphMode = !this.subgraphMode;
    if (this.subgraphMode) {
      const coreTypes = ['Evidence', 'Fact', 'DisputeFocus', 'LegalProvision', 'JudgmentResult', 'CaseSummary'];
      const nodes = this.nodesDs.get();
      const updates = nodes.map(n => {
        const type = n.nodeType || n.group;
        return { id: n.id, hidden: !coreTypes.includes(type) };
      });
      this.nodesDs.update(updates);
      this.network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
    } else {
      const nodes = this.nodesDs.get();
      this.nodesDs.update(nodes.map(n => ({ id: n.id, hidden: false })));
      this.network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
    }
    this.syncToolButtonStates();
  }

  getLayoutMode(state = store.getState()) {
    return state.parseGraphLayoutMode || this.layoutMode || 'lane';
  }

  renderLayoutModeButton() {
    const btn = document.getElementById('btnSmartLayout');
    if (!btn) return;
    const mode = this.getLayoutMode();
    btn.innerHTML = mode === 'focus_orbit'
      ? '<span class="icon">✨</span> 切换为车道布局'
      : '<span class="icon">🌀</span> 切换为焦点环布局';
  }

  toggleLayoutMode() {
    const next = this.getLayoutMode() === 'focus_orbit' ? 'lane' : 'focus_orbit';
    store.setState({ parseGraphLayoutMode: next });
    if (this.lastRenderedData && this.network) {
      this.layoutMode = next;
      this.syncToolButtonStates();
      this.syncRenderedGraph();
      this.apply2DLayout();
    } else {
      this.layoutMode = next;
      this.syncToolButtonStates();
    }
    return next;
  }

  applySmartLayout() {
    this.toggleLayoutMode();
  }

  togglePlayback() {
    if (this.playbackInterval) {
      clearInterval(this.playbackInterval);
      this.playbackInterval = null;
      const btn = document.getElementById('btnPlayback');
      if (btn) {
        btn.textContent = '▶ 逻辑回放';
      }
      this.clearTypeFocus();
      this.syncToolButtonStates();
      return;
    }

    const nodes = this.nodesDs.get();
    const edges = this.edgesDs.get();
    
    // Dim all
    this.nodesDs.update(nodes.map(n => ({ id: n.id, color: { background: '#f1f5f9', border: '#e2e8f0' }, font: { color: '#cbd5e1' } })));
    this.edgesDs.update(edges.map(e => ({ id: e.id, color: { color: 'rgba(226,232,240,0.2)' } })));
    
    const steps = ['Evidence', 'Fact', 'DisputeFocus', 'LegalProvision', 'JudgmentResult'];
    let currentStep = 0;
    
    const btn = document.getElementById('btnPlayback');
    if (btn) {
      btn.textContent = '⏹ 停止回放';
    }
    this.syncToolButtonStates();
    
    this.playbackInterval = setInterval(() => {
      if (currentStep >= steps.length) {
        clearInterval(this.playbackInterval);
        this.playbackInterval = null;
        if (btn) {
          btn.textContent = '▶ 逻辑回放';
        }
        this.syncToolButtonStates();
        setTimeout(() => this.clearTypeFocus(), 2000);
        return;
      }
      
      const type = steps[currentStep];
      const activeNodes = nodes.filter(n => (n.nodeType || n.group) === type).map(n => n.id);
      
      if (activeNodes.length > 0) {
        const originalStyles = this.styleNodes(nodes.filter(n => activeNodes.includes(n.id)));
        this.nodesDs.update(originalStyles.map(n => ({...n, shadow: { enabled: true, color: '#f59e0b', size: 20 }})));
        
        const activeEdges = edges.filter(e => activeNodes.includes(e.from) || activeNodes.includes(e.to));
        this.edgesDs.update(activeEdges.map(e => ({ id: e.id, color: { color: '#f59e0b' }, width: 2 })));
        
        this.network.fit({ nodes: activeNodes, animation: { duration: 500 } });
      }
      
      currentStep++;
    }, 1500);
  }

  toggleXRayMode() {
    this.xrayMode = !this.xrayMode;
    if (this.xrayMode) {
      const nodes = this.nodesDs.get();
      const edges = this.edgesDs.get();
      
      const edgeFroms = new Set(edges.map(e => e.from));
      const edgeTos = new Set(edges.map(e => e.to));
      
      const updates = [];
      nodes.forEach(n => {
        const type = n.nodeType || n.group;
        let isAnomaly = false;
        let anomalyReason = '';
        
        if (!edgeFroms.has(n.id) && !edgeTos.has(n.id)) {
          isAnomaly = true; anomalyReason = '孤立节点';
        } else if (type === 'Fact' && !edgeTos.has(n.id)) {
          isAnomaly = true; anomalyReason = '无证据支撑';
        } else if (type === 'DisputeFocus') {
          const hasResolution = edges.some(e => e.from === n.id && nodes.find(target => target.id === e.to && (target.nodeType||target.group) === 'LegalProvision'));
          if (!hasResolution) {
            isAnomaly = true; anomalyReason = '未引用法条';
          }
        }
        
        if (isAnomaly) {
          updates.push({
            id: n.id,
            shapeProperties: { borderDashes: [5, 5] },
            borderWidth: 4,
            color: { border: '#e74c3c', background: '#fadbd8' },
            shadow: { enabled: true, color: '#e74c3c', size: 15 },
            label: `⚠ ${n.label || n.title || n.id}\n(${anomalyReason})`
          });
        } else {
          updates.push({
            id: n.id,
            color: { background: '#f1f5f9', border: '#e2e8f0' },
            font: { color: '#cbd5e1' }
          });
        }
      });
      this.nodesDs.update(updates);
    } else {
      this.clearTypeFocus();
    }
    this.syncToolButtonStates();
  }

  locateAndFlashNode(targetKey) {
    if (!this.network) return;
    const nodes = this.nodesDs.get();
    
    // Attempt to find by ID or nodeType/group or label
    const targetNodes = nodes.filter(n => n.id === targetKey || n.nodeType === targetKey || n.group === targetKey || n.label === targetKey);
    
    if (targetNodes.length > 0) {
      const targetIds = targetNodes.map(n => n.id);
      this.network.selectNodes(targetIds, false);
      this.network.fit({
        nodes: targetIds,
        animation: { duration: 500, easingFunction: 'easeInOutQuad' },
        scale: 1.2
      });

      // Flash effect
      let flashCount = 0;
      const flashInterval = setInterval(() => {
        const isHighlight = flashCount % 2 === 0;
        const updated = targetNodes.map(n => ({
          id: n.id,
          color: isHighlight ? { background: '#ffeb3b', border: '#e74c3c' } : undefined,
          borderWidth: isHighlight ? 4 : 1
        }));
        this.nodesDs.update(updated);
        
        flashCount++;
        if (flashCount >= 6) { // 3 flashes
          clearInterval(flashInterval);
          // Restore original style via styleNodes
          this.nodesDs.update(this.styleNodes(targetNodes));
        }
      }, 300);
      
      // Also scroll JSON tree to view
      const jsonTree = document.getElementById('termJsonTree');
      if (jsonTree) {
        // A naive search for the text in JSON
        const walker = document.createTreeWalker(jsonTree, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while ((node = walker.nextNode())) {
          if (node.nodeValue.includes(targetKey)) {
            const parent = node.parentElement;
            if (parent) {
              parent.style.backgroundColor = '#ffeb3b';
              parent.scrollIntoView({ behavior: 'smooth', block: 'center' });
              setTimeout(() => parent.style.backgroundColor = '', 2000);
            }
            break;
          }
        }
      }
    }
  }

  highlightNeighbors(nodeId) {
    if (!this.network) return;
    const connectedNodes = this.network.getConnectedNodes(nodeId);
    const connectedEdges = this.network.getConnectedEdges(nodeId);
    const nodes = this.nodesDs.get();
    const edges = this.edgesDs.get();
    
    // Nodes to highlight: clicked node + 1st degree neighbors
    const highlightNodeIds = [nodeId, ...connectedNodes];
    
    const updatedNodes = nodes.map(n => {
      const isMatch = highlightNodeIds.includes(n.id);
      const isFocus = n.id === nodeId;
      return {
        id: n.id,
        color: isMatch
          ? (isFocus ? { background: '#fef3c7', border: '#d97706' } : undefined)
          : { background: 'rgba(241, 245, 249, 0.22)', border: 'rgba(226, 232, 240, 0.22)' },
        borderWidth: isFocus ? 3.5 : undefined,
        shadow: isFocus
          ? { enabled: true, color: 'rgba(217,119,6,0.32)', size: 20 }
          : (isMatch ? { enabled: true, color: 'rgba(37,99,235,0.18)', size: 10 } : { enabled: false }),
        font: isMatch
          ? (isFocus ? { color: '#7c2d12', strokeWidth: 4, strokeColor: '#ffffff' } : undefined)
          : { color: 'rgba(203, 213, 225, 0.26)' }
      };
    });
    
    const updatedEdges = edges.map(e => {
      const isMatch = connectedEdges.includes(e.id);
      const isP0 = e.edgePriority === 'P0';
      const isP1 = e.edgePriority === 'P1';
      const isContext = e.isCaseContextEdge;
      return {
        id: e.id,
        color: isMatch
          ? (isP0
              ? { color: '#2563eb', highlight: '#1d4ed8' }
              : isP1
                ? { color: '#4f46e5', highlight: '#4338ca' }
                : isContext
                  ? { color: 'rgba(148,163,184,0.38)', highlight: '#94a3b8' }
                  : { color: '#64748b', highlight: '#475569' })
          : { color: 'rgba(226, 232, 240, 0.16)' },
        width: isMatch ? (isP0 ? 3.6 : isP1 ? 2.6 : isContext ? 1.1 : 1.8) : 0.8,
        dashes: isMatch ? Boolean(isContext || e.edgePriority === 'P2') : true,
        font: isMatch
          ? {
              size: isP0 ? 12 : 10,
              color: isP0 ? '#1d4ed8' : isP1 ? '#4338ca' : '#64748b',
              align: 'horizontal',
              strokeWidth: 3,
              strokeColor: '#ffffff'
            }
          : { size: 9, color: 'rgba(203, 213, 225, 0.22)', align: 'horizontal', strokeWidth: 2, strokeColor: '#ffffff' }
      };
    });
    
    this.nodesDs.update(updatedNodes);
    this.edgesDs.update(updatedEdges);
  }

  clearNeighborHighlight() {
    if (!this.network) return;
    const state = store.getState();
    if (state.parseGraphData && !state.selectedNodeId) {
      this.syncRenderedGraph({ preservePositions: true });
    }
  }

  bindControls() {
    this.btnRelatedOnly = document.getElementById('btnRelatedOnly');
    this.btnResetLayout = document.getElementById('btnResetLayout');
    this.btnGraphRegen = document.getElementById('btnGraphRegen');
    
    if (this.btnResetLayout) {
      this.btnResetLayout.addEventListener('click', () => {
        this.apply2DLayout();
      });
    }
    
    if (this.btnGraphRegen) {
      this.btnGraphRegen.addEventListener('click', () => {
        const state = store.getState();
        if (state.parseGraphData) {
          // Re-render
          this.lastRenderedData = null;
          this.render(state);
        }
      });
    }

    if (this.btnRelatedOnly) {
      this.btnRelatedOnly.addEventListener('click', () => {
        if (this.viewMode === 'related') {
          this.viewMode = 'all';
          this.btnRelatedOnly.textContent = '🎯 只看当前相关';
          this.btnRelatedOnly.classList.remove('active-filter');
        } else {
          const state = store.getState();
          if (!state.selectedNodeId) return;
          this.viewMode = 'related';
          this.btnRelatedOnly.textContent = '↺ 返回全图';
          this.btnRelatedOnly.classList.add('active-filter');
        }
        this.updateView();
      });
    }
  }

  updateView() {
    if (!this.lastRenderedData) return;
    this.syncRenderedGraph({ reposition: true });
  }

  getRenderedGraph(state = store.getState()) {
    if (!this.lastRenderedData) {
      return { nodes: [], edges: [] };
    }

    const { nodes = [], edges = [] } = this.lastRenderedData;
    const displayGraph = this.buildDisplayGraph(nodes, edges, state);
    let filteredNodes = displayGraph.nodes;
    let filteredEdges = displayGraph.edges;

    if (this.viewMode === 'related' && state.selectedNodeId) {
      const focusNodeId = state.selectedNodeId;
      const focusNodeIds = new Set([focusNodeId]);

      filteredEdges.forEach((edge) => {
        if (edge.from === focusNodeId || edge.to === focusNodeId) {
          focusNodeIds.add(edge.from);
          focusNodeIds.add(edge.to);
        }
      });

      filteredNodes = filteredNodes.filter((node) => focusNodeIds.has(node.id));
      filteredEdges = filteredEdges.filter((edge) => focusNodeIds.has(edge.from) && focusNodeIds.has(edge.to));
    }

    ({ nodes: filteredNodes, edges: filteredEdges } = this.applyFocusFilters(filteredNodes, filteredEdges, state));

    return {
      nodes: filteredNodes,
      edges: filteredEdges,
    };
  }

  syncRenderedGraph({ reposition = false, preservePositions = false } = {}) {
    const state = store.getState();
    const renderedGraph = this.getRenderedGraph(state);
    this.refreshTraceSummary(state, renderedGraph.nodes);
    const styledNodes = this.styleNodes(renderedGraph.nodes, state);
    const styledEdges = this.styleEdges(renderedGraph.edges, state);

    let nodesToRender = styledNodes;
    if (preservePositions) {
      const currentNodeMap = new Map(this.nodesDs.get().map((node) => [node.id, node]));
      nodesToRender = styledNodes.map((node) => {
        const current = currentNodeMap.get(node.id);
        if (!current) return node;
        return {
          ...node,
          x: current.x ?? node.x,
          y: current.y ?? node.y,
        };
      });
    }

    this.nodesDs.clear();
    this.nodesDs.add(nodesToRender);
    this.edgesDs.clear();
    this.edgesDs.add(styledEdges);

    if (reposition) {
      this.apply2DLayout();
    } else if (this.network) {
      this.network.redraw();
    }
  }

  applyFocusFilters(nodes, edges, state) {
    let filteredNodes = nodes;
    let filteredEdges = edges;

    if (this.localFocusMode && state.selectedNodeId) {
      ({ nodes: filteredNodes, edges: filteredEdges } = this.filterLocalFocus(filteredNodes, filteredEdges, state.selectedNodeId));
    }

    if (this.pathPreset !== 'none') {
      ({ nodes: filteredNodes, edges: filteredEdges } = this.filterPathPreset(filteredNodes, filteredEdges, this.pathPreset));
    }

    if (this.traceDirection !== 'none' && state.selectedNodeId) {
      ({ nodes: filteredNodes, edges: filteredEdges } = this.filterDirectionalTrace(
        filteredNodes,
        filteredEdges,
        state.selectedNodeId,
        this.traceDirection
      ));
    }

    return {
      nodes: filteredNodes,
      edges: filteredEdges,
    };
  }

  filterLocalFocus(nodes, edges, focusNodeId) {
    const keepNodeIds = new Set([focusNodeId]);
    edges.forEach((edge) => {
      if (edge.from === focusNodeId || edge.to === focusNodeId) {
        keepNodeIds.add(edge.from);
        keepNodeIds.add(edge.to);
      }
    });

    return {
      nodes: nodes.filter((node) => keepNodeIds.has(node.id)),
      edges: edges.filter((edge) => keepNodeIds.has(edge.from) && keepNodeIds.has(edge.to)),
    };
  }

  getPresetConfig(preset) {
    if (preset === 'evidence_chain') {
      return {
        types: new Set(['CourtCase', 'AggregateGroup', 'Evidence', 'Fact', 'DisputeFocus', 'LegalProvisionElement', 'LegalProvision', 'JudgmentResult', 'CaseSummary']),
        relations: new Set(['aggregate_link', 'proves_fact', 'matches_element', 'element_of_provision', 'judgment_cites', 'leads_to', 'resolved_by']),
      };
    }

    if (preset === 'judgment_basis') {
      return {
        types: new Set(['CourtCase', 'AggregateGroup', 'Fact', 'DisputeFocus', 'LegalProvisionElement', 'LegalProvision', 'JudgmentResult', 'CaseSummary']),
        relations: new Set(['aggregate_link', 'matches_element', 'element_of_provision', 'judgment_cites', 'leads_to', 'resolved_by']),
      };
    }

    return null;
  }

  filterPathPreset(nodes, edges, preset) {
    const config = this.getPresetConfig(preset);
    if (!config) {
      return { nodes, edges };
    }

    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const keepEdgeIds = new Set();
    const keepNodeIds = new Set();

    edges.forEach((edge) => {
      const relationType = this.getRelationType(edge);
      const fromType = this.getNodeType(nodeMap.get(edge.from));
      const toType = this.getNodeType(nodeMap.get(edge.to));
      const relationMatched = config.relations.has(relationType);
      const typeMatched = config.types.has(fromType) && config.types.has(toType);

      if (relationMatched && typeMatched) {
        keepEdgeIds.add(edge.id);
        keepNodeIds.add(edge.from);
        keepNodeIds.add(edge.to);
      }
    });

    nodes.forEach((node) => {
      if (this.isAggregateNode(node) && config.types.has(this.getNodeType(node))) {
        keepNodeIds.add(node.id);
      }
    });

    return {
      nodes: nodes.filter((node) => keepNodeIds.has(node.id)),
      edges: edges.filter((edge) => keepEdgeIds.has(edge.id)),
    };
  }

  filterDirectionalTrace(nodes, edges, focusNodeId, direction) {
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const keepNodeIds = new Set([focusNodeId]);
    const keepEdgeIds = new Set();
    const nodeDepthMap = new Map([[focusNodeId, 0]]);
    const edgeDepthMap = new Map();
    const queue = [{ nodeId: focusNodeId, depth: 0 }];
    const visited = new Set([`${focusNodeId}:0`]);
    const maxDepth = 3;

    const eligibleEdges = edges.filter((edge) => {
      if (edge.isAggregateEdge) return true;
      if (edge.edgePriority === 'P0' || edge.edgePriority === 'P1') return true;
      return Boolean(edge.isExpandedStructural);
    });

    while (queue.length > 0) {
      const current = queue.shift();
      if (!current || current.depth >= maxDepth) continue;

      eligibleEdges.forEach((edge) => {
        const matchesDirection = direction === 'upstream'
          ? edge.to === current.nodeId
          : edge.from === current.nodeId;
        if (!matchesDirection) return;

        const nextNodeId = direction === 'upstream' ? edge.from : edge.to;
        if (!nodeMap.has(nextNodeId) && nextNodeId !== focusNodeId) return;

        keepEdgeIds.add(edge.id);
        keepNodeIds.add(edge.from);
        keepNodeIds.add(edge.to);
        if (!edgeDepthMap.has(edge.id)) {
          edgeDepthMap.set(edge.id, current.depth + 1);
        }
        if (!nodeDepthMap.has(nextNodeId) || nodeDepthMap.get(nextNodeId) > current.depth + 1) {
          nodeDepthMap.set(nextNodeId, current.depth + 1);
        }

        const visitKey = `${nextNodeId}:${current.depth + 1}`;
        if (!visited.has(visitKey)) {
          visited.add(visitKey);
          queue.push({ nodeId: nextNodeId, depth: current.depth + 1 });
        }
      });
    }

    return {
      nodes: nodes
        .filter((node) => keepNodeIds.has(node.id))
        .map((node) => ({
          ...node,
          isTraceNode: true,
          isTraceFocus: node.id === focusNodeId,
          traceDepth: nodeDepthMap.get(node.id) ?? 0,
        })),
      edges: edges
        .filter((edge) => keepEdgeIds.has(edge.id))
        .map((edge) => ({
          ...edge,
          isTraceEdge: true,
          traceDepth: edgeDepthMap.get(edge.id) ?? 1,
          traceDirection: direction,
        })),
    };
  }

  refreshTraceSummary(state, nodes) {
    if (this.traceDirection === 'none' || !state.selectedNodeId) {
      this.setTraceSummary('');
      return;
    }

    const focusNode = nodes.find((node) => node.id === state.selectedNodeId)
      || state.parseGraphData?.nodes?.find((node) => node.id === state.selectedNodeId);
    const focusLabel = focusNode?.fullLabel || focusNode?.label || state.selectedNodeId;
    const typeCounter = new Map();

    (nodes || []).forEach((node) => {
      if (!node || node.id === state.selectedNodeId || this.isAggregateNode(node)) return;
      const type = this.getNodeType(node) || '未分类';
      typeCounter.set(type, (typeCounter.get(type) || 0) + 1);
    });

    const summaryItems = Array.from(typeCounter.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'zh-CN'))
      .slice(0, 4)
      .map(([type, count]) => `${type} ${count}`);

    const directionLabel = this.traceDirection === 'upstream' ? '上游' : '下游';
    const summary = summaryItems.length
      ? `追踪摘要：以 ${this.truncateLabel(focusLabel, 16)} 为中心，当前 ${directionLabel}路径覆盖 ${summaryItems.join('，')}`
      : `追踪摘要：以 ${this.truncateLabel(focusLabel, 16)} 为中心，当前仅保留中心节点`;

    this.setTraceSummary(summary);
  }

  buildDisplayGraph(rawNodes, rawEdges, state) {
    const nodes = (rawNodes || []).map(node => ({ ...node }));
    const rawNodeMap = new Map(nodes.map(node => [node.id, node]));
    const expandedGroups = state.parseGraphExpandedGroups || {};
    const displayMode = state.parseGraphDisplayMode || 'skeleton';
    const displayEdges = [];
    const aggregateGroups = new Map();
    // NOTE: We keep all entity nodes visible by default.
    // "skeleton" mode should reduce clutter mainly by weakening/hiding structural edges,
    // not by removing core entities from the graph.

    (rawEdges || []).forEach((edge, index) => {
      const relationType = this.getRelationType(edge);
      const normalizedEdge = {
        ...edge,
        id: edge.id || `edge_${index}`,
        relationType,
        edgePriority: this.getEdgePriority(edge),
        isStructural: this.isStructuralEdge(edge),
        isCaseContextEdge: this.isCaseContextEdge(edge, rawNodeMap),
        fromLane: this.getNodeLane(rawNodeMap.get(edge.from)),
        toLane: this.getNodeLane(rawNodeMap.get(edge.to)),
      };

      const aggregateMeta = this.getAggregateEdgeMeta(normalizedEdge, rawNodeMap);
      if (displayMode === 'skeleton' && aggregateMeta) {
        const aggregateKey = `${aggregateMeta.courtCaseId}:${aggregateMeta.groupKey}`;
        if (!aggregateGroups.has(aggregateKey)) {
          aggregateGroups.set(aggregateKey, {
            aggregateKey,
            courtCaseId: aggregateMeta.courtCaseId,
            groupKey: aggregateMeta.groupKey,
            label: aggregateMeta.groupLabel,
            lane: aggregateMeta.lane,
            nodeIds: new Set(),
          });
        }
        const group = aggregateGroups.get(aggregateKey);
        group.nodeIds.add(aggregateMeta.childId);

        if (!expandedGroups[aggregateKey]) {
          // Keep node + edge; we only add an aggregate entrance node for convenience.
          normalizedEdge.isCollapsedStructural = true;
        } else {
          normalizedEdge.isExpandedStructural = true;
        }

        normalizedEdge.hidden = false;
      }

      displayEdges.push(normalizedEdge);
    });

    const aggregateNodes = [];
    const aggregateEdges = [];
    aggregateGroups.forEach((group) => {
      const aggregateNodeId = `aggregate:${group.aggregateKey}`;
      aggregateNodes.push({
        id: aggregateNodeId,
        nodeType: 'AggregateGroup',
        group: 'AggregateGroup',
        aggregateKey: group.aggregateKey,
        aggregateCount: group.nodeIds.size,
        aggregateLane: group.lane,
        aggregateLabel: group.label,
        label: `${group.label} ${group.nodeIds.size}`,
        title: `${group.label} ${group.nodeIds.size}`,
      });
      aggregateEdges.push({
        id: `aggregate-edge:${group.aggregateKey}`,
        from: group.courtCaseId,
        to: aggregateNodeId,
        relationType: 'aggregate_link',
        edgePriority: 'P2',
        isAggregateEdge: true,
        isCaseContextEdge: false,
        hidden: false,
        fromLane: 'caseLane',
        toLane: group.lane,
      });
    });

    return {
      nodes: [...nodes, ...aggregateNodes],
      edges: [...displayEdges, ...aggregateEdges],
    };
  }

  getAggregateEdgeMeta(edge, rawNodeMap) {
    if (!edge?.isStructural) return null;
    const fromNode = rawNodeMap.get(edge.from);
    const toNode = rawNodeMap.get(edge.to);
    const fromType = this.getNodeType(fromNode);
    const toType = this.getNodeType(toNode);

    if (fromType === 'CourtCase' && AGGREGATE_GROUP_CONFIG[toType]) {
      const config = AGGREGATE_GROUP_CONFIG[toType];
      return {
        courtCaseId: edge.from,
        childId: edge.to,
        groupKey: config.key,
        groupLabel: config.label,
        lane: config.lane,
      };
    }

    if (toType === 'CourtCase' && AGGREGATE_GROUP_CONFIG[fromType]) {
      const config = AGGREGATE_GROUP_CONFIG[fromType];
      return {
        courtCaseId: edge.to,
        childId: edge.from,
        groupKey: config.key,
        groupLabel: config.label,
        lane: config.lane,
      };
    }

    return null;
  }

  getSemanticZoomLevel(scale = this.network?.getScale?.() ?? 1) {
    if (scale <= 0.7) return 'far';
    if (scale >= 1.35) return 'near';
    return 'mid';
  }

  updateSemanticZoom(force = false) {
    if (!this.network || !this.lastRenderedData) return;
    const nextZoom = this.getSemanticZoomLevel();
    if (!force && nextZoom === this.semanticZoom) return;

    this.semanticZoom = nextZoom;
    store.setState({ parseGraphSemanticZoom: nextZoom });
    this.syncRenderedGraph({ preservePositions: true });
  }

  truncateLabel(text, maxLength) {
    const source = String(text || '').replace(/\s+/g, ' ').trim();
    if (!source || !maxLength || source.length <= maxLength) return source;
    return `${source.slice(0, Math.max(1, maxLength - 1))}…`;
  }

  getLegalProvisionArticleMarker(node) {
    const explicit = String(node?.articleNumber || node?.article || '').trim();
    if (explicit) {
      const explicitMatch = explicit.match(/第?\s*([0-9A-Za-z一二三四五六七八九十百千万零〇两甲乙丙丁戊己庚辛壬癸]+(?:之[0-9A-Za-z一二三四五六七八九十百千万零〇两甲乙丙丁戊己庚辛壬癸]+)?)\s*条?/);
      if (explicitMatch?.[1]) return String(explicitMatch[1]).trim();
      const cleaned = explicit.replace(/^第/, '').replace(/条$/, '').trim();
      if (cleaned && cleaned !== '条') return cleaned;
    }
    const fullLabel = String(node?.fullLabel || node?.label || '');
    const match = fullLabel.match(/第([0-9A-Za-z一二三四五六七八九十百千万零〇两甲乙丙丁戊己庚辛壬癸]+(?:之[0-9A-Za-z一二三四五六七八九十百千万零〇两甲乙丙丁戊己庚辛壬癸]+)?)条/);
    return match ? String(match[1] || '').trim() : '';
  }

  getLegalProvisionStatuteShort(node) {
    const explicit = String(node?.statuteName || '').trim();
    const raw = explicit || String(node?.fullLabel || node?.label || '').split('第')[0] || '';
    return raw.replace(/^中华人民共和国/, '').trim();
  }

  escapeSvgText(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  getLegalProvisionGlyphText(node) {
    const article = this.getLegalProvisionArticleMarker(node);
    return String(article || '').replace(/^第/, '').replace(/条$/, '').trim() || '法';
  }

  buildLegalProvisionNodeImage({ text, statuteLabel = '', background, border, fontColor, borderWidth = 2, borderDashes = false }) {
    const glyph = this.escapeSvgText(text);
    const fontSize = glyph.length >= 4 ? 30 : glyph.length === 3 ? 36 : glyph.length === 2 ? 44 : 52;
    const dashArray = Array.isArray(borderDashes) ? borderDashes.join(' ') : (borderDashes ? '7 5' : 'none');
    const safeStatute = this.escapeSvgText(this.truncateLabel(statuteLabel || '', 16));
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 156">
        <polygon
          points="72,8 122,36 122,94 72,122 22,94 22,36"
          fill="${background}"
          stroke="${border}"
          stroke-width="${borderWidth}"
          stroke-dasharray="${dashArray}"
          stroke-linejoin="round"
        />
        <text
          x="72"
          y="67"
          text-anchor="middle"
          dominant-baseline="middle"
          font-family="Microsoft YaHei, PingFang SC, Helvetica Neue, Arial, sans-serif"
          font-size="${fontSize}"
          font-weight="700"
          fill="${fontColor}"
        >${glyph}</text>
        <text
          x="72"
          y="141"
          text-anchor="middle"
          dominant-baseline="middle"
          font-family="Microsoft YaHei, PingFang SC, Helvetica Neue, Arial, sans-serif"
          font-size="18"
          font-weight="600"
          fill="${fontColor}"
        >${safeStatute}</text>
      </svg>
    `;
    return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
  }

  getNodeDisplayLabel(node, state, type) {
    const semanticZoom = state.parseGraphSemanticZoom || this.semanticZoom || 'mid';
    const fullLabel = node.fullLabel || node.label || node.title || node.id || '';

    if (type === 'LegalProvision') {
      const articleMarker = this.getLegalProvisionArticleMarker(node);
      return articleMarker || '法条';
    }

    if (type === 'AggregateGroup') {
      const aggregateExpanded = Boolean(state.parseGraphExpandedGroups?.[node.aggregateKey]);
      const prefix = aggregateExpanded ? '收起' : '展开';
      return semanticZoom === 'far'
        ? `${node.aggregateLabel || ''} ${node.aggregateCount ?? ''}`.trim()
        : `${prefix}${node.aggregateLabel || ''}\n${node.aggregateCount ?? ''}`.trim();
    }

    if (semanticZoom === 'far') {
      const farLimitMap = {
        CourtCase: 12,
        Evidence: 8,
        Fact: 8,
        LegalSubject: 8,
        Judge: 8,
        Attorney: 8,
        Person: 8,
        DisputeFocus: 8,
        JudgmentResult: 8,
        CaseSummary: 8,
        LegalProvisionElement: 8,
        LegalProvision: 8,
        Law: 8,
      };
      return this.truncateLabel(fullLabel, farLimitMap[type] || 8);
    }

    if (semanticZoom === 'mid') {
      const limitMap = {
        CourtCase: 14,
        Evidence: 10,
        Fact: 12,
        LegalProvisionElement: 10,
        LegalProvision: 10,
        Law: 10,
        Person: 8,
        LegalSubject: 8,
        Judge: 6,
        Attorney: 6,
      };
      return this.truncateLabel(fullLabel, limitMap[type] || 10);
    }

    return fullLabel;
  }

  getNodeChangeMarker(nodeId, highlight, semanticZoom = 'mid') {
    if (!highlight || !nodeId) return '';
    if ((highlight.addedNodeIds || []).includes(nodeId)) {
      return semanticZoom === 'far' ? '+' : '+ ';
    }
    if ((highlight.updatedNodeIds || []).includes(nodeId)) {
      return semanticZoom === 'far' ? '●' : '● ';
    }
    return '';
  }

  getEdgeDisplayLabel(edge, state) {
    const semanticZoom = state.parseGraphSemanticZoom || this.semanticZoom || 'mid';
    const displayMode = state.parseGraphDisplayMode || 'skeleton';
    const fullLabel = edge.fullLabel || edge.label || edge.relationType || '';
    if (!fullLabel || edge.isAggregateEdge) return '';
    if (edge.isCaseContextEdge) {
      return semanticZoom === 'near' && displayMode !== 'skeleton' ? fullLabel : '';
    }
    if (semanticZoom === 'far') {
      return edge.edgePriority === 'P0' ? fullLabel : '';
    }
    if (semanticZoom === 'mid') {
      if (edge.edgePriority === 'P0') return fullLabel;
      if (edge.edgePriority === 'P1' && displayMode !== 'skeleton') return fullLabel;
      return '';
    }
    if (edge.edgePriority === 'P2' && !edge.isExpandedStructural) {
      return '';
    }
    if (displayMode === 'skeleton' && edge.edgePriority === 'P1') {
      return '';
    }
    return fullLabel;
  }

  getEdgeSmooth(edge) {
    if (edge.isTraceEdge) {
      return {
        type: 'cubicBezier',
        forceDirection: 'horizontal',
        roundness: edge.traceDepth <= 1 ? 0.24 : edge.traceDepth === 2 ? 0.18 : 0.14,
      };
    }

    if (edge.isAggregateEdge) {
      return { type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.08 };
    }

    if (edge.isCaseContextEdge) {
      if ((edge.fromLane === 'caseLane' && edge.toLane === 'subjectLane') || (edge.fromLane === 'subjectLane' && edge.toLane === 'caseLane')) {
        return {
          type: 'cubicBezier',
          forceDirection: 'horizontal',
          roundness: 0.012,
        };
      }
      return {
        type: 'cubicBezier',
        forceDirection: 'horizontal',
        roundness: 0.035,
      };
    }

    const laneOrder = {
      caseLane: 0,
      subjectLane: 1,
      evidenceLane: 2,
      factLane: 3,
      elementLane: 4,
      lawLane: 5,
      resultLane: 6,
    };
    const fromLaneIndex = laneOrder[edge.fromLane] ?? 0;
    const toLaneIndex = laneOrder[edge.toLane] ?? 0;
    const laneDistance = Math.max(1, Math.abs(toLaneIndex - fromLaneIndex));

    if (edge.edgePriority === 'P2') {
      return {
        type: 'cubicBezier',
        forceDirection: 'horizontal',
        roundness: edge.isExpandedStructural ? 0.08 : 0.04,
      };
    }

    if (edge.edgePriority === 'P0') {
      return {
        type: 'cubicBezier',
        forceDirection: 'horizontal',
        roundness: laneDistance >= 3 ? 0.2 : 0.12,
      };
    }

    return {
      type: 'cubicBezier',
      forceDirection: 'horizontal',
      roundness: laneDistance >= 3 ? 0.14 : 0.1,
    };
  }

  getActiveMergeHighlight(state = store.getState()) {
    if (state.parseEnhancementPreviewActive && state.parseEnhancementPreviewPatch) {
      return state.parseEnhancementPreviewPatch;
    }
    return state.parseMergeHighlight || null;
  }

  styleEdges(edges, state = store.getState()) {
    const highlight = this.getActiveMergeHighlight(state);
    const isPreview = Boolean(state.parseEnhancementPreviewActive && state.parseEnhancementPreviewPatch);
    const addedEdgeIds = new Set(highlight?.addedEdgeIds || []);
    const updatedEdgeIds = new Set(highlight?.updatedEdgeIds || []);
    const addedDerivedEdgeIds = new Set(highlight?.addedDerivedEdgeIds || []);
    const updatedDerivedEdgeIds = new Set(highlight?.updatedDerivedEdgeIds || []);
    return (edges || []).map(e => ({
      ...e,
      fullLabel: e.fullLabel || e.label || e.relationType || '',
      label: this.getEdgeDisplayLabel(e, state),
      smooth: e.smooth || this.getEdgeSmooth(e),
      hidden: Boolean(e.hidden),
      dashes: (
        addedDerivedEdgeIds.has(e.id) || updatedDerivedEdgeIds.has(e.id)
          ? true
          : addedEdgeIds.has(e.id) || updatedEdgeIds.has(e.id)
            ? false
            : e.dashes || e.isAggregateEdge || e.isCaseContextEdge || (e.edgePriority === 'P2') || (e.edgePriority === 'P1' && state.parseGraphDisplayMode === 'skeleton')
      ),
      color: (
        addedEdgeIds.has(e.id) || addedDerivedEdgeIds.has(e.id)
          ? { color: '#0ea5e9', highlight: '#0284c7' }
          : updatedEdgeIds.has(e.id) || updatedDerivedEdgeIds.has(e.id)
            ? { color: '#f59e0b', highlight: '#d97706' }
          : e.color || (
        e.isTraceEdge
          ? {
              color: e.traceDirection === 'upstream'
                ? (e.traceDepth <= 1 ? '#0f766e' : e.traceDepth === 2 ? '#14b8a6' : '#7dd3fc')
                : (e.traceDepth <= 1 ? '#ea580c' : e.traceDepth === 2 ? '#f97316' : '#fdba74'),
              highlight: e.traceDirection === 'upstream' ? '#115e59' : '#c2410c'
            }
          : e.isAggregateEdge
          ? { color: '#94a3b8', highlight: '#64748b' }
          : e.isCaseContextEdge
            ? { color: 'rgba(148, 163, 184, 0.26)', highlight: '#94a3b8' }
          : e.edgePriority === 'P0'
            ? { color: '#2563eb', highlight: '#1d4ed8' }
            : e.edgePriority === 'P2'
              ? { color: e.isExpandedStructural ? 'rgba(148, 163, 184, 0.45)' : 'rgba(203, 213, 225, 0.12)', highlight: '#94a3b8' }
              : state.parseGraphDisplayMode === 'skeleton'
                ? { color: 'rgba(99, 102, 241, 0.52)', highlight: '#4f46e5' }
                : { color: '#6366f1', highlight: '#4f46e5' }
      )),
      width: (
        addedEdgeIds.has(e.id) || updatedEdgeIds.has(e.id) || addedDerivedEdgeIds.has(e.id) || updatedDerivedEdgeIds.has(e.id)
          ? (isPreview ? 4.1 : 3.3)
          : e.width || (
        e.isTraceEdge
          ? (e.traceDepth <= 1 ? 3.6 : e.traceDepth === 2 ? 2.8 : 2.1)
          : e.isAggregateEdge
          ? 1.6
          : e.isCaseContextEdge
            ? 0.75
          : e.edgePriority === 'P0'
            ? 2.8
            : e.edgePriority === 'P2'
              ? (e.isExpandedStructural ? 1.1 : 0.55)
              : state.parseGraphDisplayMode === 'skeleton'
                ? 1.55
                : 1.8
      )),
      font: {
        size: state.parseGraphSemanticZoom === 'near' ? (e.edgePriority === 'P0' ? 11 : 10) : (e.edgePriority === 'P0' ? 10 : 9),
        color: addedEdgeIds.has(e.id) || addedDerivedEdgeIds.has(e.id)
          ? '#0369a1'
          : updatedEdgeIds.has(e.id) || updatedDerivedEdgeIds.has(e.id)
            ? '#b45309'
          : e.isTraceEdge
          ? (e.traceDirection === 'upstream' ? '#115e59' : '#c2410c')
          : e.isAggregateEdge
          ? '#64748b'
          : e.isCaseContextEdge
            ? 'rgba(100, 116, 139, 0.48)'
          : e.edgePriority === 'P2'
            ? 'rgba(148, 163, 184, 0.82)'
            : state.parseGraphDisplayMode === 'skeleton'
              ? 'rgba(79, 70, 229, 0.82)'
              : '#4f46e5',
        align: 'horizontal',
        strokeWidth: 2,
        strokeColor: '#ffffff',
        vadjust: e.isAggregateEdge ? -6 : 0,
        multi: 'md',
        ...(e.font || {})
      }
    }));
  }

  styleNodes(nodes, state = store.getState()) {
    const highlight = this.getActiveMergeHighlight(state);
    const isPreview = Boolean(state.parseEnhancementPreviewActive && state.parseEnhancementPreviewPatch);
    const addedNodeIds = new Set(highlight?.addedNodeIds || []);
    const updatedNodeIds = new Set(highlight?.updatedNodeIds || []);
    const defaultStyles = {
      CourtCase:  { shape: 'box', color: '#FFA07A', border: '#E8875A' },
      CaseType:   { shape: 'box', color: '#fff7ed', border: '#fb923c', fontColor: '#9a3412' },
      Person:     { shape: 'square', color: '#90EE90', border: '#6BCE6B' },
      Judge:      { shape: 'box', color: '#dbeafe', border: '#60a5fa', fontColor: '#1d4ed8' },
      Attorney:   { shape: 'box', color: '#ede9fe', border: '#8b5cf6', fontColor: '#6d28d9' },
      LegalProvision: { shape: 'hexagon', color: '#d9ddff', border: '#5b6ee1', fontColor: '#1e2b6d' },
      LegalProvisionElement: { shape: 'box', color: '#eef2ff', border: '#7c8cff', fontColor: '#243b8f' },
      Law:        { shape: 'hexagon', color: '#d9ddff', border: '#5b6ee1', fontColor: '#1e2b6d' },
      Evidence:   { shape: 'box', color: '#f7e2bf', border: '#c9852b', fontColor: '#6b3f08' },
      Fact:       { shape: 'box', color: '#e0f2fe', border: '#0284c7', fontColor: '#0f172a' },
      DisputeFocus: { shape: 'diamond', color: '#fef3c7', border: '#d97706', fontColor: '#92400e' },
      LitigationClaim: { shape: 'diamond', color: '#fce7f3', border: '#db2777', fontColor: '#9d174d' },
      ProceduralOpinion: { shape: 'box', color: '#ede9fe', border: '#7c3aed', fontColor: '#5b21b6' },
      ArgumentPoint: { shape: 'box', color: '#fff7ed', border: '#ea580c', fontColor: '#9a3412' },
      JudicialAssessment: { shape: 'star', color: '#dcfce7', border: '#16a34a', fontColor: '#166534' },
      JudgmentResult: { shape: 'box', color: '#dcfce7', border: '#16a34a', fontColor: '#166534' },
      LegalRole:  { shape: 'diamond', color: '#FFA500', border: '#CC8400' },
      CaseSummary: { shape: 'star', color: '#32CD32', border: '#28A428' },
      LegalSubject: { shape: 'triangle', color: '#B0C4DE', border: '#8DA3B8' },
      LegalNorm:  { shape: 'triangle', color: '#B0C4DE', border: '#8DA3B8' },
      GuidingCase:  { shape: 'star', color: '#4682B4', border: '#35608C' },
      AggregateGroup: { shape: 'box', color: '#f8fafc', border: '#94a3b8', fontColor: '#475569' },
    };

    return nodes.map(n => {
      const type = n.nodeType || n.group || '';
      const style = defaultStyles[type] || { shape: 'box', color: '#f8fafc', border: '#cbd5e1' };
      const aggregateExpanded = type === 'AggregateGroup' && state.parseGraphExpandedGroups?.[n.aggregateKey];
      const fullLabel = n.fullLabel || n.label || n.title || n.id;
      const baseLabel = this.getNodeDisplayLabel({ ...n, fullLabel }, state, type);
      const labelMarker = type === 'AggregateGroup'
        ? ''
        : this.getNodeChangeMarker(n.id, highlight, state.parseGraphSemanticZoom || this.semanticZoom || 'mid');
      const label = type === 'LegalProvision' ? '' : (labelMarker ? `${labelMarker}${baseLabel}` : baseLabel);
      const legalProvisionGlyph = type === 'LegalProvision' ? this.getLegalProvisionGlyphText({ ...n, fullLabel }) : '';
      const legalProvisionStatute = type === 'LegalProvision' ? this.getLegalProvisionStatuteShort({ ...n, fullLabel }) : '';
      const isBoxLike = ['box', 'square', 'hexagon'].includes(style.shape);
      const baseSize = type === 'AggregateGroup'
        ? 24
        : style.shape === 'triangle'
          ? 18
          : style.shape === 'diamond'
            ? 18
            : style.shape === 'star'
              ? 20
              : style.shape === 'hexagon'
                ? 20
                : 18;
      const traceColors = n.isTraceNode
        ? (n.isTraceFocus
            ? { background: '#fef3c7', border: '#d97706', font: '#7c2d12' }
            : n.traceDepth <= 1
              ? { background: '#eff6ff', border: '#2563eb', font: '#1e3a8a' }
              : n.traceDepth === 2
                ? { background: '#f8fafc', border: '#60a5fa', font: '#1e40af' }
                : { background: '#f8fafc', border: '#cbd5e1', font: '#475569' })
        : null;
      const mergeColors = addedNodeIds.has(n.id)
        ? {
            border: '#0ea5e9',
            shadow: isPreview ? 'rgba(14,165,233,0.34)' : 'rgba(14,165,233,0.22)',
            borderWidth: isPreview ? 4.5 : 3.4,
            borderDashes: false
          }
        : updatedNodeIds.has(n.id)
          ? {
              border: '#f59e0b',
              shadow: isPreview ? 'rgba(245,158,11,0.26)' : 'rgba(245,158,11,0.18)',
              borderWidth: isPreview ? 4.2 : 3.2,
              borderDashes: [7, 5]
            }
          : null;
      const fillColor = traceColors?.background || (aggregateExpanded ? '#e0f2fe' : style.color);
      const borderColor = mergeColors?.border || traceColors?.border || (aggregateExpanded ? '#0284c7' : style.border);
      const fontColor = traceColors?.font || (aggregateExpanded ? '#0f172a' : (style.fontColor || '#333'));
      
      return {
        ...n,
        fullLabel,
        label,
        nodeType: type,
        shape: type === 'LegalProvision' ? 'image' : style.shape,
        image: type === 'LegalProvision'
          ? this.buildLegalProvisionNodeImage({
              text: legalProvisionGlyph,
              statuteLabel: legalProvisionStatute,
              background: fillColor,
              border: borderColor,
              fontColor,
              borderWidth: mergeColors?.borderWidth || (n.isTraceFocus ? 3 : (n.isTraceNode ? 2.5 : 2)),
              borderDashes: mergeColors?.borderDashes || false,
            })
          : undefined,
        color: {
          background: fillColor,
          border: borderColor,
        },
        borderWidth: mergeColors?.borderWidth || (n.isTraceFocus ? 3 : (type === 'AggregateGroup' ? 1.5 : (n.isTraceNode ? 2.5 : 2))),
        shapeProperties: {
          ...(n.shapeProperties || {}),
          borderDashes: mergeColors?.borderDashes || false,
        },
        margin: type === 'AggregateGroup'
          ? { top: 8, right: 10, bottom: 8, left: 10 }
          : isBoxLike
            ? { top: 8, right: 12, bottom: 8, left: 12 }
            : undefined,
        size: state.parseGraphSemanticZoom === 'far' && type !== 'CourtCase'
          ? Math.max(baseSize, type === 'LegalProvision' ? 38 : 24)
          : (type === 'LegalProvision' ? Math.max(baseSize, 38) : baseSize),
        widthConstraint: isBoxLike
          ? { minimum: type === 'AggregateGroup' ? 74 : 78 }
          : undefined,
        heightConstraint: isBoxLike
          ? { minimum: type === 'AggregateGroup' ? 34 : 38 }
          : undefined,
        shadow: n.isTraceNode
          ? { enabled: true, color: n.isTraceFocus ? 'rgba(217,119,6,0.35)' : 'rgba(37,99,235,0.18)', size: n.isTraceFocus ? 18 : 10 }
          : { enabled: true, color: mergeColors?.shadow || 'rgba(15,23,42,0.12)', size: mergeColors ? (isPreview ? 18 : 11) : 8, x: 0, y: 2 },
        font: {
          size: type === 'AggregateGroup'
            ? (state.parseGraphSemanticZoom === 'far' ? 12 : 13)
            : (state.parseGraphSemanticZoom === 'near' ? 16 : 15),
          color: fontColor,
          face: 'Microsoft YaHei, PingFang SC, Helvetica Neue, Arial, sans-serif',
          strokeWidth: 3,
          strokeColor: '#ffffff',
          vadjust: 0,
        }
      };
    });
  }

  applyClustering() {
    if (!this.network) return;
  }

  getNodeType(node) {
    return node?.nodeType || node?.group || '';
  }

  getNodeLane(node) {
    const type = this.getNodeType(node);
    if (type === 'AggregateGroup' && node?.aggregateLane) {
      return node.aggregateLane;
    }
    if (['GuidingCase', 'CaseType', 'CourtCase'].includes(type)) return 'caseLane';
    if (['Judge', 'Attorney', 'LegalRole', 'LegalSubject', 'Person'].includes(type)) return 'subjectLane';
    if (['Evidence', 'LitigationClaim', 'ProceduralOpinion'].includes(type)) return 'evidenceLane';
    if (['Fact', 'ArgumentPoint', 'JudicialAssessment'].includes(type)) return 'factLane';
    if (type === 'LegalProvisionElement') return 'elementLane';
    if (['LegalProvision', 'Law', 'LegalNorm'].includes(type)) return 'lawLane';
    if (['DisputeFocus', 'JudgmentResult', 'CaseSummary'].includes(type)) return 'resultLane';
    return 'caseLane';
  }

  getNodeOrderKey(node, typeRank) {
    const type = this.getNodeType(node);
    return `${String(typeRank[type] ?? 9).padStart(2, '0')}|${node.label || node.id || ''}`;
  }

  reorderLaneBuckets(laneBuckets, edges) {
    const laneOrder = ['caseLane', 'subjectLane', 'evidenceLane', 'factLane', 'elementLane', 'lawLane', 'resultLane'];
    const edgeList = edges || [];
    const nodeLaneMap = new Map();
    const nodeIndexMap = new Map();

    const refreshIndices = () => {
      nodeLaneMap.clear();
      nodeIndexMap.clear();
      laneOrder.forEach((laneKey) => {
        (laneBuckets[laneKey] || []).forEach((node, index) => {
          nodeLaneMap.set(node.id, laneKey);
          nodeIndexMap.set(node.id, index);
        });
      });
    };

    const computeScore = (nodeId, laneIndex) => {
      let total = 0;
      let weightSum = 0;
      edgeList.forEach((edge) => {
        let neighborId = null;
        if (edge.from === nodeId) neighborId = edge.to;
        else if (edge.to === nodeId) neighborId = edge.from;
        if (!neighborId || !nodeIndexMap.has(neighborId)) return;

        const neighborLane = nodeLaneMap.get(neighborId);
        const neighborLaneIndex = laneOrder.indexOf(neighborLane);
        if (neighborLaneIndex === -1) return;

        const distance = Math.abs(neighborLaneIndex - laneIndex) || 1;
        const priorityWeight = edge.edgePriority === 'P0' ? 2.6 : edge.edgePriority === 'P1' ? 1.6 : 0.65;
        const laneWeight = priorityWeight / distance;
        total += nodeIndexMap.get(neighborId) * laneWeight;
        weightSum += laneWeight;
      });
      return weightSum ? (total / weightSum) : null;
    };

    const sortLane = (laneKey) => {
      const laneIndex = laneOrder.indexOf(laneKey);
      const bucket = laneBuckets[laneKey] || [];
      bucket.sort((a, b) => {
        const typeA = this.getNodeType(a);
        const typeB = this.getNodeType(b);
        const isClaimA = ['LitigationClaim', 'ProceduralOpinion', 'ArgumentPoint', 'JudicialAssessment'].includes(typeA);
        const isClaimB = ['LitigationClaim', 'ProceduralOpinion', 'ArgumentPoint', 'JudicialAssessment'].includes(typeB);
        
        if (isClaimA && !isClaimB) return 1;
        if (!isClaimA && isClaimB) return -1;

        const scoreA = computeScore(a.id, laneIndex);
        const scoreB = computeScore(b.id, laneIndex);
        if (scoreA == null && scoreB == null) return 0;
        if (scoreA == null) return 1;
        if (scoreB == null) return -1;
        return scoreA - scoreB;
      });
    };

    refreshIndices();
    for (let round = 0; round < 2; round += 1) {
      laneOrder.forEach((laneKey) => {
        sortLane(laneKey);
        refreshIndices();
      });
      [...laneOrder].reverse().forEach((laneKey) => {
        sortLane(laneKey);
        refreshIndices();
      });
    }
  }

  buildVerticalLanePositions(nodes, edges = []) {
    const laneBuckets = {
      caseLane: [],
      subjectLane: [],
      evidenceLane: [],
      factLane: [],
      elementLane: [],
      lawLane: [],
      resultLane: [],
    };

    const typeRank = {
      GuidingCase: 0,
      CaseType: 1,
      CourtCase: 2,
      AggregateGroup: 3,
      Evidence: 0,
      LitigationClaim: 8,
      ProceduralOpinion: 9,
      Fact: 0,
      ArgumentPoint: 8,
      JudicialAssessment: 9,
      LegalProvision: 0,
      LegalProvisionElement: 1,
      Law: 2,
      LegalNorm: 3,
      CaseSummary: 0,
      DisputeFocus: 1,
      JudgmentResult: 2,
      Judge: 0,
      LegalSubject: 1,
      Attorney: 2,
      LegalRole: 3,
      Person: 4,
    };

    nodes.forEach((node) => {
      const laneKey = this.getNodeLane(node);
      (laneBuckets[laneKey] || laneBuckets.caseLane).push(node);
    });

    Object.values(laneBuckets).forEach((bucket) => bucket.sort((a, b) => this.getNodeOrderKey(a, typeRank).localeCompare(this.getNodeOrderKey(b, typeRank), 'zh-CN')));
    this.reorderLaneBuckets(laneBuckets, edges);

    const updates = [];
    Object.entries(laneBuckets).forEach(([laneKey, bucket]) => {
      const xBase = MAIN_LANE_X[laneKey];
      const yBase = MAIN_LANE_Y[laneKey];
      const spacing = MAIN_LANE_SPACING[laneKey];

      bucket.forEach((node, index) => {
        const type = this.getNodeType(node);
        let targetX = xBase;
        let targetY = yBase + index * spacing;

        if (laneKey === 'caseLane' || laneKey === 'resultLane' || laneKey === 'subjectLane') {
          targetX += AUXILIARY_LANE_X_JITTER[type] || 0;
        }

        updates.push({ id: node.id, x: targetX, y: targetY });
      });
    });

    return updates;
  }

  buildFocusOrbitPositions(nodes, edges = []) {
    const baseUpdates = this.buildVerticalLanePositions(nodes, edges);
    const updatesById = new Map(baseUpdates.map((item) => [item.id, { ...item }]));
    const visibleNodes = (nodes || []).filter((node) => !node.hidden);
    const byType = (types) => visibleNodes.filter((node) => types.includes(this.getNodeType(node)));
    const focusNodes = byType(['DisputeFocus']);
    const elementNodes = byType(['LegalProvisionElement']);
    const lawNodes = byType(['LegalProvision', 'Law', 'LegalNorm']);
    const judgmentNodes = byType(['JudgmentResult']);
    const summaryNodes = byType(['CaseSummary']);
    const centerX = Math.round((MAIN_LANE_X.lawLane + MAIN_LANE_X.resultLane) / 2);
    const centerY = 520;

    const placeArc = (items, { radius, startDeg, endDeg, xOffset = 0, yOffset = 0 }) => {
      if (!items.length) return;
      items.forEach((node, index) => {
        const ratio = items.length === 1 ? 0.5 : index / Math.max(1, items.length - 1);
        const angle = (startDeg + (endDeg - startDeg) * ratio) * (Math.PI / 180);
        updatesById.set(node.id, {
          id: node.id,
          x: Math.round(centerX + Math.cos(angle) * radius + xOffset),
          y: Math.round(centerY + Math.sin(angle) * radius + yOffset),
        });
      });
    };

    const adaptiveRadius = (count, baseRadius, minGap, arcSpanDeg) => {
      if (count <= 1) return baseRadius;
      const spanRad = (arcSpanDeg * Math.PI) / 180;
      return Math.max(baseRadius, Math.round(((count - 1) * minGap) / Math.max(spanRad, 0.8)));
    };

    const placeColumn = (items, { x, spacing, startY = centerY }) => {
      if (!items.length) return;
      const topY = startY - ((items.length - 1) * spacing) / 2;
      items.forEach((node, index) => {
        updatesById.set(node.id, {
          id: node.id,
          x,
          y: Math.round(topY + index * spacing),
        });
      });
    };

    const lawArcSpan = 140;
    const resultArcSpan = 140;
    const summaryArcSpan = 110;
    const lawRadius = adaptiveRadius(lawNodes.length, 360, 92, lawArcSpan);
    const judgmentRadius = adaptiveRadius(judgmentNodes.length, 360, 92, resultArcSpan);
    const summaryRadius = adaptiveRadius(summaryNodes.length, 445, 104, summaryArcSpan);

    // Keep provision elements in their original lane so the "法条元素区" remains stable.
    placeColumn(
      elementNodes,
      {
        x: MAIN_LANE_X.elementLane,
        spacing: 148,
        startY: centerY - 170,
      }
    );
    placeColumn(focusNodes, { x: centerX, spacing: 132, startY: centerY });
    placeArc(lawNodes, { radius: lawRadius, startDeg: 110, endDeg: 250 });
    placeArc(judgmentNodes, { radius: judgmentRadius, startDeg: -70, endDeg: 70 });
    placeArc(summaryNodes, { radius: summaryRadius, startDeg: -55, endDeg: 55, yOffset: -12 });

    return Array.from(updatesById.values());
  }

  buildLayoutPositions(nodes, edges = [], state = store.getState()) {
    return (state.parseGraphLayoutMode || this.layoutMode || 'lane') === 'focus_orbit'
      ? this.buildFocusOrbitPositions(nodes, edges)
      : this.buildVerticalLanePositions(nodes, edges);
  }

  apply2DLayout() {
    const nodes = this.nodesDs.get();
    const edges = this.edgesDs.get();
    this.nodesDs.update(this.buildLayoutPositions(nodes, edges, store.getState()));

    this.applyClustering();

    this.network.fit({ animation: true, minZoomLevel: 0.76, maxZoomLevel: 1.18 });
    setTimeout(() => {
      if (this.network) {
        this.network.moveTo({ scale: 0.98, animation: { duration: 220, easingFunction: 'easeInOutQuad' } });
        this.renderZoneOverlay();
        this.updateSemanticZoom(true);
      }
    }, 180);
  }

  renderZoneOverlay() {
    if (!this.network || !this.network.canvasToDOM) return;
    const host = this.overlayHost;
    if (!host) return;
    
    let overlay = host.querySelector('.term-zone-overlay');
    const bottomY = host.clientHeight > 100 ? host.clientHeight - 80 : 500;
    const topY = 70; // 顶部偏下的安全位置，加大偏移量以避开黑色导航栏
    const zoneDefs = this.getLayoutMode() === 'focus_orbit'
      ? [
          { key: 'factLane', title: '事实区', desc: '证据与事实上游', x: MAIN_LANE_X.factLane - 40, screenTop: topY },
          { key: 'elementLane', title: '法条元素区', desc: '法条构成要件', x: MAIN_LANE_X.elementLane, screenTop: topY },
          { key: 'focusCore', title: '争点核心', desc: 'DisputeFocus 中心', x: Math.round((MAIN_LANE_X.lawLane + MAIN_LANE_X.resultLane) / 2), screenTop: topY },
          { key: 'lawLane', title: '法条半环', desc: '法条与依据', x: MAIN_LANE_X.lawLane - 40, screenTop: topY },
          { key: 'resultLane', title: '裁判半环', desc: '裁判与结果', x: MAIN_LANE_X.resultLane, screenTop: topY },
        ]
      : [
          { key: 'caseLane', title: '案件区', desc: 'CourtCase 主轴', x: MAIN_LANE_X.caseLane, screenTop: topY },
          { key: 'subjectLane', title: '主体区', desc: '案件当事人', x: MAIN_LANE_X.subjectLane, screenTop: topY },
          { key: 'evidenceLane', title: '证据区', desc: '证据材料', x: MAIN_LANE_X.evidenceLane, screenTop: topY },
          { key: 'factLane', title: '事实区', desc: '案件事实', x: MAIN_LANE_X.factLane, screenTop: topY },
          { key: 'claimLane', title: '诉求区', desc: '程序意见与诉求', x: Math.round((MAIN_LANE_X.evidenceLane + MAIN_LANE_X.factLane) / 2), screenTop: bottomY },
          { key: 'elementLane', title: '法条元素区', desc: '法条构成要件', x: MAIN_LANE_X.elementLane, screenTop: topY },
          { key: 'lawLane', title: '法条区', desc: '法条依据', x: MAIN_LANE_X.lawLane, screenTop: topY },
          { key: 'resultLane', title: '裁判区', desc: '焦点与结果', x: MAIN_LANE_X.resultLane, screenTop: topY },
        ];

    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'term-zone-overlay';
      host.appendChild(overlay);
    }

    // Completely remove the optimization logic for now. 
    // If the elements exist but aren't showing, it might be because the browser 
    // thinks they are static or detached. Let's just forcibly recreate them and 
    // set absolute positions without relying on CSS class toggling for visibility.
    overlay.innerHTML = zoneDefs.map(zone => 
      `<div class="term-zone-badge" data-zone="${zone.key}" style="display:none;"><span class="term-zone-title">${zone.title}</span><span class="term-zone-desc">${zone.desc}</span></div>`
    ).join('');
    
    zoneDefs.forEach(zone => {
      const badge = overlay.querySelector(`[data-zone="${zone.key}"]`);
      if (!badge) return;
      const domPos = this.network.canvasToDOM({ x: zone.x, y: 0 });
      const top = zone.screenTop ?? 24; 
      
      const within = domPos && domPos.x > -1500 && domPos.x < (host.clientWidth + 1500);
      
      if (within) {
        badge.style.left = domPos.x + 'px';
        badge.style.top = `${top}px`;
        badge.style.display = 'inline-flex';
        badge.style.zIndex = '9999';
        // Force opacity to 1 bypassing any .zone-hidden CSS rules
        badge.style.opacity = '1';
        badge.classList.remove('zone-hidden');
      } else {
        badge.style.display = 'none';
      }
    });
  }


  focusNodesByType(typeKey) {
    if (!this.network || !typeKey) return;
    const nodes = this.nodesDs.get();
    const matchedNodes = nodes.filter(item => item.group === typeKey || item.nodeType === typeKey || item.label === typeKey);
    const targetIds = matchedNodes.map(n => n.id);
    
    if (targetIds.length > 0) {
      this.network.selectNodes(targetIds, false);
      
      // Dimming other nodes
      const updatedNodes = nodes.map(n => {
        const isMatch = targetIds.includes(n.id);
        return {
          id: n.id,
          color: isMatch ? undefined : { background: '#f1f5f9', border: '#e2e8f0' },
          font: { color: isMatch ? undefined : '#cbd5e1' }
        };
      });
      this.nodesDs.update(updatedNodes);
      
      const edges = this.edgesDs.get();
      const updatedEdges = edges.map(e => {
        const isMatch = targetIds.includes(e.from) || targetIds.includes(e.to);
        return {
          id: e.id,
          color: isMatch ? undefined : { color: '#e2e8f0' }
        };
      });
      this.edgesDs.update(updatedEdges);
      
      this.network.fit({
        nodes: targetIds,
        animation: { duration: 400, easingFunction: 'easeInOutQuad' },
        scale: 1.0
      });
    } else {
      this.clearTypeFocus();
    }
  }

  previewNodesByType(typeKey) {
    if (!this.network || !typeKey) return;
    // For hover effect, we can temporarily change the style of matched nodes
    // to make them pop out. 
    const matchedNodes = this.nodesDs.get({
      filter: (item) => {
        return item.group === typeKey || item.nodeType === typeKey || item.label === typeKey;
      }
    });
    
    if (matchedNodes.length > 0) {
      this.nodesDs.update(matchedNodes.map(n => ({
        id: n.id,
        borderWidth: 4,
        shadow: { enabled: true, size: 14, color: 'rgba(37,99,235,0.4)' }
      })));
    }
  }

  clearTypeFocus() {
    if (!this.network) return;
    this.network.unselectAll();
    const state = store.getState();
    if (state.parseGraphData) {
      this.syncRenderedGraph({ preservePositions: true });
    }
  }

  render(state) {
    const nextLayoutMode = state.parseGraphLayoutMode || 'lane';
    const layoutChanged = nextLayoutMode !== this.layoutMode;
    if (layoutChanged) {
      this.layoutMode = nextLayoutMode;
      this.syncToolButtonStates();
      if (state.parseGraphData) {
        this.syncRenderedGraph();
        this.apply2DLayout();
      }
      return;
    }

    if (state.parseGraphData && state.parseGraphData !== this.lastRenderedData) {
      this.lastRenderedData = state.parseGraphData;
      
      // Enable buttons
      if (this.btnGraphRegen) {
        this.btnGraphRegen.disabled = false;
        this.btnGraphRegen.style.display = 'inline-block';
      }
      if (this.btnResetLayout) {
        this.btnResetLayout.disabled = false;
        this.btnResetLayout.style.display = 'inline-block';
      }
      if (this.btnRelatedOnly) {
        this.btnRelatedOnly.disabled = false;
        this.btnRelatedOnly.style.display = 'inline-block';
      }
      
      this.viewMode = 'all';
      if (this.btnRelatedOnly) {
        this.btnRelatedOnly.textContent = '🎯 只看当前相关';
        this.btnRelatedOnly.classList.remove('active-filter');
      }

      this.updateView();
      this.syncToolButtonStates();
      this.lastMergeHighlight = state.parseMergeHighlight;
      this.lastPreviewPatch = state.parseEnhancementPreviewPatch;
      this.lastPreviewActive = state.parseEnhancementPreviewActive;
      this.scheduleRelayout({ fit: this.isMainView, delay: 40, preserveView: !this.isMainView });
      return;
    }

    const highlightChanged =
      state.parseMergeHighlight !== this.lastMergeHighlight
      || state.parseEnhancementPreviewPatch !== this.lastPreviewPatch
      || state.parseEnhancementPreviewActive !== this.lastPreviewActive;
    if (state.parseGraphData && highlightChanged) {
      this.lastMergeHighlight = state.parseMergeHighlight;
      this.lastPreviewPatch = state.parseEnhancementPreviewPatch;
      this.lastPreviewActive = state.parseEnhancementPreviewActive;
      this.renderAnalysisModeState(state);
      this.syncRenderedGraph({ preservePositions: true });
      this.scheduleRelayout({ fit: false, delay: 20, preserveView: true });
    }
  }
}
