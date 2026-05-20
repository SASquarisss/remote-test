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
  selectedEdgeId: null,
  isPanelOpen: false,
  isOntologyVisible: true,
  isParseResultAvailable: false,
  workspaceLayoutMode: 'ontology_primary',
  terminalCollapsed: false,
  terminalHeightPx: null,
  parseGraphDisplayMode: 'skeleton',
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
  retrievalFilters: {
    type: 'all',
    status: 'all',
    search: '',
  },
  retrievalPreviewMode: 'vector',
});
