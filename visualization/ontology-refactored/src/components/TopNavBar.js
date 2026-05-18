import { safeGetElement } from '../utils/dom.js';

export class TopNavBar {
  constructor() {
    this.container = safeGetElement('topNavBar');
    this.nodeCount = safeGetElement('navNodeCount');
    this.edgeCount = safeGetElement('navEdgeCount');
    
    this.ensureUI();
  }
  
  ensureUI() {
    if (!this.container) {
      const html = `
        <div id="topNavBar" style="position: fixed; top: 0; left: 0; right: 0; z-index: 999; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color: #fff; padding: 10px 24px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 8px rgba(0,0,0,0.3);">
          <div>
            <h1 style="font-size: 17px; font-weight: 600; letter-spacing: 1px; margin: 0;">📜 法律本体论 v2.2 (Refactored)</h1>
            <div style="font-size: 12px; opacity: 0.7;">Legal Ontology Knowledge Graph</div>
          </div>
          <div style="font-size: 12px; opacity: 0.8; display: flex; gap: 16px; align-items: center;">
            <span><span id="navNodeCount">-</span> 类型节点</span>
            <span><span id="navEdgeCount">-</span> 关系边</span>
            <button style="background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); color: #fff; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.25)'" onmouseout="this.style.background='rgba(255,255,255,0.15)'">⚙ 样式</button>
          </div>
        </div>
      `;
      document.body.insertAdjacentHTML('afterbegin', html);
      
      this.container = document.getElementById('topNavBar');
      this.nodeCount = document.getElementById('navNodeCount');
      this.edgeCount = document.getElementById('navEdgeCount');
    }
  }
  
  updateStats(nodes, edges) {
    if (this.nodeCount) this.nodeCount.textContent = nodes;
    if (this.edgeCount) this.edgeCount.textContent = edges;
  }
}
