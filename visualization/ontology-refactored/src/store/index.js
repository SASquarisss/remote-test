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
  isPanelOpen: false,
});
