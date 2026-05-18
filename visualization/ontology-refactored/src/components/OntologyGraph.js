import { Network } from 'vis-network';
import { store } from '../store/index.js';
import { TYPE_NAMES, RELATION_EDGES, ZH_LABELS } from '../data/schema.js';
import { bindCustomPan } from '../utils/pan.js';

export class OntologyGraph {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.host = document.getElementById('ontologyNetworkHost') || this.container;
    this.network = null;
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
            document.querySelectorAll('.onto-tab-content').forEach(c => c.style.display = 'none');
            document.getElementById(targetId).style.display = 'block';
          }
        });
      }
      
      this.init();
    this.bindFloatingEvents();
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
    
    const edges = RELATION_EDGES.map((e, idx) => ({ 
      id: `edge_${idx}`,
      from: e[1], 
      to: e[2], 
      label: e[0],
      arrows: 'to',
      color: { color: '#94a3b8' }
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
        smooth: { type: 'continuous' }
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
        store.setState({
          selectedNodeId: null,
          selectedEdgeId: edgeId,
          selectedGraph: 'ontology',
          isPanelOpen: true
        });
        
        const edge = this.network.body.data.edges.get(edgeId);
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

    let lastLocateTarget = null;
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
          this.setMainMode();
        } else {
          this.setMiniMode();
        }
      });
    }

    const header = document.getElementById('ontologyHeader');
    if (header) {
      let isDragging = false;
      let startX, startY, initialLeft, initialTop;

      header.addEventListener('mousedown', (e) => {
        if (e.target.closest('button')) return;
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = this.container.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;

        const onMouseMove = (moveEvent) => {
          if (!isDragging) return;
          this.container.style.left = `${initialLeft + moveEvent.clientX - startX}px`;
          this.container.style.top = `${initialTop + moveEvent.clientY - startY}px`;
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
    this.container.classList.add('mini-mode');
    this.container.style.width = '460px';
    this.container.style.height = '520px';
    this.container.style.top = '54px';
    this.container.style.left = '20px';
    this.container.style.zIndex = '998';
    this.container.style.boxShadow = '0 10px 30px rgba(0,0,0,0.3)';
    this.container.style.borderRadius = '8px';
    this.container.style.border = '1px solid #334155';
    this.container.style.overflow = 'hidden';
    this.container.style.backgroundColor = '#ffffff'; // remove transparent gaps
    
    const header = document.getElementById('ontologyHeader');
    if (header) {
      header.style.display = 'flex';
    }
    
    this.host.style.height = 'calc(100% - 35px)'; // Adjust for header
    setTimeout(() => this.network.fit({ animation: true }), 350); // Wait for CSS transition
  }

  setMainMode() {
    this.container.classList.remove('mini-mode');
    this.container.style.width = '100%';
    this.container.style.height = '100vh';
    this.container.style.top = '0';
    this.container.style.left = '0';
    this.container.style.zIndex = '2';
    this.container.style.boxShadow = 'none';
    this.container.style.borderRadius = '0';
    this.container.style.border = 'none';
    this.container.style.backgroundColor = 'transparent';
    
    const header = document.getElementById('ontologyHeader');
    if (header) {
      header.style.display = 'none';
    }
    
    this.host.style.height = '100%';
    setTimeout(() => this.network.fit({ animation: true }), 350);
  }
}
