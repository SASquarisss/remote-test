import { Store, store } from './store/index.js';
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
  const parseGraph = new ParseGraph('termVisCanvasHost');
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

  // Handle cross-component layout coordination via store
  store.subscribe((state) => {
    // When parse result is available, ParseGraph goes to main view, Ontology goes to mini-mode
    if (state.isParseResultAvailable) {
      parseGraph.mountToMainView();
      ontologyGraph.setMiniMode();
      store.setState({ isOntologyVisible: true });
    }
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
        
        store.setState({ 
          parseGraphData: result,
          selectedGraph: 'parse',
          isParseResultAvailable: true,
          activeTab: targetTab
        });
        
        terminalPanel.switchTab(targetTab);
        terminalPanel.handleQualityAnalysis(result.json_result);
        
        if (data.term_eval_result) {
          // Hydrate eval result if it exists
          terminalPanel.renderEvalResult(data.term_eval_result);
        }
        
        terminalPanel.setStatus('测试数据已加载（含上次解析结果）', '#27ae60');
        terminalPanel.ensureTerminalExpanded();
      }
    }
  }).catch(err => console.warn('加载测试数据失败:', err));
  
  console.log('Ontology Refactored App Initialized.');
});
