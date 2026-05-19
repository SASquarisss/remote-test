import { Network } from 'vis-network';
import { store } from '../store/index.js';
import { TYPE_NAMES, ZH_LABELS } from '../data/schema.js';
import { getOntologyRelationEdges } from '../data/relationModel.js';
import { bindCustomPan } from '../utils/pan.js';

export class OntologyGraph {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.host = document.getElementById('ontologyNetworkHost') || this.container;
    this.network = null;
    this.relayoutTimer = null;
    this.resizeObserver = null;
    this.miniFrameDefaults = {
      top: '54px',
      left: '20px',
      width: '460px',
      height: '520px'
    };
    this.initializeFrameVars();
    const header = document.getElementById('ontologyHeader');
      if (header) {
        header.addEventListener('click', (e) => {
          const tab = e.target.closest('.onto-tab');
          if (tab) {
            header.querySelectorAll('.onto-tab').forEach(t => {
              t.classList.remove('active');
              t.style.borderBottomColor = 'transparent';
              t.style.color = '#94a3b8';
            });
            tab.classList.add('active');
            tab.style.borderBottomColor = '#3b82f6';
            tab.style.color = '#fff';
            
            const targetId = tab.getAttribute('data-target');
            const targetEl = targetId ? document.getElementById(targetId) : null;
            document.querySelectorAll('.onto-tab-content').forEach(c => c.style.display = 'none');
            if (targetEl) {
              targetEl.style.display = 'block';
            }
            this.scheduleRelayout({ fit: false, delay: 40 });
          }
        });
      }
      
      this.init();
    this.bindFloatingEvents();
    this.bindResizeObserver();
  }

  initializeFrameVars() {
    if (!this.container) return;
    this.container.style.setProperty('--workspace-terminal-height', '0px');
    this.container.style.setProperty('--ontology-mini-top', this.miniFrameDefaults.top);
    this.container.style.setProperty('--ontology-mini-left', this.miniFrameDefaults.left);
    this.container.style.setProperty('--ontology-mini-width', this.miniFrameDefaults.width);
    this.container.style.setProperty('--ontology-mini-height', this.miniFrameDefaults.height);
  }

  scheduleRelayout({ fit = false, delay = 80 } = {}) {
    if (!this.network) return;
    window.clearTimeout(this.relayoutTimer);
    this.relayoutTimer = window.setTimeout(() => {
      if (!this.network || this.container.style.display === 'none') return;
      this.network.setSize('100%', '100%');
      this.network.redraw();
      if (fit) {
        this.network.fit({ animation: true });
      }
    }, delay);
  }

  bindResizeObserver() {
    if (!this.container || typeof ResizeObserver === 'undefined') return;
    this.resizeObserver = new ResizeObserver(() => {
      if (!this.container.classList.contains('mini-mode')) return;
      const rect = this.container.getBoundingClientRect();
      this.container.style.setProperty('--ontology-mini-width', `${Math.round(rect.width)}px`);
      this.container.style.setProperty('--ontology-mini-height', `${Math.round(rect.height)}px`);
      this.scheduleRelayout({ fit: false, delay: 30 });
    });
    this.resizeObserver.observe(this.container);
  }

  init() {
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

    const nodes = TYPE_NAMES.map(name => {
      const style = defaultStyles[name] || { shape: 'dot', color: '#f8fafc', border: '#cbd5e1' };
      return { 
        id: name, 
        label: name,
        title: ZH_LABELS[name] || name,
        shape: style.shape,
        color: { background: style.color, border: style.border },
        font: { size: 12, color: name === 'LegalProvision' || name === 'Law' ? '#fff' : '#333' }
      };
    });
    
    const edges = getOntologyRelationEdges().map(edge => ({
      id: edge.id,
      from: edge.fromType,
      to: edge.toType,
      label: edge.label,
      relationType: edge.relationType,
      edgeSource: edge.source,
      description: edge.description,
      derivationKind: edge.derivationKind || '',
      arrows: 'to',
      dashes: edge.source === 'derived' ? [6, 4] : false,
      color: edge.source === 'derived' ? { color: '#6366f1' } : { color: '#94a3b8' },
      font: {
        size: 11,
        color: edge.source === 'derived' ? '#4338ca' : '#64748b',
        align: 'horizontal',
        strokeWidth: 2,
        strokeColor: '#ffffff'
      }
    }));
    
    const data = { nodes, edges };
    const options = {
      nodes: {
        shape: 'dot',
        size: 16,
        font: { size: 12, face: 'Arial' }
      },
      edges: {
        width: 1,
        color: { color: '#b3b3b3', highlight: '#3498db' },
        smooth: { type: 'continuous' },
        font: { size: 11, color: '#64748b', align: 'horizontal', strokeWidth: 2, strokeColor: '#ffffff' }
      },
      physics: {
        solver: 'barnesHut',
        barnesHut: {
          gravitationalConstant: -3000,
          centralGravity: 0.3,
          springLength: 120,
          springConstant: 0.04,
          damping: 0.5,
          avoidOverlap: 0.5
        },
        stabilization: {
          iterations: 400,
          updateInterval: 25,
          fit: true
        },
        maxVelocity: 50,
        minVelocity: 0.5
      },
      interaction: {
        hover: true,
        tooltipDelay: 100,
        navigationButtons: true,
        keyboard: true,
        zoomView: true,
        dragView: false
      }
    };
    
    this.network = new Network(this.host, data, options);
    this.ensureRelationLegend();

    // Support wheel zoom in mini-mode explicitly
    this.host.addEventListener('wheel', (e) => {
      if (this.container.classList.contains('mini-mode') && this.network) {
        e.preventDefault();
        const scale = this.network.getScale();
        const newScale = e.deltaY > 0 ? scale * 0.9 : scale * 1.1;
        this.network.moveTo({ scale: newScale });
      }
    }, { passive: false });
    
    this.network.on('stabilizationIterationsDone', () => {
      // 稳定后关闭物理引擎，防止持续浮动
      this.network.setOptions({ physics: { enabled: false } });
    });
    this.scheduleRelayout({ fit: true, delay: 40 });

    bindCustomPan(this.network, this.container);
    
    this.network.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        
        // Ensure state is updated, including triggering the locateTarget for the JSON view
        store.setState({
          selectedNodeId: nodeId,
          selectedEdgeId: null,
          selectedGraph: 'ontology',
          isPanelOpen: true,
          // Fire locateTarget to trigger TerminalPanel JSON highlight logic
          locateTarget: {
            sourceGraph: 'parse', // use 'parse' so TerminalPanel treats it as a JSON focus request
            typeKey: nodeId,
            timestamp: Date.now()
          }
        });
        
        // Auto-focus on clicked node
        this.network.focus(nodeId, {
          scale: 1.1,
          animation: { duration: 400, easingFunction: 'easeInOutQuad' }
        });
      } else if (params.edges.length > 0) {
        const edgeId = params.edges[0];
        const edge = this.network.body.data.edges.get(edgeId);
        store.setState({
          selectedNodeId: null,
          selectedEdgeId: edgeId,
          ontologyEdgeData: edge || null,
          selectedGraph: 'ontology',
          isPanelOpen: true
        });

        if (edge) {
          const fromNode = this.network.body.nodes[edge.from];
          const toNode = this.network.body.nodes[edge.to];
          if (fromNode && toNode) {
            const centerX = (fromNode.x + toNode.x) / 2;
            const centerY = (fromNode.y + toNode.y) / 2;
            this.network.moveTo({
              position: { x: centerX, y: centerY },
              scale: 1.1,
              animation: { duration: 400, easingFunction: 'easeInOutQuad' }
            });
          }
        }
      } else {
        store.setState({ isPanelOpen: false });
        this.network.unselectAll();
      }
    });

    this.network.on('hoverNode', (params) => {
      if (!params || !params.node) return;
      store.setState({ hoverOntologyType: params.node });
    });

    this.network.on('blurNode', () => {
      store.setState({ hoverOntologyType: null });
    });

    // Subscribe to store changes to reflect selections from ParseGraph or Issues
    store.subscribe((state) => {
      // Update node counts based on parseGraphData
      if (state.parseGraphData && state.parseGraphData.nodes) {
        const typeCounts = {};
        state.parseGraphData.nodes.forEach(n => {
          const type = n.nodeType || n.group;
          if (type) {
            typeCounts[type] = (typeCounts[type] || 0) + 1;
          }
        });
        
        const updatedNodes = this.network.body.data.nodes.get().map(n => {
          const count = typeCounts[n.id] || 0;
          return {
            id: n.id,
            label: count > 0 ? `${n.id} [${count}]` : n.id,
            font: { 
              size: 12, 
              color: n.id === 'LegalProvision' || n.id === 'Law' ? '#fff' : '#333',
              bold: count > 0 
            }
          };
        });
        this.network.body.data.nodes.update(updatedNodes);
      }

      if (state.selectedGraph === 'parse' && state.parseNodeData) {
        // When a node is selected in ParseGraph, highlight corresponding Ontology schema node
        const typeKey = state.parseNodeData.nodeType || state.parseNodeData.group;
        if (typeKey && this.network.body.data.nodes.get(typeKey)) {
          this.network.selectNodes([typeKey], false);
        }
      }
      
      // If a specific schema node is targeted from somewhere else
      if (state.selectedGraph === 'ontology' && state.selectedNodeId) {
        if (this.network.body.data.nodes.get(state.selectedNodeId)) {
          this.network.selectNodes([state.selectedNodeId], false);
        }
      }
    });
  }

  ensureRelationLegend() {
    if (!this.container || this.container.querySelector('.ontology-relation-legend')) return;
    const legend = document.createElement('div');
    legend.className = 'ontology-relation-legend';
    legend.innerHTML = `
      <span class="legend-item"><span class="legend-line solid"></span><span>本体原生关系</span></span>
      <span class="legend-item"><span class="legend-line dashed"></span><span>自动补图关系</span></span>
    `;
    this.container.appendChild(legend);
  }

  bindFloatingEvents() {
    const ohClose = document.getElementById('ohClose');
    if (ohClose) {
      ohClose.addEventListener('click', () => {
        this.container.style.display = 'none';
        store.setState({ isOntologyVisible: false });
      });
    }

    const ohToggleFull = document.getElementById('ohToggleFull');
    if (ohToggleFull) {
      ohToggleFull.addEventListener('click', () => {
        const isMini = this.container.classList.contains('mini-mode');
        if (isMini) {
          store.setState({
            workspaceLayoutMode: 'ontology_primary',
            isOntologyVisible: true
          });
        } else {
          store.setState({
            workspaceLayoutMode: store.getState().isParseResultAvailable ? 'parse_primary' : 'ontology_primary',
            isOntologyVisible: true
          });
        }
      });
    }

    const restoreFloatBtn = document.getElementById('ontologyRestoreFloat');
    if (restoreFloatBtn) {
      restoreFloatBtn.addEventListener('click', () => {
        store.setState({
          workspaceLayoutMode: store.getState().isParseResultAvailable ? 'parse_primary' : 'ontology_primary',
          isOntologyVisible: true
        });
      });
    }

    const header = document.getElementById('ontologyHeader');
    if (header) {
      let isDragging = false;
      let startX, startY, initialLeft, initialTop;

      header.addEventListener('mousedown', (e) => {
        if (!this.container.classList.contains('mini-mode')) return;
        if (e.target.closest('button') || e.target.closest('.onto-tab')) return;
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = this.container.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;

        const onMouseMove = (moveEvent) => {
          if (!isDragging) return;
          this.container.style.setProperty('--ontology-mini-left', `${initialLeft + moveEvent.clientX - startX}px`);
          this.container.style.setProperty('--ontology-mini-top', `${initialTop + moveEvent.clientY - startY}px`);
          this.scheduleRelayout({ fit: false, delay: 16 });
        };

        const onMouseUp = () => {
          isDragging = false;
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });
    }
  }

  setMiniMode() {
    this.container.style.display = 'block';
    this.container.classList.add('mini-mode');
    this.container.classList.remove('main-mode');
    
    const header = document.getElementById('ontologyHeader');
    if (header) {
      header.style.display = 'flex';
    }
    
    this.scheduleRelayout({ fit: true, delay: 120 });
  }

  setMainMode() {
    const state = store.getState();
    const terminalHeight = state.terminalCollapsed ? 40 : (state.terminalHeightPx || 0);
    this.container.style.display = 'block';
    this.container.classList.remove('mini-mode');
    this.container.classList.add('main-mode');
    this.container.style.setProperty('--workspace-terminal-height', `${terminalHeight}px`);
    
    const header = document.getElementById('ontologyHeader');
    if (header) {
      header.style.display = 'none';
    }
    
    this.scheduleRelayout({ fit: true, delay: 120 });
  }
}
