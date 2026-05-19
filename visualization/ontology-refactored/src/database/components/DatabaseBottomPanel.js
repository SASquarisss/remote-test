import { getFilteredCases, getVisibleCases, getActiveCaseEntry, getVersionEntries } from '../model/selectors.js';
import { escapeHtml } from '../../shared/utils/formatter.js';

function getCaseTypeText(entry = {}) {
  const meta = entry.meta || {};
  return [...(meta.case_categories || []), ...(meta.case_reasons || []), entry.case_type || '']
    .filter(Boolean)
    .join(' / ') || '未标注';
}

function getSummaryLines(entry = {}) {
  const meta = entry.meta || {};
  const trialLevels = (meta.trial_levels || []).join(' / ') || '未标注';
  const judgmentYears = (meta.judgment_years || []).join(' / ') || '未标注';
  const publicationYears = (meta.publication_years || []).join(' / ') || '未标注';
  return { trialLevels, judgmentYears, publicationYears };
}

export class DatabaseBottomPanel {
  constructor({ store, containerId }) {
    this.store = store;
    this.container = document.getElementById(containerId);
    this.ensureUI();
    this.bindEvents();
    this.store.subscribe(state => this.render(state));
    this.render(this.store.getState());
  }

  ensureUI() {
    if (!this.container || this.container.children.length) return;
    this.container.innerHTML = `
      <div class="db-terminal-shell">
        <div id="dbTerminalDragHandle" class="db-terminal-drag-handle">
          <span>案例终端工作台</span>
          <div class="db-terminal-handle-actions">
            <span id="dbBottomStatus" class="db-terminal-status">等待加载</span>
            <button type="button" id="dbTerminalToggleCollapse" class="db-terminal-toggle-btn">收起</button>
          </div>
        </div>
        <div class="db-terminal-body">
          <section id="dbTerminalCases" class="db-terminal-col db-terminal-left">
            <div class="db-terminal-header">
              <div class="db-terminal-title">案件列表</div>
              <div class="db-terminal-subtitle">左侧列表保持与当前筛选结果同步</div>
            </div>
            <div id="dbCasesPane" class="db-terminal-content"></div>
          </section>
          <div id="dbTerminalSplitterLeft" class="db-terminal-splitter"></div>
          <section id="dbTerminalMiddle" class="db-terminal-col db-terminal-middle">
            <div class="db-terminal-header">
              <div class="db-terminal-tabs">
                <button type="button" class="db-terminal-tab" data-middle-tab="raw">原始数据</button>
                <button type="button" class="db-terminal-tab" data-middle-tab="parse">解析数据</button>
                <button type="button" class="db-terminal-tab" data-middle-tab="eval">评估结果</button>
              </div>
              <div class="db-terminal-subtitle">中间区域用于多标签数据浏览</div>
            </div>
            <div id="dbMiddlePane" class="db-terminal-content"></div>
          </section>
          <div id="dbTerminalSplitterRight" class="db-terminal-splitter"></div>
          <section id="dbTerminalRight" class="db-terminal-col db-terminal-right">
            <div class="db-terminal-header">
              <div class="db-terminal-tabs">
                <button type="button" class="db-terminal-tab" data-right-tab="summary">案例摘要</button>
                <button type="button" class="db-terminal-tab" data-right-tab="versions">版本链</button>
              </div>
              <div class="db-terminal-subtitle">右侧展示结构摘要与辅助信息</div>
            </div>
            <div id="dbRightPane" class="db-terminal-content"></div>
          </section>
        </div>
      </div>
    `;
  }

  setActiveCase(caseKey) {
    if (!caseKey || caseKey === 'all') {
      this.store.update('selection', {
        activeCaseKey: null,
        activeNodeId: null,
        activeEdgeId: null,
        activeItem: null
      });
      this.store.update('panels', { detailOpen: false });
      return;
    }

    const state = this.store.getState();
    const entry = state.data.casesIndex.find(item => item.caseKey === caseKey);
    if (!entry) return;
    this.store.update('selection', {
      activeCaseKey: entry.caseKey,
      activeNodeId: entry.caseKey,
      activeEdgeId: null,
      activeItem: { kind: 'case', ...entry }
    });
    this.store.update('panels', { detailOpen: true });
  }

  bindResizeEvents() {
    const dragHandle = this.container.querySelector('#dbTerminalDragHandle');
    const leftSplitter = this.container.querySelector('#dbTerminalSplitterLeft');
    const rightSplitter = this.container.querySelector('#dbTerminalSplitterRight');
    const leftCol = this.container.querySelector('#dbTerminalCases');
    const middleCol = this.container.querySelector('#dbTerminalMiddle');

    if (dragHandle) {
      let draggingHeight = false;
      let startY = 0;
      let startHeight = 0;

      dragHandle.addEventListener('mousedown', event => {
        if (this.store.getState().layout.terminalCollapsed) return;
        draggingHeight = true;
        startY = event.clientY;
        startHeight = this.container.offsetHeight;
        document.body.style.cursor = 'ns-resize';
      });

      document.addEventListener('mousemove', event => {
        if (!draggingHeight) return;
        const nextHeight = Math.max(220, Math.min(window.innerHeight - 180, startHeight + (startY - event.clientY)));
        this.container.style.height = `${nextHeight}px`;
        document.getElementById('databaseApp')?.style.setProperty('--db-terminal-height', `${nextHeight}px`);
      });

      document.addEventListener('mouseup', () => {
        if (!draggingHeight) return;
        draggingHeight = false;
        document.body.style.cursor = '';
        this.store.update('layout', { terminalHeightPx: this.container.offsetHeight });
      });
    }

    if (leftSplitter && leftCol && middleCol) {
      let draggingLeft = false;
      leftSplitter.addEventListener('mousedown', () => {
        draggingLeft = true;
        document.body.style.cursor = 'col-resize';
      });
      document.addEventListener('mousemove', event => {
        if (!draggingLeft) return;
        const body = this.container.querySelector('.db-terminal-body');
        if (!body) return;
        const bounds = body.getBoundingClientRect();
        const pct = ((event.clientX - bounds.left) / bounds.width) * 100;
        if (pct < 18 || pct > 45) return;
        leftCol.style.width = `${pct}%`;
      });
      document.addEventListener('mouseup', () => {
        if (!draggingLeft) return;
        draggingLeft = false;
        document.body.style.cursor = '';
        this.store.update('layout', { terminalLeftWidthPct: leftCol.offsetWidth / this.container.offsetWidth * 100 });
      });
    }

    if (rightSplitter && leftCol && middleCol) {
      let draggingRight = false;
      rightSplitter.addEventListener('mousedown', () => {
        draggingRight = true;
        document.body.style.cursor = 'col-resize';
      });
      document.addEventListener('mousemove', event => {
        if (!draggingRight) return;
        const body = this.container.querySelector('.db-terminal-body');
        if (!body) return;
        const bounds = body.getBoundingClientRect();
        const leftWidth = leftCol.getBoundingClientRect().width;
        const pct = ((event.clientX - bounds.left - leftWidth - leftSplitter.offsetWidth) / bounds.width) * 100;
        if (pct < 24 || pct > 58) return;
        middleCol.style.width = `${pct}%`;
      });
      document.addEventListener('mouseup', () => {
        if (!draggingRight) return;
        draggingRight = false;
        document.body.style.cursor = '';
        this.store.update('layout', { terminalCenterWidthPct: middleCol.offsetWidth / this.container.offsetWidth * 100 });
      });
    }
  }

  bindEvents() {
    if (!this.container) return;
    this.bindResizeEvents();

    this.container.addEventListener('click', event => {
      const middleTab = event.target.closest('[data-middle-tab]');
      if (middleTab) {
        this.store.update('panels', { middleTab: middleTab.getAttribute('data-middle-tab') || 'raw' });
        return;
      }

      const rightTab = event.target.closest('[data-right-tab]');
      if (rightTab) {
        this.store.update('panels', { rightTab: rightTab.getAttribute('data-right-tab') || 'summary' });
        return;
      }

      const toggleCollapse = event.target.closest('#dbTerminalToggleCollapse');
      if (toggleCollapse) {
        const collapsed = Boolean(this.store.getState().layout.terminalCollapsed);
        this.store.update('layout', { terminalCollapsed: !collapsed });
        return;
      }

      const caseItem = event.target.closest('[data-case-key]');
      if (caseItem) {
        this.setActiveCase(caseItem.getAttribute('data-case-key'));
      }
    });
  }

  renderCases(state) {
    const filteredEntries = getFilteredCases(state.data.casesIndex, state.filters);
    const visibleEntries = getVisibleCases(filteredEntries, state.graph.browseMode);
    const summaryHtml = `
      <div class="db-case-summary">
        <div class="db-case-summary-text">当前匹配 <strong>${filteredEntries.length}</strong> 个案例，图谱展示 <strong>${visibleEntries.length}</strong> 个案例。</div>
      </div>
    `;

    if (!visibleEntries.length) {
      return `${summaryHtml}<div class="db-empty">当前没有可展示的案例</div>`;
    }

    const list = visibleEntries.map(entry => {
      const meta = entry.meta || {};
      const stats = meta.stats || {};
      const { trialLevels, judgmentYears } = getSummaryLines(entry);
      return `
        <div class="db-case-item ${state.selection.activeCaseKey === entry.caseKey ? 'active' : ''}" data-case-key="${escapeHtml(entry.caseKey)}">
          <div class="db-case-title-row">
            <div class="db-case-title">${escapeHtml(entry.case_name || entry.row_id)}</div>
            <div class="db-case-tags">
              <span class="db-case-tag">${escapeHtml(meta.source || entry.source || '未知来源')}</span>
              ${entry.version > 1 ? `<span class="db-case-tag db-case-tag-version">v${escapeHtml(String(entry.version))}</span>` : ''}
              ${stats.facts ? `<span class="db-case-tag db-case-tag-metric">facts ${escapeHtml(String(stats.facts))}</span>` : ''}
              ${stats.relations ? `<span class="db-case-tag db-case-tag-metric">rels ${escapeHtml(String(stats.relations))}</span>` : ''}
            </div>
          </div>
          <div class="db-case-meta">#${escapeHtml(entry.row_id)} · ${escapeHtml(getCaseTypeText(entry))}</div>
          <div class="db-case-meta">${escapeHtml(trialLevels)} · 裁判年份 ${escapeHtml(judgmentYears)}</div>
        </div>
      `;
    }).join('');

    return `${summaryHtml}
      <div class="db-case-item ${state.selection.activeCaseKey ? '' : 'active'}" data-case-key="all">
        <div class="db-case-title">全部结果集</div>
        <div class="db-case-meta">返回总体浏览模式，按来源聚合查看当前结果集。</div>
      </div>
      ${list}`;
  }

  renderMiddlePane(state) {
    const active = getActiveCaseEntry(state);
    if (!active) {
      return '<div class="db-empty">选择案例后显示完整原始记录或结构化输出</div>';
    }

    const detail = state.data.caseDetailMap[active.caseKey] || null;
    const rawText = detail?.raw_text || detail?.raw_record?.input?.text || '';
    const parseData = detail?.json_result || detail?.raw_record?.output || null;
    const parseEval = detail?.parse_eval || detail?.raw_record?.eval || null;
    const ontologyEval = detail?.ontology_eval || detail?.raw_record?.ontology_eval || null;
    const rawRecord = detail?.raw_record || detail || {
      row_id: active.row_id,
      case_name: active.case_name,
      case_type: active.case_type,
      source: active.source,
      version: active.version,
      meta: active.meta
    };

    if (state.panels.middleTab === 'parse') {
      return parseData
        ? `<pre class="db-raw-pre">${escapeHtml(JSON.stringify(parseData, null, 2))}</pre>`
        : '<div class="db-empty">当前案例暂无解析数据</div>';
    }

    if (state.panels.middleTab === 'eval') {
      const evalPayload = {
        parse_eval: parseEval || null,
        ontology_eval: ontologyEval || null
      };
      return (parseEval || ontologyEval)
        ? `<pre class="db-raw-pre">${escapeHtml(JSON.stringify(evalPayload, null, 2))}</pre>`
        : '<div class="db-empty">当前案例暂无评估结果</div>';
    }

    return rawText
      ? `<pre class="db-raw-pre">${escapeHtml(rawText)}</pre>`
      : `<pre class="db-raw-pre">${escapeHtml(JSON.stringify(rawRecord, null, 2))}</pre>`;
  }

  renderSummaryPane(state) {
    const active = getActiveCaseEntry(state);
    if (!active) {
      return '<div class="db-empty">当前未选择案例</div>';
    }

    const detail = state.data.caseDetailMap[active.caseKey] || null;
    const meta = active.meta || {};
    const stats = meta.stats || {};
    const { trialLevels, judgmentYears, publicationYears } = getSummaryLines(active);
    const topKeys = detail?.json_result ? Object.keys(detail.json_result).join(', ') : '等待加载';

    return `
      <div class="db-version-card">
        <div class="db-version-title">${escapeHtml(active.case_name || active.row_id)}</div>
        <div class="db-version-meta">#${escapeHtml(active.row_id)} · ${escapeHtml(getCaseTypeText(active))}</div>
        <div class="db-version-note">
          数据来源：${escapeHtml(meta.source || active.source || '未知来源')}<br>
          审级：${escapeHtml(trialLevels)}<br>
          裁判年份：${escapeHtml(judgmentYears)}<br>
          发布年份：${escapeHtml(publicationYears)}<br>
          解析键：${escapeHtml(topKeys)}
        </div>
        <div class="db-version-list">
          <div class="db-version-item"><span>facts</span><span>${escapeHtml(String(stats.facts || 0))}</span></div>
          <div class="db-version-item"><span>relations</span><span>${escapeHtml(String(stats.relations || 0))}</span></div>
          <div class="db-version-item"><span>focuses</span><span>${escapeHtml(String(stats.focuses || 0))}</span></div>
          <div class="db-version-item"><span>evidence</span><span>${escapeHtml(String(stats.evidence || 0))}</span></div>
        </div>
      </div>
    `;
  }

  renderVersions(state) {
    const active = getActiveCaseEntry(state);
    if (!active) {
      return '<div class="db-empty">当前未选择案例</div>';
    }

    const versions = getVersionEntries(state, active.caseKey);
    if (versions.length <= 1) {
      return `
        <div class="db-version-card">
          <div class="db-version-title">版本信息</div>
          <div class="db-version-meta">当前案例 #${escapeHtml(active.row_id)}</div>
          <div class="db-version-note">该案例当前只有一个可用版本。</div>
        </div>
      `;
    }

    return `
      <div class="db-version-card">
        <div class="db-version-title">版本链</div>
        <div class="db-version-meta">当前案例 #${escapeHtml(active.row_id)} 共 ${escapeHtml(String(versions.length))} 个版本</div>
        <div class="db-version-list">
          ${versions.map(item => `
            <button type="button" class="db-version-item ${item.caseKey === active.caseKey ? 'active' : ''}" data-case-key="${escapeHtml(item.caseKey)}">
              <span>v${escapeHtml(String(item.version || 1))}</span>
              <span>${escapeHtml(item.case_name || item.row_id)}</span>
            </button>
          `).join('')}
        </div>
      </div>
    `;
  }

  render(state) {
    if (!this.container) return;

    const leftCol = this.container.querySelector('#dbTerminalCases');
    const middleCol = this.container.querySelector('#dbTerminalMiddle');
    const toggleButton = this.container.querySelector('#dbTerminalToggleCollapse');
    const collapsed = Boolean(state.layout.terminalCollapsed);
    if (leftCol) leftCol.style.width = `${state.layout.terminalLeftWidthPct}%`;
    if (middleCol) middleCol.style.width = `${state.layout.terminalCenterWidthPct}%`;
    this.container.style.height = `${collapsed ? 28 : state.layout.terminalHeightPx}px`;
    this.container.style.minHeight = collapsed ? '28px' : '220px';
    this.container.classList.toggle('collapsed', collapsed);
    if (toggleButton) toggleButton.textContent = collapsed ? '展开' : '收起';

    this.container.querySelectorAll('[data-middle-tab]').forEach(button => {
      button.classList.toggle('active', button.getAttribute('data-middle-tab') === state.panels.middleTab);
    });
    this.container.querySelectorAll('[data-right-tab]').forEach(button => {
      button.classList.toggle('active', button.getAttribute('data-right-tab') === state.panels.rightTab);
    });

    const casesPane = this.container.querySelector('#dbCasesPane');
    const middlePane = this.container.querySelector('#dbMiddlePane');
    const rightPane = this.container.querySelector('#dbRightPane');
    const status = this.container.querySelector('#dbBottomStatus');

    if (casesPane) casesPane.innerHTML = this.renderCases(state);
    if (middlePane) middlePane.innerHTML = this.renderMiddlePane(state);
    if (rightPane) {
      rightPane.innerHTML = state.panels.rightTab === 'versions'
        ? this.renderVersions(state)
        : this.renderSummaryPane(state);
    }
    if (status) status.textContent = state.ui.statusText || '就绪';
  }
}
