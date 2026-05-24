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

import { deleteSavedCase } from '../../shared/api/backend.js';

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
            <div class="db-terminal-header" style="display:flex; justify-content:space-between; align-items:center;">
              <div>
                <div class="db-terminal-title">案件列表</div>
                <div class="db-terminal-subtitle">左侧列表保持与当前筛选结果同步</div>
              </div>
              <label class="db-multiselect-toggle" style="display:flex; align-items:center; gap:6px; cursor:pointer; font-size:12px; color:#475569;">
                <input type="checkbox" id="dbToggleMultiSelect" />
                <span>多选模式</span>
              </label>
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
                <button type="button" class="db-terminal-tab" data-middle-tab="retrieval">检索资产</button>
                <button type="button" class="db-terminal-tab" data-middle-tab="compare">对比结果</button>
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
                <button type="button" class="db-terminal-tab" data-right-tab="thinking">类案思考</button>
              </div>
              <div class="db-terminal-subtitle">右侧展示结构摘要与辅助信息</div>
            </div>
            <div id="dbRightPane" class="db-terminal-content"></div>
          </section>
        </div>
      </div>
    `;
  }

  async deleteCase(rowId) {
    try {
      this.store.update('ui', { loading: true });
      await deleteSavedCase(rowId);
      // Trigger a global event or store update so main.database.js can reload indexes
      window.dispatchEvent(new CustomEvent('database-case-deleted'));
    } catch (err) {
      console.error(err);
      alert('删除失败: ' + err.message);
    } finally {
      this.store.update('ui', { loading: false });
    }
  }

  toggleCaseSelection(caseKey, isMulti = false) {
    const state = this.store.getState();
    const isAll = !caseKey || caseKey === 'all';
    
    if (isAll) {
      this.store.update('selection', {
        activeCaseKey: null,
        selectedCaseKeys: [],
        activeMiddleCaseKey: null,
        activeNodeId: null,
        activeEdgeId: null,
        activeItem: null
      });
      this.store.update('panels', { detailOpen: false });
      return;
    }

    const entry = state.data.casesIndex.find(item => item.caseKey === caseKey);
    if (!entry) return;

    let nextSelected = [...(state.selection.selectedCaseKeys || [])];
    
    if (isMulti || state.selection.multiSelectMode) {
      if (nextSelected.includes(caseKey)) {
        nextSelected = nextSelected.filter(k => k !== caseKey);
      } else {
        nextSelected.push(caseKey);
      }
    } else {
      nextSelected = [caseKey];
    }

    const nextActiveKey = nextSelected.length > 0 ? nextSelected[nextSelected.length - 1] : null;
    const nextMiddleKey = nextSelected.includes(state.selection.activeMiddleCaseKey) 
      ? state.selection.activeMiddleCaseKey 
      : nextActiveKey;
    const nextEntry = nextActiveKey ? state.data.casesIndex.find(item => item.caseKey === nextActiveKey) : null;

    this.store.update('selection', {
      activeCaseKey: nextActiveKey,
      selectedCaseKeys: nextSelected,
      activeMiddleCaseKey: nextMiddleKey,
      activeNodeId: nextActiveKey,
      activeEdgeId: null,
      activeItem: nextEntry ? { kind: 'case', ...nextEntry } : null
    });
    
    if (nextEntry) {
      this.store.update('panels', { detailOpen: true });
    } else {
      this.store.update('panels', { detailOpen: false });
    }
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

      const multiSelectToggle = event.target.closest('#dbToggleMultiSelect');
      if (multiSelectToggle) {
        this.store.update('selection', { multiSelectMode: multiSelectToggle.checked });
        return;
      }

      const deleteBtn = event.target.closest('[data-action="delete-case"]');
      if (deleteBtn) {
        event.stopPropagation();
        const caseItem = deleteBtn.closest('[data-case-key]');
        if (caseItem) {
          const caseKey = caseItem.getAttribute('data-case-key');
          const entry = this.store.getState().data.casesIndex.find(item => item.caseKey === caseKey);
          if (entry && confirm(`确定要删除案例 "${entry.case_name || entry.row_id}" 的所有数据吗？`)) {
            this.deleteCase(entry.row_id);
          }
        }
        return;
      }

      const middleNavPill = event.target.closest('.db-middle-nav-pill');
      if (middleNavPill) {
        this.store.update('selection', { activeMiddleCaseKey: middleNavPill.getAttribute('data-case-key') });
        return;
      }

      const caseItem = event.target.closest('[data-case-key]');
      if (caseItem) {
        const isMulti = event.ctrlKey || event.metaKey;
        this.toggleCaseSelection(caseItem.getAttribute('data-case-key'), isMulti);
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
      const isSelected = (state.selection.selectedCaseKeys || []).includes(entry.caseKey) || state.selection.activeCaseKey === entry.caseKey;
      const showCheckbox = state.selection.multiSelectMode;
      
      return `
        <div class="db-case-item ${isSelected ? 'active' : ''}" data-case-key="${escapeHtml(entry.caseKey)}" style="display:flex; align-items:flex-start;">
          ${showCheckbox ? `
          <div style="margin-right: 12px; display:flex; align-items:center; padding-top:2px;">
            <input type="checkbox" ${isSelected ? 'checked' : ''} style="pointer-events:none; cursor:pointer;" />
          </div>
          ` : ''}
          <div style="flex:1 1 0%; min-width:0; width:100%; overflow:hidden;">
            <div class="db-case-title-row" style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px; width:100%;">
              <div class="db-case-title" style="flex:1 1 0%; min-width:0; display:block; overflow-wrap:break-word; word-break:normal; white-space:normal;">${escapeHtml(entry.case_name || entry.row_id)}</div>
              ${entry.recordSource === 'saved' ? `<button class="db-case-del-btn" data-action="delete-case" title="删除案例" style="background:transparent;border:none;cursor:pointer;color:#ef4444;font-size:14px;padding:0 4px;flex-shrink:0;">🗑</button>` : ''}
            </div>
            <div class="db-case-tags" style="margin-top:4px;">
              <span class="db-case-tag">${escapeHtml(meta.source || entry.source || '未知来源')}</span>
              ${entry.version > 1 ? `<span class="db-case-tag db-case-tag-version">v${escapeHtml(String(entry.version))}</span>` : ''}
              ${stats.facts ? `<span class="db-case-tag db-case-tag-metric">facts ${escapeHtml(String(stats.facts))}</span>` : ''}
              ${stats.relations ? `<span class="db-case-tag db-case-tag-metric">rels ${escapeHtml(String(stats.relations))}</span>` : ''}
            </div>
            <div class="db-case-meta">#${escapeHtml(entry.row_id)} · ${escapeHtml(getCaseTypeText(entry))}</div>
            <div class="db-case-meta">${escapeHtml(trialLevels)} · 裁判年份 ${escapeHtml(judgmentYears)}</div>
          </div>
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
    let subNavHtml = '';
    let targetCaseKey = state.selection.activeCaseKey;

    if (state.selection.multiSelectMode && state.selection.selectedCaseKeys?.length > 1) {
      targetCaseKey = state.selection.activeMiddleCaseKey || state.selection.selectedCaseKeys[0];
      
      const pills = state.selection.selectedCaseKeys.map(k => {
        const c = state.data.casesIndex.find(item => item.caseKey === k);
        const name = c ? (c.case_name || c.row_id).substring(0, 8) : k;
        const isActive = k === targetCaseKey;
        return `<div class="db-middle-nav-pill ${isActive ? 'active' : ''}" data-case-key="${escapeHtml(k)}" style="padding:4px 10px; border-radius:12px; font-size:12px; cursor:pointer; background:${isActive ? '#e0f2fe' : '#f1f5f9'}; color:${isActive ? '#0284c7' : '#64748b'}; border:1px solid ${isActive ? '#bae6fd' : '#e2e8f0'}; white-space:nowrap;">${escapeHtml(name)}</div>`;
      }).join('');
      
      subNavHtml = `<div style="display:flex; gap:8px; padding:8px 16px; border-bottom:1px solid #e2e8f0; background:#f8fafc; overflow-x:auto;">
        <span style="font-size:12px; color:#94a3b8; display:flex; align-items:center;">多案视图:</span>
        ${pills}
      </div>`;
    }

    const active = targetCaseKey ? state.data.casesIndex.find(item => item.caseKey === targetCaseKey) : null;
    
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

    let contentHtml = '';

    if (state.panels.middleTab === 'compare') {
      contentHtml = `<div class="db-empty" style="flex-direction:column; gap:12px;">
        <div style="font-size:24px;">⚖️</div>
        <div style="color:#1e293b; font-weight:bold;">深度对比结果 (开发中)</div>
        <div style="font-size:13px; max-width:400px; line-height:1.5;">利用大模型对多个案件的结构化图谱进行交叉比对，自动生成包含事实差异、证据采信异同、法条适用辨析的深度报告。</div>
      </div>`;
    } else if (state.panels.middleTab === 'parse') {
      contentHtml = parseData
        ? `<pre class="db-raw-pre">${escapeHtml(JSON.stringify(parseData, null, 2))}</pre>`
        : '<div class="db-empty">当前案例暂无解析数据</div>';
    } else if (state.panels.middleTab === 'eval') {
      const evalPayload = {
        parse_eval: parseEval || null,
        ontology_eval: ontologyEval || null
      };
      contentHtml = (parseEval || ontologyEval)
        ? `<pre class="db-raw-pre">${escapeHtml(JSON.stringify(evalPayload, null, 2))}</pre>`
        : '<div class="db-empty">当前案例暂无评估结果</div>';
    } else if (state.panels.middleTab === 'retrieval') {
      const retrievalBundle = detail?.retrieval_bundle || detail?.raw_record?.retrieval_bundle || null;
      if (!retrievalBundle) {
        contentHtml = '<div class="db-empty">当前案例暂无检索资产数据，请先在解析工作台生成并保存。</div>';
      } else {
        const entries = retrievalBundle.entries || [];
        const stats = retrievalBundle.stats || {};
        
        let html = `<div style="padding: 16px;">
          <div style="margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0;">
            <h3 style="margin: 0 0 8px 0; color: #0f172a; font-size: 14px;">检索资产摘要 (Bundle: ${escapeHtml(retrievalBundle.bundle_id || '')})</h3>
            <div style="display:flex; gap: 12px; font-size: 12px; color: #64748b;">
              <span>总条目数: <b>${entries.length}</b></span>
              <span>已写入: <b style="color:#16a34a;">${stats.written_count || 0}</b></span>
              <span>来源版本: <b>${escapeHtml(retrievalBundle.source_parse_version_id || 'v0')}</b></span>
            </div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 12px;">
        `;
        
        entries.forEach((entry, idx) => {
          const title = entry.meta_header?.title || entry.primary_entity?.entity_name || `条目 ${idx + 1}`;
          const viewType = entry.entry_type || '未知视角';
          const isWritten = entry.write_state?.written;
          
          html += `
            <div style="border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; background: #f8fafc;">
              <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
                <div style="font-weight: bold; color: #1e293b; font-size: 13px;">${escapeHtml(title)}</div>
                <div style="display:flex; gap: 6px;">
                  <span style="background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-size: 11px;">${escapeHtml(viewType)}</span>
                  ${isWritten ? `<span style="background: #dcfce7; color: #166534; padding: 2px 6px; border-radius: 4px; font-size: 11px;">已写入</span>` : ''}
                </div>
              </div>
              <div style="font-size: 12px; color: #475569; margin-bottom: 8px; line-height: 1.5;">
                ${escapeHtml(entry.exact_payload?.retrieval_text || '无正文内容').substring(0, 150)}...
              </div>
              <details style="font-size: 11px;">
                <summary style="cursor: pointer; color: #3b82f6;">查看完整 JSON</summary>
                <pre style="margin-top: 8px; padding: 8px; background: #f1f5f9; border-radius: 4px; overflow-x: auto; color: #334155;">${escapeHtml(JSON.stringify(entry, null, 2))}</pre>
              </details>
            </div>
          `;
        });
        
        html += `</div></div>`;
        contentHtml = html;
      }
    } else {
      contentHtml = rawText
        ? `<pre class="db-raw-pre">${escapeHtml(rawText)}</pre>`
        : `<div class="db-empty">该案例的原始长文本未保存或已丢失。</div>`;
    }

    return `<div style="display:flex; flex-direction:column; height:100%; overflow:hidden;">
      ${subNavHtml}
      <div style="flex:1; overflow:auto;">${contentHtml}</div>
    </div>`;
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

  renderThinkingPane(state) {
    return `
      <div style="padding:16px; display:flex; flex-direction:column; gap:16px; height:100%; overflow:hidden;">
        <div style="font-weight:bold; color:#0f172a; font-size:14px; border-bottom:1px solid #e2e8f0; padding-bottom:8px;">类案思考视角配置</div>
        
        <div style="display:flex; flex-direction:column; gap:12px; overflow-y:auto; padding-right:8px;">
          <div style="font-size:12px; color:#475569;">选择您希望对比的角度：</div>
          
          <label style="display:flex; align-items:center; gap:8px; cursor:pointer;">
            <input type="checkbox" checked style="accent-color:#2563eb;" />
            <span style="font-size:13px; color:#1e293b;">⚖️ 法条适用异同</span>
          </label>
          <div style="padding-left:24px; font-size:11px; color:#94a3b8; line-height:1.4;">对比不同案件在认定同一事实时，是否援引了不同的法律条款或司法解释。</div>
          
          <label style="display:flex; align-items:center; gap:8px; cursor:pointer;">
            <input type="checkbox" checked style="accent-color:#2563eb;" />
            <span style="font-size:13px; color:#1e293b;">🧩 构成要件满足度</span>
          </label>
          <div style="padding-left:24px; font-size:11px; color:#94a3b8; line-height:1.4;">分析各案件在具体法条构成要件（如：主观故意、客观行为）上的事实填补差异。</div>

          <label style="display:flex; align-items:center; gap:8px; cursor:pointer;">
            <input type="checkbox" style="accent-color:#2563eb;" />
            <span style="font-size:13px; color:#1e293b;">🧾 证据采信与证明力</span>
          </label>
          <div style="padding-left:24px; font-size:11px; color:#94a3b8; line-height:1.4;">挖掘针对类似争议焦点，不同法院对某类证据（如：电子证据）的采信倾向差异。</div>
          
          <label style="display:flex; align-items:center; gap:8px; cursor:pointer;">
            <input type="checkbox" style="accent-color:#2563eb;" />
            <span style="font-size:13px; color:#1e293b;">💰 裁判尺度偏差</span>
          </label>
          <div style="padding-left:24px; font-size:11px; color:#94a3b8; line-height:1.4;">量化分析相似度高的案件在最终裁判结果（如：量刑、赔偿金额）上的偏离度。</div>
        </div>

        <button style="margin-top:auto; padding:10px; border:none; border-radius:6px; background:#2563eb; color:white; font-weight:bold; cursor:pointer; box-shadow:0 1px 2px rgba(0,0,0,0.05);">生成深度思考报告 (开发中)</button>
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
    const multiSelectToggle = this.container.querySelector('#dbToggleMultiSelect');

    if (multiSelectToggle) multiSelectToggle.checked = Boolean(state.selection.multiSelectMode);

    if (casesPane) casesPane.innerHTML = this.renderCases(state);
    if (middlePane) middlePane.innerHTML = this.renderMiddlePane(state);
    if (rightPane) {
      if (state.panels.rightTab === 'thinking') {
        rightPane.innerHTML = this.renderThinkingPane(state);
      } else if (state.panels.rightTab === 'versions') {
        rightPane.innerHTML = this.renderVersions(state);
      } else {
        rightPane.innerHTML = this.renderSummaryPane(state);
      }
    }
    if (status) status.textContent = state.ui.statusText || '就绪';
  }
}
