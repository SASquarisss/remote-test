import { createStore } from './createStore.js';

export const initialDatabaseState = {
  app: {
    product: 'legal_ontology_database',
    ready: true
  },
  selection: {
    activeCaseKey: null,
    activeNodeId: null,
    activeEdgeId: null,
    activeItem: null
  },
  filters: {
    sources: [],
    caseCategories: [],
    caseReasons: [],
    trialLevels: [],
    judgmentYears: [],
    publicationYears: []
  },
  graph: {
    layoutMode: 'force',
    graphViewMode: 'all',
    browseMode: 'latest_only',
    selectedOntologyType: null,
    hoverOntologyType: null,
    renderedTypeCounts: {}
  },
  panels: {
    detailOpen: false,
    middleTab: 'raw',
    rightTab: 'summary',
    schemaTab: 'graph',
    schemaOpen: false
  },
  layout: {
    topFiltersHeightPx: 72,
    terminalHeightPx: 280,
    terminalCollapsed: false,
    terminalLeftWidthPct: 28,
    terminalCenterWidthPct: 42
  },
  data: {
    casesIndex: [],
    caseDetailMap: {}
  },
  ui: {
    loading: false,
    error: null,
    statusText: '等待加载案例索引',
    vectorQueryText: '',
    vectorQueryMode: 'similar_cases',
    vectorQueryStatus: '待输入检索描述'
  }
};

export const databaseStore = createStore(initialDatabaseState);
