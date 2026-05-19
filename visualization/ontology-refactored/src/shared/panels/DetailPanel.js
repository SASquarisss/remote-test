import { safeGetElement } from '../utils/dom.js';

export class DetailPanel {
  constructor({ store, panelId, titleId, bodyId, closeId, titleResolver, contentRenderer, isOpenSelector, itemSelector, onClose }) {
    this.store = store;
    this.panel = safeGetElement(panelId);
    this.title = safeGetElement(titleId);
    this.body = safeGetElement(bodyId);
    this.closeBtn = safeGetElement(closeId);
    this.titleResolver = titleResolver;
    this.contentRenderer = contentRenderer;
    this.isOpenSelector = isOpenSelector;
    this.itemSelector = itemSelector;
    this.onClose = onClose;

    this.bindEvents();
    this.store.subscribe(state => this.render(state));
    this.render(this.store.getState());
  }

  bindEvents() {
    if (!this.closeBtn) return;
    this.closeBtn.addEventListener('click', event => {
      event.stopPropagation();
      if (this.onClose) this.onClose();
    });
  }

  render(state) {
    if (!this.panel || !this.title || !this.body) return;
    const isOpen = this.isOpenSelector ? this.isOpenSelector(state) : false;
    const item = this.itemSelector ? this.itemSelector(state) : null;

    this.panel.classList.toggle('open', !!isOpen);
    this.title.textContent = item ? (this.titleResolver ? this.titleResolver(item, state) : '详细信息') : '详细信息';

    if (!item) {
      this.body.innerHTML = '<div class="detail-empty">选择对象后查看详细信息</div>';
      return;
    }

    this.body.innerHTML = this.contentRenderer ? this.contentRenderer(item, state) : '<div class="detail-empty">暂无渲染器</div>';
  }
}
