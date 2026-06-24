export class Store {
  constructor(initialState = {}) {
    this.state = initialState;
    this.listeners = new Set();
  }
  getState() { return this.state; }
  setState(newState) {
    let hasChanged = false;
    for (const key in newState) {
      if (this.state[key] !== newState[key]) {
        hasChanged = true;
        break;
      }
    }
    if (!hasChanged) return;
    this.state = { ...this.state, ...newState };
    this.listeners.forEach(fn => fn(this.state));
  }
  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}
export const store = new Store({
  selectedNodeId: null,
  selectedNodeType: null,
  selectedGraph: null, // 'ontology' | 'parse'
  ontologySelectionKind: 'type',
  ontologySelectionScope: 'all',
  hoverOntologyDomain: null,
  selectedEdgeId: null,
  isPanelOpen: false,
  graphViewMode: 'global',
  discoveryHistory: [],
  activeDiscoveryIdx: -1,
  isOntologyVisible: true,
  isParseResultAvailable: false,
  workspaceLayoutMode: 'ontology_primary',
  terminalCollapsed: false,
  terminalHeightPx: null,
  parseGraphDisplayMode: 'skeleton',
  parseGraphLayoutMode: 'lane',
  parseGraphExpandedGroups: {},
  parseGraphSemanticZoom: 'mid',
  parseVersions: [],
  parseActiveVersionId: 'v0',
  parseEnhancementRuns: [],
  parseEnhancementPreviewActive: false,
  parseEnhancementPreviewRunId: null,
  parseEnhancementPreviewPatch: null,
  parseMergeHighlight: null,
  retrievalBundle: null,
  retrievalEntries: [],
  retrievalActiveEntryId: null,
  retrievalDirty: false,
  retrievalEmbeddingStatus: 'idle',
  retrievalWriteStatus: 'idle',
  retrievalSourceParseVersionId: null,
  retrievalWriteManifest: null,
  retrievalLastWriteSummary: null,
  retrievalFilters: {
    type: 'all',
    status: 'all',
    search: '',
  },
  retrievalPreviewMode: 'vector',
  textChunks: [],
  sourceAlignment: {},
  chunkingMeta: null,
  alignmentStats: null,
  alignmentUnmatchedItems: [],
  neo4jStatus: null,
  neo4jLastWriteSummary: null,
  neo4jLastRunId: null,
  neo4jDocId: null,
});
