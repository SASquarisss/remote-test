import { safeGetElement } from '../utils/dom.js';

export class TopNavBar {
  constructor({ containerId = 'topNavBar', productName, subtitle = '', stats = [], actions = [] }) {
    this.containerId = containerId;
    this.productName = productName;
    this.subtitle = subtitle;
    this.stats = stats;
    this.actions = actions;
    this.container = document.getElementById(containerId);
    this.ensureUI();
  }

  ensureUI() {
    if (this.container) return;
    const statsHtml = this.stats.map(stat => `
      <span class="app-topbar-stat"><strong data-stat-key="${stat.key}">-</strong><em>${stat.label}</em></span>
    `).join('');
    const actionsHtml = this.actions.map(action => `
      <button class="app-topbar-action" data-action-key="${action.key}">${action.label}</button>
    `).join('');

    document.body.insertAdjacentHTML('afterbegin', `
      <div id="${this.containerId}" class="app-topbar">
        <div class="app-topbar-left">
          <h1>${this.productName}</h1>
          <div class="app-topbar-subtitle">${this.subtitle}</div>
        </div>
        <div class="app-topbar-right">
          <div class="app-topbar-stats">${statsHtml}</div>
          ${actionsHtml ? `<div class="app-topbar-actions">${actionsHtml}</div>` : ''}
        </div>
      </div>
    `);
    this.container = safeGetElement(this.containerId);
  }

  updateStats(statsMap = {}) {
    if (!this.container) return;
    Object.keys(statsMap).forEach(key => {
      const el = this.container.querySelector(`[data-stat-key="${key}"]`);
      if (el) el.textContent = statsMap[key];
    });
  }
}
