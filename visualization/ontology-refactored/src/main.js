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
        const hydratedVersions = Array.isArray(data.parse_versions) ? data.parse_versions : [];
        const activeVersionId = data.active_version_id || (hydratedVersions[hydratedVersions.length - 1] || {}).version_id || 'v0';
        const activeVersion = hydratedVersions.find((item) => item?.version_id === activeVersionId) || null;
        const topLevelJsonResult = data.json_result || {};
        const versionJsonResult = activeVersion?.json_result || {};
        const watchedKeys = ['litigation_claims', 'procedural_opinions', 'argument_points', 'judicial_assessments'];
        const countPopulatedKeys = (payload) => watchedKeys.reduce((sum, key) => {
          const value = payload?.[key];
          return sum + ((Array.isArray(value) && value.length > 0) ? 1 : 0);
        }, 0);
        const shouldPreferTopLevel =
          !activeVersion
          || countPopulatedKeys(topLevelJsonResult) > countPopulatedKeys(versionJsonResult);
        const effectiveVersions = shouldPreferTopLevel
          ? [{
              version_id: data.active_version_id || 'v0',
              label: '当前缓存',
              version_type: 'hydrated',
              source_run_id: null,
              created_at: '',
              change_summary: {},
              highlight_patch: data.term_merge_highlight || null,
              json_result: topLevelJsonResult,
              nodes: data.nodes || [],
              edges: data.edges || [],
            }]
          : hydratedVersions;
        const effectiveActiveVersionId = shouldPreferTopLevel
          ? (effectiveVersions[0]?.version_id || 'v0')
          : activeVersionId;
        const effectiveVersion = shouldPreferTopLevel
          ? effectiveVersions[0]
          : activeVersion;
        const result = {
          json_result: effectiveVersion?.json_result || topLevelJsonResult,
          nodes: effectiveVersion?.nodes || data.nodes || [],
          edges: effectiveVersion?.edges || data.edges || [],
          score: data.score || 0,
          issues: data.issues || [],
          row_id: data.row_id || null,
          case_name: data.case_name || '',
          text_chunks: data.text_chunks || [],
          source_alignment: data.source_alignment || {},
          chunking_meta: data.chunking_meta || null,
          alignment_stats: data.alignment_stats || null,
          alignment_unmatched_items: data.alignment_unmatched_items || [],
        };
        
        // Inject to terminal and graph
        terminalPanel.lastResult = result;
        terminalPanel.renderJson(result.json_result);
        if (terminalPanel.evalBtn) terminalPanel.evalBtn.disabled = false;
        if (terminalPanel.saveBtn) terminalPanel.saveBtn.disabled = false;
        if (terminalPanel.saveBtnBottom) terminalPanel.saveBtnBottom.disabled = false;
        if (terminalPanel.neo4jWriteBtnBottom) terminalPanel.neo4jWriteBtnBottom.disabled = false;
        let targetTab = 'termVisContainer';
        if (data.active_tab === 'eval') targetTab = 'termEvalTabContent';
        else if (data.active_tab === 'issues') targetTab = 'termIssuesTabContent';
        else if (data.active_tab === 'enhance') targetTab = 'termEnhanceTabContent';
        else if (data.active_tab === 'retrieval') targetTab = 'termRetrievalTabContent';
        
        store.setState({ 
          parseGraphData: result,
          selectedGraph: 'parse',
          isParseResultAvailable: true,
          workspaceLayoutMode: 'parse_primary',
          isOntologyVisible: true,
          activeTab: targetTab,
          parseVersions: effectiveVersions,
          parseActiveVersionId: effectiveActiveVersionId,
          parseEnhancementRuns: data.term_enhancement_runs || [],
          parseMergeHighlight: effectiveVersion?.highlight_patch || data.term_merge_highlight || null,
          parseEnhancementPreviewActive: false,
          parseEnhancementPreviewRunId: null,
          parseEnhancementPreviewPatch: null,
          retrievalBundle: data.retrieval_bundle || null,
          retrievalEntries: (data.retrieval_bundle?.entries || []),
          retrievalActiveEntryId: data.retrieval_bundle?.entries?.[0]?.entry_id || null,
          retrievalDirty: Boolean(data.retrieval_bundle?.status?.has_manual_edits),
          retrievalEmbeddingStatus: data.retrieval_bundle?.status?.has_stale_embeddings ? 'stale' : 'ready',
          retrievalWriteStatus: data.retrieval_bundle?.status?.write_status || 'idle',
          retrievalSourceParseVersionId: data.retrieval_bundle?.source_parse_version_id || null,
          retrievalWriteManifest: data.retrieval_write_manifest || null,
          textChunks: data.text_chunks || [],
          sourceAlignment: data.source_alignment || {},
          chunkingMeta: data.chunking_meta || null,
          alignmentStats: data.alignment_stats || null,
          alignmentUnmatchedItems: data.alignment_unmatched_items || [],
          neo4jStatus: null,
          neo4jLastWriteSummary: null,
          neo4jLastRunId: null,
          neo4jDocId: null,
        });
        
        terminalPanel.switchTab(targetTab);
        terminalPanel.renderNeo4jStatus(null);
        terminalPanel.refreshNeo4jStatus();
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
        if (typeof terminalPanel.renderVersionRail === 'function') {
          terminalPanel.renderVersionRail(effectiveVersions, effectiveActiveVersionId);
        }
        if (data.retrieval_bundle && typeof terminalPanel.renderRetrievalBundle === 'function') {
          terminalPanel.lastRetrievalWriteManifest = data.retrieval_write_manifest || null;
          terminalPanel.renderRetrievalBundle(data.retrieval_bundle);
        }
        if (Array.isArray(data.discovery_history)) {
          terminalPanel.discoveryHistory = data.discovery_history;
          terminalPanel.activeDiscoveryIdx = data.discovery_history.length > 0 ? data.discovery_history.length - 1 : -1;
          terminalPanel.saveDiscoveryHistory();
          terminalPanel.renderDiscoveryHistoryTabs();
          if (data.discovery_history.length > 0) {
            terminalPanel.showDiscoveryResult(terminalPanel.activeDiscoveryIdx, false);
          } else {
            terminalPanel.resetDiscoveryUI();
          }
        }
        
        terminalPanel.setStatus('测试数据已加载（含上次解析结果）', '#27ae60');
        terminalPanel.ensureTerminalExpanded();
      }
    }
  }).catch(err => console.warn('加载测试数据失败:', err));

  applyWorkspaceLayout(store.getState());
  
  console.log('legal_ontology_workspace initialized.');
});
