import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { store } from '../store/index.js';
import { bindCustomPan } from '../utils/pan.js';

const ZONE_MAP = {
  Evidence: 'left',
  Fact: 'leftDetail',
  DisputeFocus: 'centerDetail',
  CourtCase: 'core',
  GuidingCase: 'core',
  CaseType: 'core',
  CaseSummary: 'centerDetail',
  JudgmentResult: 'rightDetail',
  Judge: 'right',
  Attorney: 'right',
  LegalRole: 'right',
  Person: 'right',
  LegalSubject: 'right',
  LegalProvision: 'bottom',
  Law: 'bottom',
  LegalNorm: 'bottom',
};

const Y_LEVEL_MAP = {
  CourtCase: 1, GuidingCase: 0, CaseType: 0, CaseSummary: 1,
  JudgmentResult: 1, Evidence: 0, Fact: 1, DisputeFocus: 1,
  Judge: 0, Attorney: 1, LegalRole: 1, Person: 0,
  LegalSubject: 0, LegalProvision: 0, Law: 0, LegalNorm: 0,
};

const ZONE_X_OFFSET = {
  left: -760, leftDetail: -440, core: 0, center: 0,
  centerDetail: 0, right: 760, rightDetail: 460, bottom: 0,
};

const ZONE_SPACING = {
  left: 220, leftDetail: 240, core: 210, center: 230,
  centerDetail: 280, right: 220, rightDetail: 260, bottom: 250
};

const ZONE_Y_BASE = {
  left: 70, leftDetail: 300, core: 80, center: 90,
  centerDetail: 360, right: 90, rightDetail: 340, bottom: 710
};

export class ParseGraph {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.network = null;
    this.nodesDs = new DataSet();
    this.edgesDs = new DataSet();
    this.overlayHost = this.container;
    this.viewMode = 'all';
    this.lastRenderedData = null;
    this.needsLayout = false;
    this.init();
  }

  mountToMainView() {
    const mainView = document.getElementById('kgMainView');
    if (!mainView) return;
    
    // Move the entire container to the main view so vis.js coordinate math works correctly
    if (this.network && this.network.canvas && !this.isMainView) {
      mainView.appendChild(this.container);
      this.isMainView = true;
      
      // Force height adjustment based on terminal state
      const terminal = document.getElementById('parseTerminal');
      if (terminal && !terminal.classList.contains('collapsed')) {
        const termHeight = terminal.offsetHeight;
        mainView.style.height = `calc(100vh - ${termHeight}px)`;
      } else {
        mainView.style.height = 'calc(100vh - 36px)';
      }
      
      setTimeout(() => {
        this.network.setSize('100%', '100%');
        this.network.fit({ animation: true });
      }, 100);
    }
  }

  mountToTerminal() {
    const termVisContainer = document.getElementById('termVisContainer');
    if (!termVisContainer) return;
    
    // Move the container back to terminal
    if (this.network && this.network.canvas) {
      termVisContainer.appendChild(this.container);
      this.isMainView = false;
      setTimeout(() => {
        this.network.setSize('100%', '100%');
        this.network.fit({ animation: true });
      }, 100);
    }
  }

  init() {
    if (!this.container) return;
    
    const options = {
      physics: { enabled: false },
      interaction: { hover: true, tooltipDelay: 100, navigationButtons: true, keyboard: true, zoomView: false, dragView: false, dragNodes: true },
      edges: { smooth: { type: 'curvedCW', roundness: 0.1 }, font: { size: 9, color: '#64748b' }, selectionWidth: 2.2 },
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
        
        store.setState({
          selectedNodeId: nodeId,
          selectedEdgeId: null,
          selectedGraph: 'parse',
          isPanelOpen: true,
          parseNodeData: this.nodesDs.get(nodeId)
        });
        
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
      this.zoomTimeout = setTimeout(() => this.renderZoneOverlay(), 16);
    });

    // Native zoom and pan will work now that we reparent this.container instead of just the canvas.frame.
    // Ensure we trigger overlay render on drag.
    this.network.on('dragging', () => this.renderZoneOverlay());

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
      setTimeout(() => this.renderZoneOverlay(), 0);
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
          <button id="btnSmartLayout" class="tool-btn"><span class="icon">✨</span> 智能语义排版</button>
          <button id="btnPlayback" class="tool-btn"><span class="icon">▶</span> 逻辑动态回放</button>
          <button id="btnXRay" class="tool-btn"><span class="icon">🩻</span> 异常断链审查</button>
          <button id="btnRestoreGraph" class="tool-btn" style="grid-column: span 2; justify-content: center; background: #f8fafc; color: #64748b; border-color: #cbd5e1;"><span class="icon">↺</span> 恢复初始状态</button>
        </div>
        <div class="graph-tools-desc" id="graphToolDesc">请选择上方的分析模式。这些工具可以帮助你过滤冗余信息、检查逻辑断裂或一键排版案件结构。</div>
      `;
      termGraphInfo.appendChild(toolbar);
      
      const updateDesc = (text) => {
        const desc = toolbar.querySelector('#graphToolDesc');
        if (desc) desc.textContent = text;
      };

      toolbar.querySelector('#btnSubgraph').addEventListener('click', () => {
        this.toggleSubgraphMode();
        updateDesc(this.subgraphMode ? '已开启核心子图透视：隐藏边缘节点，仅显示 证据 -> 事实 -> 焦点 -> 法条 的骨架链路。' : '已恢复全量图谱显示。');
      });
      toolbar.querySelector('#btnSmartLayout').addEventListener('click', () => {
        this.applySmartLayout();
        updateDesc('已应用智能语义排版：事实纵向排列，焦点沉底，当事人分布四周。');
      });
      toolbar.querySelector('#btnPlayback').addEventListener('click', () => {
        this.togglePlayback();
        updateDesc(this.playbackInterval ? '正在播放逻辑推导动画：按照 证据->事实->焦点->法条 顺序点亮。' : '逻辑回放已停止。');
      });
      toolbar.querySelector('#btnXRay').addEventListener('click', () => {
        this.toggleXRayMode();
        updateDesc(this.xrayMode ? '已开启 X 光审查：红色虚线高亮显示孤立节点、无证据事实和断链的争议焦点。' : '已关闭 X 光审查模式。');
      });
      toolbar.querySelector('#btnRestoreGraph').addEventListener('click', () => {
        this.subgraphMode = false;
        this.xrayMode = false;
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
        
        setTimeout(() => {
          this.network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
        }, 100);
        updateDesc('已恢复图谱的初始完整状态和默认排版。');
      });
    }
  }

  toggleSubgraphMode() {
    this.subgraphMode = !this.subgraphMode;
    const btn = document.getElementById('btnSubgraph');
    if (this.subgraphMode) {
      btn.classList.add('active');
      btn.style.background = '#3b82f6'; btn.style.color = 'white';
      const coreTypes = ['Evidence', 'Fact', 'DisputeFocus', 'LegalProvision', 'JudgmentResult', 'CaseSummary'];
      const nodes = this.nodesDs.get();
      const updates = nodes.map(n => {
        const type = n.nodeType || n.group;
        return { id: n.id, hidden: !coreTypes.includes(type) };
      });
      this.nodesDs.update(updates);
      this.network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
    } else {
      btn.classList.remove('active');
      btn.style.background = ''; btn.style.color = '';
      const nodes = this.nodesDs.get();
      this.nodesDs.update(nodes.map(n => ({ id: n.id, hidden: false })));
      this.network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
    }
  }

  applySmartLayout() {
    const nodes = this.nodesDs.get();
    const edges = this.edgesDs.get();
    const updates = [];
    
    const facts = nodes.filter(n => (n.nodeType || n.group) === 'Fact');
    const courts = nodes.filter(n => (n.nodeType || n.group) === 'CourtCase');
    const subjects = nodes.filter(n => (n.nodeType || n.group) === 'LegalSubject' || (n.nodeType || n.group) === 'Person');
    const provisions = nodes.filter(n => (n.nodeType || n.group) === 'LegalProvision');
    const evidences = nodes.filter(n => (n.nodeType || n.group) === 'Evidence');
    const disputeFocuses = nodes.filter(n => (n.nodeType || n.group) === 'DisputeFocus');
    const others = nodes.filter(n => !['Fact', 'CourtCase', 'LegalSubject', 'Person', 'LegalProvision', 'Evidence', 'DisputeFocus'].includes(n.nodeType || n.group));

    // Vertical Fact backbone
    facts.forEach((n, i) => {
      updates.push({ id: n.id, x: 0, y: i * 150 });
    });

    // Courts at top
    courts.forEach((n, i) => {
      updates.push({ id: n.id, x: (i - (courts.length-1)/2) * 300, y: -200 });
    });

    // Dispute Focuses near bottom center
    const focusStartY = facts.length * 150 + 50;
    disputeFocuses.forEach((n, i) => {
      updates.push({ id: n.id, x: (i - (disputeFocuses.length-1)/2) * 250, y: focusStartY });
    });

    // Provisions at very bottom
    const provStartY = focusStartY + 150;
    provisions.forEach((n, i) => {
      updates.push({ id: n.id, x: (i - (provisions.length-1)/2) * 250, y: provStartY });
    });

    // Subjects at corners
    const corners = [[-800, -200], [800, -200], [-800, provStartY], [800, provStartY]];
    subjects.forEach((n, i) => {
      const corner = corners[i % 4];
      updates.push({ id: n.id, x: corner[0], y: corner[1] + Math.floor(i/4)*120 });
    });

    // Evidence on left side, aligned with facts if possible
    evidences.forEach((n, i) => {
      updates.push({ id: n.id, x: -450, y: i * 100 });
    });

    // Others on right side
    others.forEach((n, i) => {
      updates.push({ id: n.id, x: 450, y: i * 100 });
    });

    this.nodesDs.update(updates);
    this.network.fit({ animation: { duration: 800, easingFunction: 'easeInOutQuad' } });
    
    // Highlight CourtCase diff edges if multiple courts
    if (courts.length > 1) {
      const courtIds = courts.map(c => c.id);
      const edgeUpdates = edges.map(e => {
        if (courtIds.includes(e.from) || courtIds.includes(e.to)) {
          return { id: e.id, color: { color: '#10b981', highlight: '#059669' }, width: 3, dashes: true };
        }
        return { id: e.id };
      });
      this.edgesDs.update(edgeUpdates);
    }
  }

  togglePlayback() {
    if (this.playbackInterval) {
      clearInterval(this.playbackInterval);
      this.playbackInterval = null;
      const btn = document.getElementById('btnPlayback');
      if (btn) {
        btn.textContent = '▶ 逻辑回放';
        btn.style.background = ''; btn.style.color = '';
      }
      this.clearTypeFocus();
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
      btn.style.background = '#e74c3c'; btn.style.color = 'white';
    }
    
    this.playbackInterval = setInterval(() => {
      if (currentStep >= steps.length) {
        clearInterval(this.playbackInterval);
        this.playbackInterval = null;
        if (btn) {
          btn.textContent = '▶ 逻辑回放';
          btn.style.background = ''; btn.style.color = '';
        }
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
    const btn = document.getElementById('btnXRay');
    if (this.xrayMode) {
      btn.classList.add('active');
      btn.style.background = '#8e44ad'; btn.style.color = 'white';
      
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
      btn.classList.remove('active');
      btn.style.background = ''; btn.style.color = '';
      this.clearTypeFocus();
    }
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
      return {
        id: n.id,
        color: isMatch ? undefined : { background: 'rgba(241, 245, 249, 0.3)', border: 'rgba(226, 232, 240, 0.3)' },
        font: { color: isMatch ? undefined : 'rgba(203, 213, 225, 0.3)' }
      };
    });
    
    const updatedEdges = edges.map(e => {
      const isMatch = connectedEdges.includes(e.id);
      return {
        id: e.id,
        color: isMatch ? { color: '#3b82f6', highlight: '#2563eb' } : { color: 'rgba(226, 232, 240, 0.2)' },
        width: isMatch ? 3 : 1,
        font: isMatch ? { size: 12, color: '#2563eb', strokeWidth: 3, strokeColor: '#ffffff' } : { size: 9, color: 'rgba(203, 213, 225, 0.3)' }
      };
    });
    
    this.nodesDs.update(updatedNodes);
    this.edgesDs.update(updatedEdges);
  }

  clearNeighborHighlight() {
    if (!this.network) return;
    const state = store.getState();
    if (state.parseGraphData && !state.selectedNodeId) {
      // Restore styles from store
      this.nodesDs.update(this.styleNodes(state.parseGraphData.nodes));
      this.edgesDs.update(state.parseGraphData.edges.map(e => ({ 
        id: e.id, 
        color: undefined, 
        width: undefined, 
        font: undefined 
      })));
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

    const { nodes = [], edges = [] } = this.lastRenderedData;
    let filteredNodes = nodes;
    let filteredEdges = edges;
    const state = store.getState();

    if (this.viewMode === 'related' && state.selectedNodeId) {
      const focusNodeId = state.selectedNodeId;
      const focusEdgeIds = new Set();
      const focusNodeIds = new Set([focusNodeId]);
      
      edges.forEach(e => {
        if (e.from === focusNodeId || e.to === focusNodeId) {
          focusEdgeIds.add(e.id);
          focusNodeIds.add(e.from);
          focusNodeIds.add(e.to);
        }
      });
      
      filteredNodes = nodes.filter(n => focusNodeIds.has(n.id));
      filteredEdges = edges.filter(e => focusEdgeIds.has(e.id));
    }

    if (this.viewMode === 'related') {
      this.nodesDs.clear();
      this.nodesDs.add(this.styleNodes(filteredNodes));
      this.edgesDs.clear();
      this.edgesDs.add(filteredEdges);
      this.apply2DLayout();
    } else {
      this.nodesDs.clear();
      this.nodesDs.add(this.styleNodes(nodes));
      this.edgesDs.clear();
      this.edgesDs.add(edges);
      this.apply2DLayout();
    }
  }

  styleNodes(nodes) {
    const defaultStyles = {
      CourtCase:  { shape: 'box', color: '#FFA07A', border: '#E8875A' },
      Person:     { shape: 'square', color: '#90EE90', border: '#6BCE6B' },
      LegalProvision: { shape: 'hexagon', color: '#483D8B', border: '#3A2D6E' },
      Law:        { shape: 'hexagon', color: '#483D8B', border: '#3A2D6E' },
      Evidence:   { shape: 'database', color: '#CD853F', border: '#A06B32' },
      LegalRole:  { shape: 'diamond', color: '#FFA500', border: '#CC8400' },
      CaseSummary: { shape: 'star', color: '#32CD32', border: '#28A428' },
      LegalSubject: { shape: 'triangle', color: '#B0C4DE', border: '#8DA3B8' },
      LegalNorm:  { shape: 'triangle', color: '#B0C4DE', border: '#8DA3B8' },
      GuidingCase:  { shape: 'star', color: '#4682B4', border: '#35608C' },
    };

    return nodes.map(n => {
      const type = n.nodeType || n.group || '';
      const style = defaultStyles[type] || { shape: 'box', color: '#f8fafc', border: '#cbd5e1' };
      
      return {
        ...n,
        label: n.label || n.title || n.id,
        nodeType: type,
        shape: style.shape,
        color: { background: style.color, border: style.border },
        font: { size: 12, color: type === 'LegalProvision' || type === 'Law' ? '#fff' : '#333' }
      };
    });
  }

  applyClustering() {
    if (!this.network) return;
    const nodes = this.nodesDs.get();
    const clusterTypes = ['Judge', 'Attorney', 'Evidence', 'LegalProvision'];
    clusterTypes.forEach(type => {
      const count = nodes.filter(n => (n.nodeType || n.group) === type).length;
      if (count >= 3) {
        try {
          this.network.cluster({
            joinCondition: function(nodeOpts) {
              return nodeOpts.nodeType === type || nodeOpts.group === type;
            },
            clusterNodeProperties: {
              id: 'cluster_' + type,
              label: `${type}组 (${count})`,
              shape: 'box',
              color: { background: '#94a3b8', border: '#64748b' },
              font: { size: 12, color: '#fff' },
              title: '双击展开查看详情',
            },
            processProperties: function(clusterProps, childNodes) {
              return clusterProps;
            }
          });
        } catch(e) {
          console.warn(`聚类失败 [${type}]:`, e);
        }
      }
    });
  }

  apply2DLayout() {
    const nodes = this.nodesDs.get();
    const zoneBuckets = {};
    
    nodes.forEach(n => {
      const zone = ZONE_MAP[n.nodeType] || 'center';
      const yLvl = Y_LEVEL_MAP[n.nodeType] !== undefined ? Y_LEVEL_MAP[n.nodeType] : 2;
      const key = `${zone}|${yLvl}`;
      if (!zoneBuckets[key]) zoneBuckets[key] = [];
      zoneBuckets[key].push(n);
    });

    const updatedPositions = [];
    nodes.forEach(n => {
      const zone = ZONE_MAP[n.nodeType] || 'centerDetail';
      const yLvl = Y_LEVEL_MAP[n.nodeType] !== undefined ? Y_LEVEL_MAP[n.nodeType] : 2;
      const xBase = ZONE_X_OFFSET[zone] || 0;
      const yBase = (ZONE_Y_BASE[zone] || 90) + yLvl * (zone === 'bottom' ? 110 : 125);

      const key = `${zone}|${yLvl}`;
      const bucket = zoneBuckets[key] || [];
      const idx = bucket.indexOf(n);
      const bucketSize = bucket.length;
      const spacing = ZONE_SPACING[zone] || 240;
      const startX = xBase - (bucketSize - 1) * spacing / 2;
      const targetX = startX + idx * spacing;

      updatedPositions.push({ id: n.id, x: targetX, y: yBase });
    });
    
    this.nodesDs.update(updatedPositions);

    this.applyClustering();

    this.network.fit({ animation: true, minZoomLevel: 0.76, maxZoomLevel: 1.18 });
    setTimeout(() => {
      if (this.network) {
        this.network.moveTo({ scale: 0.9, animation: { duration: 220, easingFunction: 'easeInOutQuad' } });
        this.renderZoneOverlay();
      }
    }, 180);
  }

  renderZoneOverlay() {
    if (!this.network || !this.network.canvasToDOM) return;
    const host = this.overlayHost;
    if (!host) return;
    
    let overlay = host.querySelector('.term-zone-overlay');
    const zoneDefs = [
      { key: 'left', title: '证据区', desc: '证据材料', x: -760, y: 34 },
      { key: 'leftDetail', title: '事实区', desc: '案件事实', x: -440, y: 260 },
      { key: 'core', title: '案件核心', desc: '案件与主轴', x: 0, y: 30 },
      { key: 'right', title: '主体角色', desc: '人物与主体', x: 760, y: 36 },
      { key: 'rightDetail', title: '裁判结果', desc: '结果与摘要', x: 460, y: 290 },
      { key: 'bottom', title: '法条依据', desc: '规范支撑', x: 0, y: 640 }
    ];

    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'term-zone-overlay';
      overlay.innerHTML = zoneDefs.map(zone => 
        `<div class="term-zone-badge" data-zone="${zone.key}"><span class="term-zone-title">${zone.title}</span><span class="term-zone-desc">${zone.desc}</span></div>`
      ).join('');
      host.appendChild(overlay);
    }
    
    zoneDefs.forEach(zone => {
      const badge = overlay.querySelector(`[data-zone="${zone.key}"]`);
      if (!badge) return;
      const domPos = this.network.canvasToDOM({ x: zone.x, y: zone.y });
      const within = domPos && domPos.x >= 32 && domPos.x <= (host.clientWidth - 32) && domPos.y >= 28 && domPos.y <= (host.clientHeight - 28);
      badge.classList.toggle('zone-hidden', !within);
      if (within) {
        badge.style.left = domPos.x + 'px';
        badge.style.top = domPos.y + 'px';
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
    // Restore styles by re-styling nodes and edges from store data
    const state = store.getState();
    if (state.parseGraphData) {
      this.nodesDs.update(this.styleNodes(state.parseGraphData.nodes));
      this.edgesDs.update(state.parseGraphData.edges.map(e => ({ id: e.id, color: undefined })));
    }
  }

  render(state) {
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
    }
  }
}
