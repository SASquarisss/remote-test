export class DatabaseGraphController {
  constructor({ store, containerId }) {
    this.store = store;
    this.container = document.getElementById(containerId);
    this.el = null;
    this.init();
    this.store.subscribe(state => this.render(state));
  }

  init() {
    if (!this.container) return;
    this.el = document.createElement('div');
    this.el.className = 'db-graph-controller';
    this.el.style.position = 'absolute';
    this.el.style.top = '16px';
    this.el.style.right = '16px';
    this.el.style.zIndex = '10';
    this.el.style.background = 'rgba(255, 255, 255, 0.95)';
    this.el.style.border = '1px solid #cbd5e1';
    this.el.style.borderRadius = '8px';
    this.el.style.padding = '12px';
    this.el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
    this.el.style.fontFamily = 'sans-serif';
    this.el.style.fontSize = '12px';
    this.el.style.backdropFilter = 'blur(4px)';
    this.el.style.minWidth = '160px';

    this.container.style.position = 'relative'; // Ensure relative positioning for absolute child
    this.container.appendChild(this.el);

    this.el.addEventListener('change', (e) => {
      if (e.target.tagName === 'INPUT' && e.target.type === 'checkbox') {
        const type = e.target.getAttribute('data-type');
        if (type) {
          const state = this.store.getState();
          const visibleTypes = { ...state.graphConfig.visibleTypes, [type]: e.target.checked };
          this.store.update('graphConfig', { ...state.graphConfig, visibleTypes });
        }
      }
    });
  }

  render(state) {
    if (!this.el) return;
    const config = state.graphConfig || {};
    const vt = config.visibleTypes || {};

    const types = [
      { key: 'LegalProvision', label: '法条 (T0)', color: '#5b6ee1' },
      { key: 'CaseType', label: '案由 (T0)', color: '#fb923c' },
      { key: 'Fact', label: '事实 (T1)', color: '#0284c7' },
      { key: 'DisputeFocus', label: '争议焦点 (T1)', color: '#d97706' },
      { key: 'JudgmentResult', label: '裁判结果 (T1)', color: '#16a34a' },
      { key: 'Evidence', label: '证据 (T2)', color: '#c9852b' },
      { key: 'LegalSubject', label: '诉讼主体 (T2)', color: '#94a3b8' },
      { key: 'Person', label: '自然人 (T3)', color: '#22c55e' }
    ];

    let html = `<div style="font-weight: bold; margin-bottom: 8px; color: #1e293b; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">图谱视野控制</div>`;
    
    types.forEach(t => {
      const checked = vt[t.key] ? 'checked' : '';
      html += `
        <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px; cursor: pointer; color: #334155;">
          <input type="checkbox" data-type="${t.key}" ${checked} style="accent-color: ${t.color}; cursor: pointer;">
          <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${t.color};"></span>
          ${t.label}
        </label>
      `;
    });

    if (this.el.innerHTML !== html) {
      this.el.innerHTML = html;
    }
  }
}
