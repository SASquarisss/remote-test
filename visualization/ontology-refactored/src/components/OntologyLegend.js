import { safeGetElement } from '../utils/dom.js';
import { ENTITY_DATA, ZH_LABELS } from '../data/schema.js';
import { escapeHtml } from '../utils/formatter.js';

export class OntologyLegend {
  constructor() {
    this.ensureUI();
    this.container = safeGetElement('ontologyInheritanceTab');
    this.isCollapsed = false;
    
    this.bindEvents();
    this.render();
  }
  
  ensureUI() {
    // The UI is now handled by the ontologyContainer tabs.
    // We no longer need to inject the floating legend here.
  }
  
  bindEvents() {
    // No longer needed
  }
  
  toggle(collapse) {
    // Handled by tabs now
  }
  
  render() {
    const body = document.getElementById('legendBody');
    if (!body) return;
    
    // Build a simple tree for demonstration
    let html = '';
    const rootNodes = Object.keys(ENTITY_DATA).filter(k => !ENTITY_DATA[k].parent);
    
    rootNodes.forEach(root => {
      const rootZh = ZH_LABELS[root] || root;
      html += `<div style="font-weight: 600; font-size: 14px; margin: 6px 0 3px 0; display: flex; align-items: center; gap: 8px;">`;
      html += `<span style="width: 12px; height: 12px; border-radius: 50%; background: ${ENTITY_DATA[root].color?.background || '#ccc'}; border: 1px solid #aaa;"></span>`;
      html += `${escapeHtml(rootZh)} <span style="color:#888;font-size:12px;font-weight:normal;">(${escapeHtml(root)})</span></div>`;
      
      const children = Object.keys(ENTITY_DATA).filter(k => ENTITY_DATA[k].parent === root);
      if (children.length > 0) {
        html += `<div style="padding-left: 24px;">`;
        children.forEach(child => {
          const childZh = ZH_LABELS[child] || child;
          html += `<div style="font-size: 13px; color: #555; padding: 2px 0; display: flex; align-items: center; gap: 8px;">`;
          html += `<span style="width: 10px; height: 10px; border-radius: 4px; background: ${ENTITY_DATA[child].color?.background || '#ccc'};"></span>`;
          html += `${escapeHtml(childZh)}</div>`;
        });
        html += `</div>`;
      }
    });
    
    body.innerHTML = html;
  }
}
