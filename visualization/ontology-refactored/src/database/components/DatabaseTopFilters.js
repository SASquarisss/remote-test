import { getFilterOptions, getFilteredCases, getVisibleCases } from '../model/selectors.js';
import { escapeHtml } from '../../shared/utils/formatter.js';

const BROWSE_MODE_LABELS = {
  recent_latest: '最近 5 个',
  latest_only: '全部最新',
  all_versions: '全部版本'
};

const QUERY_MODE_LABELS = {
  similar_cases: '类案检索',
  multi_field: '复数字段检索'
};

const QUERY_STORAGE_KEY = 'legal_ontology_database.queryWorkbench.v1';

export class DatabaseTopFilters {
  constructor({ store, containerId, onRefresh }) {
    this.store = store;
    this.container = document.getElementById(containerId);
    this.onRefresh = onRefresh;
    this.hydratePersistedQueryWorkbench();
    this.bindEvents();
    this.store.subscribe(state => this.render(state));
    this.store.subscribe(state => this.persistQueryWorkbench(state));
    this.render(this.store.getState());
  }

  hydratePersistedQueryWorkbench() {
    try {
      const raw = window.localStorage.getItem(QUERY_STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      this.store.update('ui', {
        vectorQueryText: saved.vectorQueryText || '',
        vectorQueryMode: saved.vectorQueryMode || 'similar_cases',
        vectorQueryStatus: saved.vectorQueryText
          ? '已恢复上次检索输入'
          : '待输入检索描述'
      });
    } catch {
      // Ignore malformed local cache and continue with defaults.
    }
  }

  persistQueryWorkbench(state) {
    try {
      window.localStorage.setItem(QUERY_STORAGE_KEY, JSON.stringify({
        vectorQueryText: state.ui.vectorQueryText || '',
        vectorQueryMode: state.ui.vectorQueryMode || 'similar_cases'
      }));
    } catch {
      // Ignore storage failures to avoid blocking the page.
    }
  }

  getEventElement(event) {
    const target = event.target;
    if (target instanceof Element) return target;
    return target && target.parentElement ? target.parentElement : null;
  }

  bindEvents() {
    if (!this.container) return;

    this.container.addEventListener('click', event => {
      const eventEl = this.getEventElement(event);
      if (!eventEl) return;

      const filterChip = eventEl.closest('[data-filter-kind]');
      if (filterChip) {
        const kind = filterChip.getAttribute('data-filter-kind');
        const value = filterChip.getAttribute('data-filter-value');
        const current = this.store.getState().filters[kind] || [];
        const next = current.includes(value) ? current.filter(item => item !== value) : [...current, value];
        this.store.update('filters', { [kind]: next });
        return;
      }

      const browseButton = eventEl.closest('[data-browse-mode]');
      if (browseButton) {
        this.store.update('graph', { browseMode: browseButton.getAttribute('data-browse-mode') });
        return;
      }

      const reset = eventEl.closest('[data-action="reset-filters"]');
      if (reset) {
        this.store.update('filters', {
          sources: [],
          caseCategories: [],
          caseReasons: [],
          trialLevels: [],
          judgmentYears: [],
          publicationYears: []
        });
        return;
      }

      const refresh = eventEl.closest('[data-action="refresh-cases"]');
      if (refresh && this.onRefresh) {
        this.onRefresh();
        return;
      }

      const vectorPlaceholder = eventEl.closest('[data-action="vector-query-placeholder"]');
      if (vectorPlaceholder) {
        const mode = this.store.getState().ui.vectorQueryMode || 'similar_cases';
        this.store.update('ui', {
          statusText: `已切换到${QUERY_MODE_LABELS[mode]}工作区，后续将在这里接入真实计算逻辑。`,
          vectorQueryStatus: `${QUERY_MODE_LABELS[mode]}模式已就绪，等待接入算法。`
        });
        return;
      }

      const modeButton = eventEl.closest('[data-query-mode]');
      if (modeButton) {
        const mode = modeButton.getAttribute('data-query-mode') || 'similar_cases';
        this.store.update('ui', {
          vectorQueryMode: mode,
          vectorQueryStatus: `${QUERY_MODE_LABELS[mode]}模式已切换`
        });
      }
    });

    this.container.addEventListener('change', event => {
      const eventEl = this.getEventElement(event);
      if (!eventEl) return;
      const reasonSelector = eventEl.closest('#dbCaseReasonSelector');
      if (reasonSelector) {
        const value = reasonSelector.value || '';
        this.store.update('filters', { caseReasons: value ? [value] : [] });
        return;
      }

      const judgmentYearSelector = eventEl.closest('#dbJudgmentYearSelector');
      if (judgmentYearSelector) {
        const value = judgmentYearSelector.value || '';
        this.store.update('filters', { judgmentYears: value ? [value] : [] });
        return;
      }

      const publicationYearSelector = eventEl.closest('#dbPublicationYearSelector');
      if (publicationYearSelector) {
        const value = publicationYearSelector.value || '';
        this.store.update('filters', { publicationYears: value ? [value] : [] });
        return;
      }

      const selector = eventEl.closest('#dbCaseSelector');
      if (!selector) return;

      const caseKey = selector.value || '';
      if (!caseKey) {
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
    });

    this.container.addEventListener('input', event => {
      const eventEl = this.getEventElement(event);
      if (!eventEl) return;
      const queryInput = eventEl.closest('#dbVectorQueryInput');
      if (!queryInput) return;
      const nextText = queryInput.value || '';
      this.store.update('ui', {
        vectorQueryText: nextText,
        vectorQueryStatus: nextText ? '输入内容已自动保存到本地' : '待输入检索描述'
      });
    });
  }

  renderFilterGroup(kind, title, values, activeValues) {
    const chips = values.length
      ? values.map(value => `
          <button type="button" class="db-top-filter-chip ${activeValues.includes(value) ? 'active' : ''}" data-filter-kind="${kind}" data-filter-value="${escapeHtml(value)}">
            ${escapeHtml(value)}
          </button>
        `).join('')
      : '<span class="db-top-empty">暂无可选项</span>';

    return `
      <div class="db-top-filter-row">
        <div class="db-top-filter-label">${title}</div>
        <div class="db-top-filter-values">${chips}</div>
      </div>
    `;
  }

  renderSelectGroup(selectId, title, values, activeValue, placeholder) {
    return `
      <div class="db-top-filter-row compact">
        <div class="db-top-filter-label">${title}</div>
        <div class="db-top-filter-select-wrap">
          <select id="${selectId}" class="db-top-filter-select">
            <option value="">${placeholder}</option>
            ${values.map(value => `
              <option value="${escapeHtml(value)}" ${activeValue === value ? 'selected' : ''}>${escapeHtml(value)}</option>
            `).join('')}
          </select>
        </div>
      </div>
    `;
  }

  render(state) {
    if (!this.container) return;

    const options = getFilterOptions(state.data.casesIndex);
    const filteredEntries = getFilteredCases(state.data.casesIndex, state.filters);
    const visibleEntries = getVisibleCases(filteredEntries, state.graph.browseMode);
    const activeCaseKey = state.selection.activeCaseKey || '';
    const activeReason = state.filters.caseReasons?.[0] || '';
    const activeJudgmentYear = state.filters.judgmentYears?.[0] || '';
    const activePublicationYear = state.filters.publicationYears?.[0] || '';
    const activeQueryMode = state.ui.vectorQueryMode || 'similar_cases';

    this.container.innerHTML = `
      <div class="db-top-shell">
        <div class="db-top-layout">
          <div class="db-top-left">
            <div class="db-top-main-row">
              <div class="db-top-selector">
                <label for="dbCaseSelector">选择案例:</label>
                <select id="dbCaseSelector">
                  <option value="">全部结果集</option>
                  ${visibleEntries.map(entry => `
                    <option value="${escapeHtml(entry.caseKey)}" ${entry.caseKey === activeCaseKey ? 'selected' : ''}>
                      ${escapeHtml(entry.case_name || entry.row_id)}
                    </option>
                  `).join('')}
                </select>
              </div>
              <div class="db-top-mode-group">
                <span class="db-top-mode-label">浏览模式:</span>
                ${Object.entries(BROWSE_MODE_LABELS).map(([key, label]) => `
                  <button type="button" class="db-top-mode-btn ${state.graph.browseMode === key ? 'active' : ''}" data-browse-mode="${key}">
                    ${label}
                  </button>
                `).join('')}
                <button type="button" class="db-top-refresh-btn" data-action="refresh-cases">刷新数据</button>
                <button type="button" class="db-top-reset-btn" data-action="reset-filters">重置筛选</button>
              </div>
            </div>
            <div class="db-top-filters">
              <div class="db-top-filter-grid">
                <div class="db-top-filter-cell span-2">
                  ${this.renderFilterGroup('caseCategories', '案件类型', options.caseCategories, state.filters.caseCategories)}
                </div>
                <div class="db-top-filter-cell">
                  ${this.renderSelectGroup('dbCaseReasonSelector', '案由类型', options.caseReasons, activeReason, '全部案由类型')}
                </div>
                <div class="db-top-filter-cell">
                  ${this.renderFilterGroup('trialLevels', '审级', options.trialLevels, state.filters.trialLevels)}
                </div>
                <div class="db-top-filter-cell">
                  ${this.renderSelectGroup('dbJudgmentYearSelector', '裁判年份', options.judgmentYears, activeJudgmentYear, '全部裁判年份')}
                </div>
                <div class="db-top-filter-cell">
                  ${this.renderSelectGroup('dbPublicationYearSelector', '发布年份', options.publicationYears, activePublicationYear, '全部发布年份')}
                </div>
                <div class="db-top-filter-cell span-2">
                  ${this.renderFilterGroup('sources', '数据来源', options.sources, state.filters.sources)}
                </div>
              </div>
            </div>
          </div>
          <div class="db-top-right">
            <div class="db-top-query-card">
              <div class="db-top-query-title">文本输入模式</div>
              <div class="db-top-query-subtitle">预留给类案检索、向量召回和复数字段联合检索</div>
              <div class="db-top-query-mode-row">
                ${Object.entries(QUERY_MODE_LABELS).map(([key, label]) => `
                  <button type="button" class="db-top-query-mode-btn ${activeQueryMode === key ? 'active' : ''}" data-query-mode="${key}">
                    ${label}
                  </button>
                `).join('')}
              </div>
              <textarea id="dbVectorQueryInput" class="db-top-query-input" placeholder="输入类案描述、检索意图或多个字段组合条件，例如：&#10;走私普通货物、物品罪 二审 主从犯 量刑差异&#10;&#10;这里先保留为文本输入工作区，后续接入向量计算逻辑。">${escapeHtml(state.ui.vectorQueryText || '')}</textarea>
              <div class="db-top-query-actions">
                <button type="button" class="db-top-query-btn" data-action="vector-query-placeholder">运行入口预留</button>
                <span class="db-top-query-hint">${escapeHtml(state.ui.vectorQueryStatus || '待输入检索描述')}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    requestAnimationFrame(() => {
      if (!this.container) return;
      this.store.update('layout', { topFiltersHeightPx: this.container.offsetHeight });
    });
  }
}
