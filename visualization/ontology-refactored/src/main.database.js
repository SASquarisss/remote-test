import { fetchAdminStaticCase, fetchAdminStaticCases, fetchCasesIndex, fetchSavedCase } from './shared/api/backend.js';
import { databaseStore as store } from './shared/store/databaseStore.js';
import { TopNavBar } from './shared/chrome/TopNavBar.js';
import { ControlsPanel } from './shared/chrome/ControlsPanel.js';
import { DetailPanel } from './shared/panels/DetailPanel.js';
import { DatabaseGraph } from './database/components/DatabaseGraph.js';
import { DatabaseBottomPanel } from './database/components/DatabaseBottomPanel.js';
import { DatabaseSchemaPanel } from './database/components/DatabaseSchemaPanel.js';
import { DatabaseTopFilters } from './database/components/DatabaseTopFilters.js';
import { decorateSavedCases, decorateStaticCases, getActiveCaseEntry, getFilteredCases, getVisibleCases, mergeCaseIndexes } from './database/model/selectors.js';
import { escapeHtml } from './shared/utils/formatter.js';

function getCaseTypeText(meta = {}, fallbackType = '') {
  const categories = meta.case_categories || [];
  const reasons = meta.case_reasons || [];
  return [...categories, ...reasons, ...(fallbackType ? [fallbackType] : [])].filter(Boolean).join(' / ') || '未标注';
}

function getYearText(meta = {}) {
  const judgmentYears = (meta.judgment_years || []).join(' / ') || '未标注';
  const publicationYears = (meta.publication_years || []).join(' / ') || '未标注';
  return { judgmentYears, publicationYears };
}

function buildCaseDetailHtml(item, state) {
  if (!item) {
    return '<div class="detail-empty">暂无可展示信息</div>';
  }

  if (item.kind === 'source') {
    return `
      <div class="detail-section">
        <div class="detail-kicker">来源摘要</div>
        <div class="detail-title">${escapeHtml(item.label)}</div>
        <div class="detail-meta">该来源下共 ${escapeHtml(String(item.caseCount || 0))} 个案例</div>
      </div>
    `;
  }

  const caseKey = item.caseKey || state.selection.activeCaseKey;
  const caseData = caseKey ? state.data.caseDetailMap[caseKey] || null : null;
  const activeEntry = caseKey ? state.data.casesIndex.find(entry => entry.caseKey === caseKey) || null : null;
  const jsonResult = caseData && caseData.json_result ? caseData.json_result : null;
  const topKeys = jsonResult ? Object.keys(jsonResult) : [];
  const meta = (activeEntry && activeEntry.meta) || item.meta || {};
  const { judgmentYears, publicationYears } = getYearText(meta);
  const trialLevels = (meta.trial_levels || []).join(' / ') || '未标注';
  const typeLabels = getCaseTypeText(meta, item.case_type || activeEntry?.case_type || '');

  if (item.kind === 'edge') {
    return `
      <div class="detail-section">
        <div class="detail-kicker">关系摘要</div>
        <div class="detail-title">${escapeHtml(item.label || item.relationType || '关联关系')}</div>
        <div class="detail-meta">#${escapeHtml(item.rowId || activeEntry?.row_id || '')} · ${escapeHtml(activeEntry?.case_name || item.caseName || '')}</div>
      </div>
      <div class="detail-section">
        <div class="detail-subtitle">关系详情</div>
        <div class="detail-kv"><strong>来源节点</strong><span>${escapeHtml(item.from || '')}</span></div>
        <div class="detail-kv"><strong>目标节点</strong><span>${escapeHtml(item.to || '')}</span></div>
        <div class="detail-kv"><strong>关系类型</strong><span>${escapeHtml(item.relationType || item.label || '关联')}</span></div>
      </div>
    `;
  }

  if (item.kind === 'node') {
    return `
      <div class="detail-section">
        <div class="detail-kicker">图谱节点</div>
        <div class="detail-title">${escapeHtml(item.fullLabel || item.label || '未命名节点')}</div>
        <div class="detail-meta">${escapeHtml(item.nodeType || 'Unknown')} · ${escapeHtml(activeEntry?.case_name || item.caseName || '')}</div>
      </div>
      <div class="detail-section">
        <div class="detail-subtitle">节点详情</div>
        <div class="detail-kv"><strong>所属案例</strong><span>${escapeHtml(activeEntry?.case_name || item.caseName || '未命名案例')}</span></div>
        <div class="detail-kv"><strong>案例编号</strong><span>${escapeHtml(activeEntry?.row_id || item.rowId || '')}</span></div>
        <div class="detail-kv"><strong>节点类型</strong><span>${escapeHtml(item.nodeType || 'Unknown')}</span></div>
        <div class="detail-kv"><strong>已加载结构</strong><span>${caseData ? '是' : '否'}</span></div>
      </div>
    `;
  }

  return `
    <div class="detail-section">
      <div class="detail-kicker">案例摘要</div>
      <div class="detail-title">${escapeHtml(item.case_name || item.label || '未命名案例')}</div>
      <div class="detail-meta">#${escapeHtml(item.row_id || '')} · ${escapeHtml(typeLabels)} · ${escapeHtml(meta.source || item.source || 'unknown')}</div>
    </div>
    <div class="detail-section">
      <div class="detail-subtitle">基本信息</div>
      <div class="detail-kv"><strong>数据来源</strong><span>${escapeHtml(meta.source || item.source || 'unknown')}</span></div>
      <div class="detail-kv"><strong>版本</strong><span>v${escapeHtml(String(item.version || 1))}</span></div>
      <div class="detail-kv"><strong>案件类型</strong><span>${escapeHtml(typeLabels)}</span></div>
      <div class="detail-kv"><strong>审级</strong><span>${escapeHtml(trialLevels)}</span></div>
      <div class="detail-kv"><strong>裁判年份</strong><span>${escapeHtml(judgmentYears)}</span></div>
      <div class="detail-kv"><strong>发布年份</strong><span>${escapeHtml(publicationYears)}</span></div>
      <div class="detail-kv"><strong>加载状态</strong><span>${caseData ? '已加载详细数据' : '仅索引数据'}</span></div>
    </div>
    <div class="detail-section">
      <div class="detail-subtitle">图谱摘要</div>
      <div class="detail-kv"><strong>可用顶层键</strong><span>${escapeHtml(topKeys.length ? topKeys.join(', ') : '等待加载')}</span></div>
    </div>
  `;
}

function updateStatus(text, error = null) {
  store.update('ui', { statusText: text, error });
}

function getTopFiltersHeight(state) {
  if (typeof state.layout?.topFiltersHeightPx === 'number' && state.layout.topFiltersHeightPx > 0) {
    return state.layout.topFiltersHeightPx;
  }
  const element = document.getElementById('databaseTopFilters');
  return element?.offsetHeight || 72;
}

function getTerminalHeight(state) {
  if (state.layout?.terminalCollapsed) return 28;
  if (typeof state.layout?.terminalHeightPx === 'number' && state.layout.terminalHeightPx > 0) {
    return state.layout.terminalHeightPx;
  }
  const element = document.getElementById('databaseBottomPanel');
  return element?.offsetHeight || 280;
}

async function loadCaseIndexes({ silent = false } = {}) {
  if (!silent) {
    store.update('ui', { loading: true, statusText: '正在加载案例索引...', error: null });
  }

  try {
    const [staticResult, savedResult] = await Promise.allSettled([
      fetchAdminStaticCases(),
      fetchCasesIndex()
    ]);
    const staticCases = staticResult.status === 'fulfilled' ? staticResult.value : [];
    const savedCases = savedResult.status === 'fulfilled' ? savedResult.value : [];
    const merged = mergeCaseIndexes(decorateStaticCases(staticCases), decorateSavedCases(savedCases));
    const state = store.getState();
    const activeCaseKey = state.selection.activeCaseKey;
    const activeStillExists = activeCaseKey && merged.some(entry => entry.caseKey === activeCaseKey);
    const staticError = staticResult.status === 'rejected' ? staticResult.reason?.message || '静态案例加载失败' : '';
    const savedError = savedResult.status === 'rejected' ? savedResult.reason?.message || '保存案例加载失败' : '';
    const errorMessage = [savedError, staticError].filter(Boolean).join('；');

    store.update('data', { casesIndex: merged });

    if (activeCaseKey && !activeStillExists) {
      store.update('selection', {
        activeCaseKey: null,
        activeNodeId: null,
        activeEdgeId: null,
        activeItem: null
      });
      store.update('panels', { detailOpen: false });
    }

    store.update('ui', {
      loading: false,
      error: errorMessage || null,
      statusText: errorMessage
        ? `已加载 ${merged.length} 个案例索引（部分来源失败：${errorMessage}）`
        : `已加载 ${merged.length} 个案例索引`
    });
  } catch (error) {
    store.update('ui', {
      loading: false,
      error: error.message,
      statusText: `加载失败：${error.message}`
    });
  }
}

async function hydrateSelectedCases(state) {
  const selectedKeys = state.selection.selectedCaseKeys || [];
  const activeKey = state.selection.activeCaseKey;
  
  const keysToLoad = new Set();
  if (activeKey) keysToLoad.add(activeKey);
  selectedKeys.forEach(k => keysToLoad.add(k));

  if (keysToLoad.size === 0) return;

  const currentMap = state.data.caseDetailMap;
  const missingKeys = Array.from(keysToLoad).filter(k => !currentMap[k]);

  if (missingKeys.length === 0) return;

  store.update('ui', { loading: true });
  try {
    const nextMap = { ...currentMap };
    
    // 并行请求所有缺失的数据
    const promises = missingKeys.map(async (caseKey) => {
      const entry = state.data.casesIndex.find(e => e.caseKey === caseKey);
      if (!entry) return;
      const detail = entry.recordSource === 'static'
        ? await fetchAdminStaticCase(entry.row_id, entry.version)
        : await fetchSavedCase(entry.row_id);
      nextMap[caseKey] = detail;
    });

    await Promise.all(promises);
    
    store.update('data', { caseDetailMap: nextMap });
    updateStatus(`已加载 ${missingKeys.length} 个案例详情`);
  } catch (error) {
    updateStatus(`批量加载案例详情失败：${error.message}`, error.message);
  } finally {
    store.update('ui', { loading: false });
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const topNavBar = new TopNavBar({
    productName: 'legal_ontology_database',
    subtitle: '案例库浏览与结构图谱工作台',
    stats: [
      { key: 'cases', label: '案例' },
      { key: 'visible', label: '当前可见' },
      { key: 'sources', label: '来源' }
    ],
    actions: [
      { key: 'toggle-schema', label: '打开本体导航' }
    ]
  });

  const graph = new DatabaseGraph({
    store,
    containerId: 'databaseGraphView',
    onStatsChange: stats => topNavBar.updateStats(stats)
  });
  new ControlsPanel({ networkProvider: () => graph.network, containerId: 'databaseApp', offset: { left: 20, bottom: 244 } });
  new DetailPanel({
    store,
    panelId: 'databaseDetailPanel',
    titleId: 'databaseDetailPanelTitle',
    bodyId: 'databaseDetailPanelBody',
    closeId: 'databaseDetailPanelClose',
    titleResolver: item => item && (item.case_name || item.fullLabel || item.label || item.title || '详细信息'),
    contentRenderer: buildCaseDetailHtml,
    isOpenSelector: state => state.panels.detailOpen,
    itemSelector: state => state.selection.activeItem,
    onClose: () => store.update('panels', { detailOpen: false })
  });
  new DatabaseTopFilters({
    store,
    containerId: 'databaseTopFilters',
    onRefresh: () => loadCaseIndexes()
  });
  new DatabaseBottomPanel({ store, containerId: 'databaseBottomPanel' });
  new DatabaseSchemaPanel({ store, containerId: 'databaseSchemaPanel' });

  topNavBar.container?.addEventListener('click', event => {
    const action = event.target.closest('[data-action-key="toggle-schema"]');
    if (!action) return;
    const current = store.getState().panels.schemaOpen;
    store.update('panels', { schemaOpen: !current });
  });

  let lastLayoutSignature = '';
  const applyDatabaseLayout = (state) => {
    const topHeight = getTopFiltersHeight(state);
    const terminalHeight = getTerminalHeight(state);
    const signature = [topHeight, terminalHeight].join('|');
    if (signature === lastLayoutSignature) return;
    lastLayoutSignature = signature;

    const app = document.getElementById('databaseApp');
    if (!app) return;
    app.style.setProperty('--db-top-filters-height', `${topHeight}px`);
    app.style.setProperty('--db-terminal-height', `${terminalHeight}px`);
    app.style.setProperty('--db-schema-top', `${topHeight + 16}px`);
  };

  let lastSelectedSignature = '';
  store.subscribe(state => {
    applyDatabaseLayout(state);
    const actionButton = topNavBar.container?.querySelector('[data-action-key="toggle-schema"]');
    if (actionButton) {
      actionButton.textContent = state.panels.schemaOpen ? '收起本体导航' : '打开本体导航';
    }
    
    // 监听多选或单选变化，触发批量加载
    const selectedKeys = state.selection.selectedCaseKeys || [];
    const activeKey = state.selection.activeCaseKey;
    const signature = [activeKey, ...selectedKeys].filter(Boolean).sort().join('|');
    
    if (signature && signature !== lastSelectedSignature) {
      lastSelectedSignature = signature;
      hydrateSelectedCases(state);
    } else if (!signature) {
      lastSelectedSignature = '';
    }
  });

  store.subscribe(state => {
    const filtered = getFilteredCases(state.data.casesIndex, state.filters);
    const visible = getVisibleCases(filtered, state.graph.browseMode);
    updateStatus(`已加载 ${state.data.casesIndex.length} 个案例索引；当前匹配 ${filtered.length} 个，图谱展示 ${visible.length} 个。`, state.ui.error);
  });

  window.addEventListener('focus', () => {
    loadCaseIndexes({ silent: true });
  });

  window.addEventListener('resize', () => {
    lastLayoutSignature = '';
    applyDatabaseLayout(store.getState());
  });

  await loadCaseIndexes();
  applyDatabaseLayout(store.getState());
});
