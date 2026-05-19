import { store } from './store/index.js';
import { OntologyGraph } from './components/OntologyGraph.js';
import { ParseGraph } from './components/ParseGraph.js';
import { DetailPanel } from './components/DetailPanel.js';
import { TerminalPanel } from './components/TerminalPanel.js';
import { TopNavBar } from './components/TopNavBar.js';
import { OntologyLegend } from './components/OntologyLegend.js';
import { ControlsPanel } from './components/ControlsPanel.js';
import { loadTestData } from './api/backend.js';

document.addEventListener('DOMContentLoaded', () => {
  const topNavBar = new TopNavBar();
  const ontologyLegend = new OntologyLegend();
  const ontologyGraph = new OntologyGraph('ontologyContainer');
  const controlsPanel = new ControlsPanel(ontologyGraph.network);
  const parseGraph = new ParseGraph('parseGraphCanvasHost');
  const detailPanel = new DetailPanel();
  const terminalPanel = new TerminalPanel();
  
  // Initialize graph tools inside the terminal tab
  parseGraph.initGraphTools();
  
  // Initialize top bar counts
  setTimeout(() => {
    if (ontologyGraph.network) {
      const nodesCount = ontologyGraph.network.body.data.nodes.length;
      const edgesCount = ontologyGraph.network.body.data.edges.length;
      topNavBar.updateStats(nodesCount, edgesCount);
    }
  }, 1000);

  let lastLayoutSignature = '';

  const getTerminalHeight = (state) => {
    if (state.terminalCollapsed) return 40;
    if (typeof state.terminalHeightPx === 'number' && state.terminalHeightPx > 0) {
      return state.terminalHeightPx;
    }
    return terminalPanel.panel?.offsetHeight || Math.round(window.innerHeight * 0.5);
  };

  const applyWorkspaceLayout = (state) => {
    const hasParseResult = Boolean(state.isParseResultAvailable && state.parseGraphData);
    const layoutMode = hasParseResult ? (state.workspaceLayoutMode || 'parse_primary') : 'ontology_primary';
    const signature = [
      layoutMode,
      hasParseResult ? 'parse' : 'empty',
      state.terminalCollapsed ? 'collapsed' : 'expanded',
      state.isOntologyVisible === false ? 'ontology-hidden' : 'ontology-visible',
      getTerminalHeight(state)
    ].join('|');

    if (signature === lastLayoutSignature) return;
    lastLayoutSignature = signature;

    const mainView = document.getElementById('kgMainView');
    const ontologyContainer = document.getElementById('ontologyContainer');
    if (mainView) {
      mainView.style.height = `calc(100vh - ${getTerminalHeight(state)}px)`;
    }

    if (layoutMode === 'parse_primary') {
      parseGraph.mountToMainView();
      ontologyGraph.setMiniMode();
      if (ontologyContainer) {
        ontologyContainer.style.display = state.isOntologyVisible === false ? 'none' : 'block';
      }
      return;
    }

    parseGraph.mountToTerminal();
    ontologyGraph.setMainMode();
    if (ontologyContainer) {
      ontologyContainer.style.display = 'block';
    }
  };

  store.subscribe((state) => {
    applyWorkspaceLayout(state);
  });

  window.addEventListener('resize', () => {
    lastLayoutSignature = '';
    applyWorkspaceLayout(store.getState());
  });

  // Fetch initial test data to simulate state hydration
  loadTestData().then(data => {
    if (data) {
      const ta = terminalPanel.inputArea || document.getElementById('termInputArea');
      if (ta && data.text) {
        ta.value = data.text;
      }
      
      if (data.json_result) {
        const result = {
          json_result: data.json_result,
          nodes: data.nodes || [],
          edges: data.edges || [],
          score: data.score || 0,
          issues: data.issues || [],
          row_id: data.row_id || null,
          case_name: data.case_name || '',
        };
        
        // Inject to terminal and graph
        terminalPanel.lastResult = result;
        terminalPanel.renderJson(result.json_result);
        if (terminalPanel.evalBtn) terminalPanel.evalBtn.disabled = false;
        if (terminalPanel.saveBtn) terminalPanel.saveBtn.disabled = false;
        if (terminalPanel.saveBtnBottom) terminalPanel.saveBtnBottom.disabled = false;
        let targetTab = 'termVisContainer';
        if (data.active_tab === 'eval') targetTab = 'termEvalTabContent';
        else if (data.active_tab === 'issues') targetTab = 'termIssuesTabContent';
        else if (data.active_tab === 'enhance') targetTab = 'termEnhanceTabContent';
        
        store.setState({ 
          parseGraphData: result,
          selectedGraph: 'parse',
          isParseResultAvailable: true,
          workspaceLayoutMode: 'parse_primary',
          isOntologyVisible: true,
          activeTab: targetTab
        });
        
        terminalPanel.switchTab(targetTab);
        if (data.term_quality_result) {
          terminalPanel.lastQualityResult = data.term_quality_result;
          terminalPanel.renderQualityIssues(data.term_quality_result, store.getState().parseNodeData);
        } else {
          terminalPanel.handleQualityAnalysis(result.json_result);
        }
        
        if (data.term_eval_result) {
          // Hydrate eval result if it exists
          terminalPanel.renderEvalResult(data.term_eval_result);
        }

        if (data.term_enhancement_result) {
          terminalPanel.renderEnhancementResult(data.term_enhancement_result);
        }
        
        terminalPanel.setStatus('测试数据已加载（含上次解析结果）', '#27ae60');
        terminalPanel.ensureTerminalExpanded();
      }
    }
  }).catch(err => console.warn('加载测试数据失败:', err));

  applyWorkspaceLayout(store.getState());
  
  console.log('legal_ontology_workspace initialized.');
});
