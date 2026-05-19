export class ControlsPanel {
  constructor({ networkProvider, containerId, offset = { left: 20, bottom: 20 } }) {
    this.networkProvider = networkProvider;
    this.containerId = containerId;
    this.offset = offset;
    this.ensureUI();
    this.bindEvents();
  }

  get network() {
    return this.networkProvider ? this.networkProvider() : null;
  }

  ensureUI() {
    if (document.getElementById('sharedGraphControls')) return;
    const host = document.getElementById(this.containerId) || document.body;
    host.insertAdjacentHTML('beforeend', `
      <div id="sharedGraphControls" class="graph-controls" style="left:${this.offset.left}px;bottom:${this.offset.bottom}px;">
        <button id="sharedBtnZoomIn" title="放大">+</button>
        <button id="sharedBtnZoomOut" title="缩小">-</button>
        <button id="sharedBtnFit" title="适应视图">⤢</button>
      </div>
    `);
  }

  bindEvents() {
    const zoomIn = document.getElementById('sharedBtnZoomIn');
    const zoomOut = document.getElementById('sharedBtnZoomOut');
    const fit = document.getElementById('sharedBtnFit');

    if (zoomIn) {
      zoomIn.addEventListener('click', () => {
        if (!this.network) return;
        this.network.moveTo({ scale: this.network.getScale() * 1.15, animation: true });
      });
    }

    if (zoomOut) {
      zoomOut.addEventListener('click', () => {
        if (!this.network) return;
        this.network.moveTo({ scale: this.network.getScale() / 1.15, animation: true });
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
