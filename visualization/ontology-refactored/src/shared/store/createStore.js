export class Store {
  constructor(initialState = {}) {
    this.state = initialState;
    this.listeners = new Set();
  }

  getState() {
    return this.state;
  }

  setState(patch) {
    let changed = false;
    const nextState = { ...this.state };
    Object.keys(patch || {}).forEach(key => {
      if (nextState[key] !== patch[key]) {
        nextState[key] = patch[key];
        changed = true;
      }
    });
    if (!changed) return;
    this.state = nextState;
    this.listeners.forEach(listener => listener(this.state));
  }

  update(key, patch) {
    const current = this.state[key] || {};
    const next = { ...current, ...(patch || {}) };
    const keys = new Set([...Object.keys(current), ...Object.keys(next)]);
    let changed = false;

    for (const field of keys) {
      if (current[field] !== next[field]) {
        changed = true;
        break;
      }
    }

    if (!changed) return;
    this.setState({ [key]: next });
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

export function createStore(initialState = {}) {
  return new Store(initialState);
}
