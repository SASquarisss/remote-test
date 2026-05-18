import { safeGetElement } from '../utils/dom.js';
import { store } from '../store/index.js';

export class ControlsPanel {
  constructor(network) {
    this.network = network;
    this.ensureUI();
    this.bindEvents();
  }

  ensureUI() {
    if (!document.getElementById('ontologyControls')) {
      const html = `
        <div id="ontologyControls" style="position: absolute; bottom: 20px; left: 20px; z-index: 998; display: flex; flex-direction: column; gap: 8px; background: rgba(255,255,255,0.9); padding: 8px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
          <button id="btnZoomIn" style="width: 32px; height: 32px; border-radius: 4px; border: 1px solid #ccc; background: #fff; cursor: pointer; font-weight: bold; font-size: 16px;" title="放大">+</button>
          <button id="btnZoomOut" style="width: 32px; height: 32px; border-radius: 4px; border: 1px solid #ccc; background: #fff; cursor: pointer; font-weight: bold; font-size: 16px;" title="缩小">-</button>
          <button id="btnFit" style="width: 32px; height: 32px; border-radius: 4px; border: 1px solid #ccc; background: #fff; cursor: pointer; font-size: 14px;" title="适应屏幕">⤢</button>
        </div>
      `;
      const container = document.getElementById('ontologyContainer');
      if (container) {
        container.insertAdjacentHTML('beforeend', html);
      } else {
        document.body.insertAdjacentHTML('beforeend', html);
      }
    }
  }

  bindEvents() {
    const zoomIn = document.getElementById('btnZoomIn');
    const zoomOut = document.getElementById('btnZoomOut');
    const fit = document.getElementById('btnFit');

    if (zoomIn) {
      zoomIn.addEventListener('click', () => {
        if (!this.network) return;
        const currentScale = this.network.getScale();
        this.network.moveTo({ scale: currentScale * 1.2, animation: true });
      });
    }

    if (zoomOut) {
      zoomOut.addEventListener('click', () => {
        if (!this.network) return;
        const currentScale = this.network.getScale();
        this.network.moveTo({ scale: currentScale / 1.2, animation: true });
      });
    }

    if (fit) {
      fit.addEventListener('click', () => {
        if (!this.network) return;
        this.network.fit({ animation: true });
      });
    }
  }
}
