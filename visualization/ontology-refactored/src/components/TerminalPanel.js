import { store } from '../store/index.js';
import { safeGetElement } from '../utils/dom.js';
import { escapeHtml } from '../utils/formatter.js';
import {
  parseEnhancement,
  parseQuality,
  saveResult,
  ontologyEvaluate,
  previewEnhancementMerge,
  mergeEnhancementResult,
  buildRetrievalBundle,
  updateRetrievalEntry,
  reembedRetrievalBundle,
  writeRetrievalBundle,
} from '../api/backend.js';

export class TerminalPanel {
  constructor() {
    this.panel = safeGetElement('parseTerminal');
    this.container = document.getElementById('termBody'); // use termBody as container
    this.dragHandle = safeGetElement('termDragHandle');
    this.closeBtn = safeGetElement('btnTermClose');
    this.expandedHeightPx = null;
    
    this.ensureTerminalUI();
    
    this.inputArea = safeGetElement('termInputArea');
    this.parseBtn = safeGetElement('btnTermParse');
    this.saveBtn = document.getElementById('btnTermSave');
    this.saveBtnBottom = safeGetElement('btnTermSaveBottom');
    this.clearBtn = safeGetElement('btnTermClear');
    this.evalBtn = safeGetElement('btnTermEvaluate');
    this.enhanceBtn = safeGetElement('btnTermEnhance');
    this.statusArea = safeGetElement('termStatusArea');
    
    this.lastResult = null;
    this.lastQualityResult = null;
    this.lastEvalResult = null;
    this.lastEnhancementResult = null;
    this.lastEnhancementRuns = [];
    this.lastRetrievalBundle = null;
    this.lastRetrievalWriteManifest = null;
    this.isEnhancing = false;
    this.lastTerminalLocateTimestamp = null;
    this.jsonChangedKeys = new Set();
    
    this.bindEvents();
    this.syncLayoutState();
    
    // Listen for cross-graph focus to update issues view
    store.subscribe(state => {
      if (state.selectedGraph === 'parse' && state.selectedNodeId && this.lastQualityResult) {
        // Rerender issues to update the focus section
        this.renderQualityIssues(this.lastQualityResult, state.parseNodeData);
      }
      
      // Listen for locate events to highlight JSON tree
      if (state.locateTarget && state.locateTarget.timestamp !== this.lastTerminalLocateTimestamp) {
        this.lastTerminalLocateTimestamp = state.locateTarget.timestamp;
        if (state.locateTarget.sourceGraph === 'parse') {
          this.highlightJsonKey(state.locateTarget.typeKey);
        }
      }
    });
  }

  ensureTerminalUI() {
    if (this.panel) {
      this.panel.style.display = 'flex';
      this.panel.style.flexDirection = 'column';
    }
    const body = document.getElementById('termBody');
    if (body) {
      body.style.display = 'flex';
      body.style.flex = '1';
      body.style.overflow = 'hidden';
      body.style.position = 'relative';
      
      if (!document.getElementById('termControls')) {
          body.insertAdjacentHTML('afterbegin', `
            <div id="termControls" class="term-col term-col-left" style="width: 30%; flex: none; display: flex; flex-direction: column; height: 100%; box-sizing: border-box;">
              <div class="term-input-area" style="flex: 1; display: flex; flex-direction: column; padding: 12px; min-height: 0; box-sizing: border-box;">
                <textarea id="termInputArea" placeholder="在此粘贴法律文本（原始案件信息、裁判文书等任意文本）\n\n例如：\n人民法院案例库入库编号: 2023-09-3-029-028\n案例名称: 某某公司诉某某局行政纠纷案\n案由: 行政-商标相关行政案件\n基本案情: ……\n裁判理由: ……\n相关法条: 《中华人民共和国商标法》第四十四条" style="flex: 1; resize: none; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; font-size: 13px; font-family: monospace; outline: none; box-sizing: border-box;"></textarea>
                <div class="term-btn-row" style="display: flex; gap: 8px; margin-top: 12px; align-items: center; justify-content: space-between; flex-shrink: 0;">
                  <div class="term-input-row" style="display:flex;gap:8px;align-items:center;">
                    <button class="btn-parse" id="btnTermParse" style="padding: 8px 24px; border: none; border-radius: 6px; background: #2980b9; color: #fff; font-weight: bold; cursor: pointer;">⚡ 一键解析</button>
                    <button class="btn-clear" id="btnTermClear" title="清空原文" style="padding: 8px 16px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; color: #64748b; cursor: pointer;">🗑 清空</button>
                  </div>
                  <span class="term-status" id="termStatusArea" style="font-size: 12px; color: #94a3b8;">等待输入</span>
                </div>
              </div>
            </div>
          
          <div class="term-splitter" id="splitterLeft"></div>
          
          <div id="termJsonColumn" class="term-col term-col-middle" style="width: 42%; flex: none; background: #fff;">
            <div class="term-col-header" style="border-bottom: 1px solid #e0e0e0; background: #fbfcfe;">
              <div class="term-tab-group" id="jsonTabGroup">
                <span class="term-tab active" data-target="termJsonArea">
                  <span class="term-tab-label">📄 解析数据</span>
                </span>
                <span class="term-tab" data-target="termEnhanceTabContent">
                  <span class="term-tab-label">✨ 增量解析数据</span>
                </span>
                <span class="term-tab" data-target="termRetrievalTabContent">
                  <span class="term-tab-label">🧠 检索资产</span>
                </span>
              </div>
            </div>
            <div style="flex: 1; position: relative; overflow: hidden; display: flex; flex-direction: column;">
              <div class="term-json-area term-content-pane" id="termJsonArea" style="flex: 1; display: flex; flex-direction: row; min-width:0;">
                <div id="termJsonMain" style="flex:1; min-width:0; display:flex; flex-direction:column; position:relative;">
                  <div class="term-json-placeholder" id="termJsonPlaceholder">等待解析结果...</div>
                  <div id="termJsonChangeNote" style="display:none; padding:8px 10px; border-bottom:1px solid #e5edf7; background:#f8fbff; font-size:12px; color:#2563eb;"></div>
                  <div id="termJsonTree" style="display:none; font-family: monospace; font-size: 12px; line-height: 1.5; color: #333; padding: 10px; flex: 1; overflow: auto;"></div>
                </div>
                <div id="termJsonVersionRail" style="display:none; width:200px; flex:none; border-left:1px solid #e5e7eb; background:#fbfcfe; overflow:auto;"></div>
              </div>
              <div id="termEnhanceTabContent" class="term-content-pane" style="display: none; flex: 1; flex-direction: column; overflow: hidden; background: #fff;">
                <div id="termEnhancePlaceholder" style="padding: 16px; color: #94a3b8;">等待本体论评估后进行增量解析...</div>
                <div id="termEnhanceMeta" style="display:none; padding: 12px 14px; border-bottom: 1px solid #eef2f7; background: #fafcff;"></div>
                <div id="termEnhanceTree" style="display:none; font-family: monospace; font-size: 13px; line-height: 1.7; color: #1f2937; padding: 14px 16px 18px; flex: 1; overflow: auto;"></div>
              </div>
              <div id="termRetrievalTabContent" class="term-content-pane" style="display: none; flex: 1; flex-direction: column; overflow: hidden; background: #fff;">
                <div id="termRetrievalPane" style="display:flex; flex:1; min-height:0; flex-direction:column;">
                  <div id="termRetrievalPlaceholder" style="padding:16px; color:#94a3b8; display:flex; flex-direction:column; gap:12px; align-items:flex-start;">
                    <div>等待解析结果后生成检索资产...</div>
                    <button data-retrieval-action="build" style="padding:7px 12px;border:none;border-radius:8px;background:#2563eb;color:#fff;cursor:pointer;">生成检索资产</button>
                  </div>
                </div>
              </div>
            </div>
            <div class="term-eval-row">
              <button class="btn-eval" id="btnTermEvaluate" disabled>🔍 本体论评估</button>
              <button class="btn-enhance" id="btnTermEnhance" disabled>✨ 增量解析</button>
              <span class="term-eval-score" id="termEvalScoreArea"></span>
            </div>
          </div>
          
          <div class="term-splitter" id="splitterRight"></div>
          
          <div id="termWorkspace" class="term-col term-col-right" style="flex: 1; min-width: 0; background: #fff;">
            <div class="term-col-header">
              <div class="term-tab-group">
                <span class="term-tab active pending" data-target="termVisContainer">
                  <span class="term-tab-label">📊 图</span>
                  <span class="term-tab-badge" id="tabGraphBadge">待生成</span>
                </span>
                <span class="term-tab" data-target="termIssuesTabContent">
                  <span class="term-tab-label">⚠ 问题</span>
                  <span class="term-tab-badge" id="tabIssuesBadge">待分析</span>
                </span>
                <span class="term-tab" data-target="termEvalTabContent">
                  <span class="term-tab-label">📋 评估</span>
                  <span class="term-tab-badge" id="tabEvalBadge">待评估</span>
                </span>
              </div>
              <span class="term-panel-hint" id="termPanelHint">等待解析结果</span>
            </div>
            <div class="term-graph-mode-bar" id="termGraphModeBar">
              <span class="term-graph-mode-badge" id="termGraphModeBadge">全貌模式</span>
              <span class="term-graph-mode-summary" id="termGraphModeSummary">查看案件整体结构，默认保留全量实体并对结构边降噪。</span>
            </div>
            
            <div id="termWorkspaceContent" style="flex: 1; position: relative; overflow: hidden;">
              <!-- VisContainer moved here dynamically -->
              
              <div id="termIssuesTabContent" class="term-content-pane term-issues-area" style="display: none; position: absolute; inset: 0; background: #fff;">
                <div class="term-tab-scroll" id="termIssuesScroll" style="padding-bottom: 40px;">
                  <div class="term-issues-placeholder" id="termIssuesPlaceholder">等待分析...</div>
                </div>
              </div>
              
              <div id="termEvalTabContent" class="term-content-pane term-eval-area" style="display: none; position: absolute; inset: 0; background: #fff;">
                <div class="term-tab-scroll" id="termEvalScroll">
                  <div class="term-eval-placeholder" id="termEvalPlaceholder">等待评估...</div>
                </div>
              </div>
            </div>
          </div>
        `);
        
        const visContainer = document.getElementById('termVisContainer');
        const workspaceContent = document.getElementById('termWorkspaceContent');
        if (visContainer && workspaceContent) {
          workspaceContent.appendChild(visContainer);
          visContainer.classList.add('term-content-pane');
          visContainer.style.position = 'absolute';
          visContainer.style.inset = '0';
          visContainer.style.display = 'flex';
          visContainer.style.flexDirection = 'column';
          visContainer.style.background = '#fff';
        }
      }

      // Adjust specific DOM attributes after creation
      if (this.container) {
        const termLeft = this.container.querySelector('.term-col-left');
        if (termLeft) {
          termLeft.style.display = 'flex';
          termLeft.style.flexDirection = 'column';
          termLeft.style.height = '100%';
          termLeft.style.minHeight = '0';
        }
      }
    }
  }

  bindEvents() {
    // Horizontal Splitters
    const splitterLeft = document.getElementById('splitterLeft');
    const splitterRight = document.getElementById('splitterRight');
    const colLeft = document.getElementById('termControls');
    const colMiddle = document.getElementById('termJsonColumn');
    
    if (splitterLeft && colLeft && colMiddle) {
      let isDraggingLeft = false;
      splitterLeft.addEventListener('mousedown', () => {
        isDraggingLeft = true;
        splitterLeft.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
      });
      document.addEventListener('mousemove', (e) => {
        if (!isDraggingLeft) return;
        const containerWidth = this.panel.offsetWidth;
        const newLeftWidth = (e.clientX / containerWidth) * 100;
        if (newLeftWidth > 15 && newLeftWidth < 60) {
          colLeft.style.width = `${newLeftWidth}%`;
        }
      });
      document.addEventListener('mouseup', () => {
        if (isDraggingLeft) {
          isDraggingLeft = false;
          splitterLeft.classList.remove('dragging');
          document.body.style.cursor = '';
        }
      });
    }

    if (splitterRight && colLeft && colMiddle) {
      let isDraggingRight = false;
      splitterRight.addEventListener('mousedown', () => {
        isDraggingRight = true;
        splitterRight.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
      });
      document.addEventListener('mousemove', (e) => {
        if (!isDraggingRight) return;
        const containerWidth = this.panel.offsetWidth;
        const leftWidthPx = colLeft.offsetWidth;
        const newMiddleWidth = ((e.clientX - leftWidthPx) / containerWidth) * 100;
        if (newMiddleWidth > 15 && newMiddleWidth < 60) {
          colMiddle.style.width = `${newMiddleWidth}%`;
        }
      });
      document.addEventListener('mouseup', () => {
        if (isDraggingRight) {
          isDraggingRight = false;
          splitterRight.classList.remove('dragging');
          document.body.style.cursor = '';
        }
      });
    }

    if (this.dragHandle) {
      let isDragging = false;
      let startY = 0;
      let startHeight = 0;
      
      this.dragHandle.addEventListener('mousedown', (e) => {
        isDragging = true;
        startY = e.clientY;
        startHeight = this.panel.offsetHeight;
        document.body.style.cursor = 'ns-resize';
      });
      
      document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        const dy = startY - e.clientY;
        const newHeight = Math.max(200, Math.min(window.innerHeight - 100, startHeight + dy));
        this.panel.style.height = `${newHeight}px`;
        this.applyMainViewHeight(newHeight);

        // Force height 100% to fix flex layout issues when resizing
        const termBody = document.getElementById('termBody');
        if (termBody) {
          const termLeft = termBody.querySelector('.term-col-left');
          if (termLeft) {
            termLeft.style.height = '100%';
            termLeft.style.display = 'flex';
            termLeft.style.flexDirection = 'column';
            termLeft.style.minHeight = '0';
          }
        }
      });
      
      document.addEventListener('mouseup', () => {
        if (!isDragging) return;
        isDragging = false;
        document.body.style.cursor = '';
        this.syncLayoutState();
      });
    }

    if (this.closeBtn) {
      this.closeBtn.addEventListener('click', () => {
        if (this.panel && this.panel.classList.contains('expanded')) {
          this.expandedHeightPx = this.panel.offsetHeight || this.expandedHeightPx;
        }
        this.panel.classList.remove('expanded');
        this.panel.classList.add('collapsed');
        const bar = document.getElementById('termCollapsedBar');
        const termPanel = this.panel.querySelector('.terminal-panel');
        const footer = this.panel.querySelector('.term-footer');
        this.panel.style.height = '40px';
        if (bar) bar.style.display = 'flex';
        if (termPanel) termPanel.style.display = 'none';
        if (footer) footer.style.display = 'none';
        this.syncLayoutState();
      });
    }

    const collapsedBar = document.getElementById('termCollapsedBar');
    if (collapsedBar) {
      collapsedBar.addEventListener('click', () => {
        this.panel.classList.add('expanded');
        this.panel.classList.remove('collapsed');
        if (this.expandedHeightPx && this.expandedHeightPx > 40) {
          this.panel.style.height = `${this.expandedHeightPx}px`;
        }
        collapsedBar.style.display = 'none';
        const termPanel = this.panel.querySelector('.terminal-panel');
        const footer = this.panel.querySelector('.term-footer');
        if (termPanel) termPanel.style.display = 'flex';
        if (footer) footer.style.display = 'flex';
        this.syncLayoutState();
      });
    }

    if (this.parseBtn) {
      this.parseBtn.addEventListener('click', () => this.handleParse());
    }

    if (this.clearBtn) {
      this.clearBtn.addEventListener('click', () => {
        if (this.inputArea) this.inputArea.value = '';
      });
    }

    if (this.saveBtn) {
      this.saveBtn.addEventListener('click', () => this.handleSave());
    }
    if (this.saveBtnBottom) {
      this.saveBtnBottom.addEventListener('click', () => this.handleSave());
    }

    if (this.evalBtn) {
      this.evalBtn.addEventListener('click', () => this.handleEvaluate());
    }
    if (this.enhanceBtn) {
      this.enhanceBtn.addEventListener('click', () => this.handleEnhanceParse());
    }

    const versionRail = document.getElementById('termJsonVersionRail');
    if (versionRail) {
      versionRail.addEventListener('click', (e) => {
        const item = e.target.closest('[data-version-id]');
        if (!item) return;
        const versionId = item.getAttribute('data-version-id');
        if (versionId) this.switchVersion(versionId);
      });
    }

    const heightBtns = this.panel?.querySelectorAll('.term-height-btn');
    if (heightBtns) {
      heightBtns.forEach(btn => {
        btn.addEventListener('click', () => {
          heightBtns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const h = btn.getAttribute('data-height');
          const newHeight = (window.innerHeight * parseInt(h, 10)) / 100;
          this.panel.style.height = `${newHeight}px`;
          this.applyMainViewHeight(newHeight);

          // Force height 100% to fix flex layout issues when resizing
          const termBody = document.getElementById('termBody');
          if (termBody) {
            const termLeft = termBody.querySelector('.term-col-left');
            if (termLeft) {
              termLeft.style.height = '100%';
              termLeft.style.display = 'flex';
              termLeft.style.flexDirection = 'column';
              termLeft.style.minHeight = '0';
            }
          }

          this.syncLayoutState();
        });
      });
    }

    // Tabs
    const termBody = document.getElementById('termBody');
    if (termBody) {
      termBody.addEventListener('click', (e) => {
        const tab = e.target.closest('.term-tab');
        if (tab) {
          const targetId = tab.getAttribute('data-target');
          if (targetId) this.switchTab(targetId);
        }
      });
    }
    
    // Delegated event for tree toggle in issues
    const issuesTab = document.getElementById('termIssuesTabContent');
    if (issuesTab) {
      issuesTab.addEventListener('click', (e) => {
        const header = e.target.closest('.qa-cat-header, .qa-ent-header');
        if (header) {
          const targetId = header.getAttribute('data-target');
          const bodyEl = document.getElementById(targetId);
          const toggle = header.querySelector('.qa-toggle');
          if (bodyEl && toggle) {
            const isHidden = bodyEl.style.display === 'none';
            bodyEl.style.display = isHidden ? 'block' : 'none';
            toggle.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(-90deg)';
          }
        }
      });
    }

    const retrievalPane = document.getElementById('termRetrievalPane');
    if (retrievalPane) {
      retrievalPane.addEventListener('click', (e) => {
        const action = e.target.closest('[data-retrieval-action]');
        if (action) {
          const type = action.getAttribute('data-retrieval-action');
          if (type === 'build') this.handleBuildRetrieval(false);
          if (type === 'regenerate') this.handleBuildRetrieval(true);
          if (type === 'save-entry') this.handleSaveRetrievalEntry();
          if (type === 'reembed') this.handleReembedRetrieval();
          if (type === 'write') this.handleWriteRetrieval();
          if (type === 'preview-mode') {
            const mode = action.getAttribute('data-preview-mode');
            if (mode && this.lastRetrievalBundle) {
              store.setState({ retrievalPreviewMode: mode });
              this.persistRetrievalUIState({ previewMode: mode });
              this.renderRetrievalBundle(this.lastRetrievalBundle);
            }
          }
          return;
        }
        const item = e.target.closest('[data-entry-id]');
        if (item) {
          const entryId = item.getAttribute('data-entry-id');
          if (entryId) {
            this.persistRetrievalUIState({ activeEntryId: entryId });
            this.renderRetrievalBundle(this.lastRetrievalBundle, { activeEntryId: entryId });
          }
        }
      });
      retrievalPane.addEventListener('change', (e) => {
        const target = e.target;
        if (target?.id === 'retrievalFilterType' || target?.id === 'retrievalFilterStatus') {
          store.setState({
            retrievalFilters: {
              ...(store.getState().retrievalFilters || {}),
              type: document.getElementById('retrievalFilterType')?.value || 'all',
              status: document.getElementById('retrievalFilterStatus')?.value || 'all',
            }
          });
          this.persistRetrievalUIState({
            filters: {
              ...(store.getState().retrievalFilters || {}),
              type: document.getElementById('retrievalFilterType')?.value || 'all',
              status: document.getElementById('retrievalFilterStatus')?.value || 'all',
            }
          });
          if (this.lastRetrievalBundle) this.renderRetrievalBundle(this.lastRetrievalBundle);
        }
      });
      retrievalPane.addEventListener('input', (e) => {
        const target = e.target;
        if (target?.id === 'retrievalSearchInput') {
          store.setState({
            retrievalFilters: {
              ...(store.getState().retrievalFilters || {}),
              search: target.value || '',
            }
          });
          this.persistRetrievalUIState({
            filters: {
              ...(store.getState().retrievalFilters || {}),
              search: target.value || '',
            }
          });
          if (this.lastRetrievalBundle) this.renderRetrievalBundle(this.lastRetrievalBundle);
        }
      });
    }
  }

  applyMainViewHeight(heightPx) {
    const state = store.getState();
    if (state.workspaceLayoutMode !== 'parse_primary') return;
    const mainView = document.getElementById('kgMainView');
    if (mainView) {
      mainView.style.height = `calc(100vh - ${heightPx}px)`;
    }
  }

  syncLayoutState() {
    if (!this.panel) return;
    const isExpanded = this.panel.classList.contains('expanded');
    const isCollapsed = !isExpanded;
    this.panel.classList.toggle('collapsed', isCollapsed);
    if (isExpanded) {
      this.expandedHeightPx = this.panel.offsetHeight || this.expandedHeightPx;
    }
    store.setState({
      terminalCollapsed: isCollapsed,
      terminalHeightPx: isCollapsed ? 40 : this.panel.offsetHeight
    });
    if (isExpanded) {
      this.notifyGraphTabVisible(false);
    }
  }

  ensureTerminalExpanded() {
    if (this.panel && !this.panel.classList.contains('expanded')) {
      this.panel.classList.add('expanded');
      this.panel.classList.remove('collapsed');
      if (this.expandedHeightPx && this.expandedHeightPx > 40) {
        this.panel.style.height = `${this.expandedHeightPx}px`;
      }
      const bar = document.getElementById('termCollapsedBar');
      const termPanel = this.panel.querySelector('.terminal-panel');
      const footer = this.panel.querySelector('.term-footer');
      if (bar) bar.style.display = 'none';
      if (termPanel) termPanel.style.display = 'flex';
      if (footer) footer.style.display = 'flex';
    }
    this.syncLayoutState();
    this.notifyGraphTabVisible(false);
  }

  notifyGraphTabVisible(fit = false) {
    const activeWorkspaceTab = document.querySelector('#termWorkspace .term-tab.active');
    const activeTarget = activeWorkspaceTab?.getAttribute('data-target');
    if (activeTarget !== 'termVisContainer' && activeTarget !== 'termGraphInfo') return;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        window.dispatchEvent(new CustomEvent('parse-graph-visible', { detail: { fit } }));
      });
    });
  }

  getVersionList() {
    return store.getState().parseVersions || [];
  }

  getActiveVersionId() {
    return store.getState().parseActiveVersionId || 'v0';
  }

  getActiveVersion() {
    return this.getVersionList().find((item) => item?.version_id === this.getActiveVersionId()) || null;
  }

  getCurrentEnhancementRunId() {
    return this.lastEnhancementResult?.run_id || this.lastEnhancementRuns[this.lastEnhancementRuns.length - 1]?.run_id || null;
  }

  syncEnhancementRuns(result) {
    if (!result?.run_id) return;
    const nextRuns = [...(store.getState().parseEnhancementRuns || [])];
    const idx = nextRuns.findIndex((item) => item?.run_id === result.run_id);
    if (idx >= 0) nextRuns[idx] = result;
    else nextRuns.push(result);
    this.lastEnhancementRuns = nextRuns;
    store.setState({ parseEnhancementRuns: nextRuns });
  }

  renderVersionRail(versions = this.getVersionList(), activeVersionId = this.getActiveVersionId()) {
    const host = document.getElementById('termJsonVersionRail');
    if (!host) return;
    if (!Array.isArray(versions) || versions.length <= 1) {
      host.style.display = 'none';
      host.innerHTML = '';
      return;
    }
    host.style.display = 'block';
    host.innerHTML = `
      <div style="padding:10px 12px; border-bottom:1px solid #e5e7eb; font-size:12px; font-weight:700; color:#334155;">
        版本管理
      </div>
      <div style="padding:10px 12px 18px;">
        ${versions.map((version, index) => {
          const summary = version?.change_summary || {};
          const entityCount = Object.values(summary.entity_added || {}).reduce((sum, value) => sum + Number(value || 0), 0)
            + Object.values(summary.entity_updated || {}).reduce((sum, value) => sum + Number(value || 0), 0);
          const relationCount = Object.values(summary.relation_added || {}).reduce((sum, value) => sum + Number(value || 0), 0)
            + Object.values(summary.relation_updated || {}).reduce((sum, value) => sum + Number(value || 0), 0);
          const derivedCount = Object.values(summary.derived_relation_added || {}).reduce((sum, value) => sum + Number(value || 0), 0)
            + Object.values(summary.derived_relation_updated || {}).reduce((sum, value) => sum + Number(value || 0), 0);
          const active = version?.version_id === activeVersionId;
          return `
            <div style="position:relative; padding-left:18px; margin-bottom:${index === versions.length - 1 ? '0' : '14px'};">
              <div style="position:absolute; left:5px; top:0; bottom:-18px; width:2px; background:${active ? '#2563eb' : '#dbeafe'};"></div>
              <div data-version-id="${escapeHtml(version?.version_id || '')}" style="position:relative; cursor:pointer; border:1px solid ${active ? '#93c5fd' : '#e5e7eb'}; background:${active ? '#eff6ff' : '#fff'}; border-radius:10px; padding:10px 10px 9px;">
                <span style="position:absolute; left:-18px; top:12px; width:10px; height:10px; border-radius:999px; background:${active ? '#2563eb' : '#cbd5e1'}; border:2px solid #fff;"></span>
                <div style="font-size:12px; font-weight:700; color:#0f172a;">${escapeHtml(version?.label || version?.version_id || '')}</div>
                <div style="margin-top:4px; font-size:11px; color:#64748b;">${escapeHtml(version?.created_at || '')}</div>
                <div style="margin-top:6px; font-size:11px; color:#475569;">+${entityCount} 实体 / +${relationCount} 显式关系 / +${derivedCount} 派生关系</div>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  applyVersionSnapshot(version, { highlightPatch = null, keepPreview = false } = {}) {
    if (!version) return;
    const nextGraphData = {
      json_result: version.json_result,
      nodes: version.nodes || [],
      edges: version.edges || [],
      row_id: this.lastResult?.row_id || null,
      case_name: this.lastResult?.case_name || '',
      score: this.lastResult?.score || 0,
      issues: this.lastResult?.issues || [],
    };
    if (this.lastResult) {
      this.lastResult = { ...this.lastResult, json_result: version.json_result };
    }
    this.renderJson(version.json_result, highlightPatch || version.highlight_patch || null);
    store.setState({
      parseGraphData: nextGraphData,
      parseActiveVersionId: version.version_id || this.getActiveVersionId(),
      parseMergeHighlight: highlightPatch || version.highlight_patch || null,
      parseEnhancementPreviewActive: keepPreview ? store.getState().parseEnhancementPreviewActive : false,
      parseEnhancementPreviewRunId: keepPreview ? store.getState().parseEnhancementPreviewRunId : null,
      parseEnhancementPreviewPatch: keepPreview ? store.getState().parseEnhancementPreviewPatch : null,
    });
    this.renderVersionRail(this.getVersionList(), version.version_id || this.getActiveVersionId());
  }

  async switchVersion(versionId) {
    const version = this.getVersionList().find((item) => item?.version_id === versionId);
    if (!version) return;
    this.applyVersionSnapshot(version, { highlightPatch: version.highlight_patch || null });
    if (this.lastRetrievalBundle) {
      this.renderRetrievalBundle(this.lastRetrievalBundle);
    }
    this.setStatus(`已切换到 ${version.label || version.version_id}`, '#2563eb');
  }

  async handlePreviewEnhancementApply() {
    if (!this.lastResult || !this.getCurrentEnhancementRunId()) return;
    const runId = this.getCurrentEnhancementRunId();
    const preview = await previewEnhancementMerge(this.lastResult.row_id, runId, this.getActiveVersionId());
    const previewGraph = preview.preview_graph || {};
    const previewGraphData = {
      json_result: previewGraph.json_result || this.lastResult.json_result,
      nodes: previewGraph.nodes || [],
      edges: previewGraph.edges || [],
      row_id: this.lastResult.row_id,
      case_name: this.lastResult.case_name,
      score: this.lastResult.score,
      issues: this.lastResult.issues,
    };
    store.setState({
      parseGraphData: previewGraphData,
      parseEnhancementPreviewActive: true,
      parseEnhancementPreviewRunId: runId,
      parseEnhancementPreviewPatch: preview.highlight_patch || null,
      parseMergeHighlight: preview.highlight_patch || null,
    });
    const updated = { ...(this.lastEnhancementResult || {}), apply_status: preview.apply_status || 'previewed' };
    this.lastEnhancementResult = updated;
    this.syncEnhancementRuns(updated);
    this.renderEnhancementResult(updated);
    this.setStatus('已进入增量应用预览', '#2563eb');
  }

  handleExitPreview() {
    const version = this.getActiveVersion();
    if (version) {
      this.applyVersionSnapshot(version, { highlightPatch: version.highlight_patch || null, keepPreview: false });
    } else if (this.lastResult) {
      store.setState({
        parseGraphData: this.lastResult,
        parseEnhancementPreviewActive: false,
        parseEnhancementPreviewRunId: null,
        parseEnhancementPreviewPatch: null,
      });
    }
    this.setStatus('已退出增量预览', '#64748b');
  }

  async handleMergeEnhancement() {
    if (!this.lastResult || !this.getCurrentEnhancementRunId()) return;
    const runId = this.getCurrentEnhancementRunId();
    const merged = await mergeEnhancementResult(this.lastResult.row_id, runId, this.getActiveVersionId());
    const versions = merged.versions || [];
    const activeVersionId = merged.active_version_id || merged.new_version_id || this.getActiveVersionId();
    const activeVersion = versions.find((item) => item?.version_id === activeVersionId) || merged.merged_graph || null;
    if (activeVersion) {
      this.lastResult = { ...this.lastResult, json_result: activeVersion.json_result };
      store.setState({
        parseVersions: versions,
        parseActiveVersionId: activeVersionId,
        parseEnhancementPreviewActive: false,
        parseEnhancementPreviewRunId: null,
        parseEnhancementPreviewPatch: null,
      });
      this.applyVersionSnapshot(activeVersion, { highlightPatch: merged.highlight_patch || activeVersion.highlight_patch || null });
    }
    if (merged.enhancement_run) {
      this.lastEnhancementResult = merged.enhancement_run;
      this.syncEnhancementRuns(merged.enhancement_run);
      this.renderEnhancementResult(merged.enhancement_run);
    }
    this.renderVersionRail(versions, activeVersionId);
    this.switchTab('termJsonArea');
    this.setStatus(`增量结果已合并到 ${activeVersionId}`, '#16a34a');
  }

  renderJson(jsonResult, highlightPatch = null) {
    const treeHost = document.getElementById('termJsonTree');
    const placeholder = document.getElementById('termJsonPlaceholder');
    const changeNote = document.getElementById('termJsonChangeNote');
    this.jsonChangedKeys = new Set(highlightPatch?.changedKeys || []);
    
    if (treeHost && placeholder) {
      if (jsonResult) {
        placeholder.style.display = 'none';
        treeHost.style.display = 'block';
        if (changeNote) {
          const keys = Array.from(this.jsonChangedKeys);
          if (keys.length) {
            changeNote.style.display = 'block';
            changeNote.textContent = `本版本变化高亮：${keys.join('、')}`;
          } else {
            changeNote.style.display = 'none';
            changeNote.textContent = '';
          }
        }
        
        try {
          const jsonObj = typeof jsonResult === 'string' ? JSON.parse(jsonResult) : jsonResult;
          treeHost.innerHTML = '';
          treeHost.appendChild(this.buildJsonTree(jsonObj, true, 0));
        } catch (e) {
          treeHost.innerHTML = `<pre style="color:red">JSON parse error: ${e.message}</pre>`;
        }
      } else {
        placeholder.style.display = 'block';
        treeHost.style.display = 'none';
        if (changeNote) {
          changeNote.style.display = 'none';
          changeNote.textContent = '';
        }
      }
    }
  }

  buildJsonTree(obj, isRoot = false, depth = 0) {
    const container = document.createElement('div');
    container.style.marginLeft = isRoot ? '0' : '16px';
    
    if (typeof obj !== 'object' || obj === null) {
      const val = document.createElement('span');
      val.style.color = typeof obj === 'string' ? '#27ae60' : '#2980b9';
      val.textContent = JSON.stringify(obj);
      container.appendChild(val);
      return container;
    }
    
    const isArray = Array.isArray(obj);
    const keys = Object.keys(obj);
    
    keys.forEach((key, idx) => {
      const line = document.createElement('div');
      if (!isArray) {
        line.setAttribute('data-json-key', key);
        if (depth === 0 && this.jsonChangedKeys.has(key)) {
          line.style.background = '#eff6ff';
          line.style.border = '1px solid #bfdbfe';
          line.style.borderRadius = '8px';
          line.style.padding = '4px 6px';
          line.style.margin = '2px 0';
        }
      }
      
      const isComplex = typeof obj[key] === 'object' && obj[key] !== null;
      // Auto-collapse case_summary to save space
      let isCollapsed = key === 'case_summary';
      
      const toggleBtn = document.createElement('span');
      toggleBtn.style.display = 'inline-block';
      toggleBtn.style.width = '12px';
      toggleBtn.style.cursor = isComplex ? 'pointer' : 'default';
      toggleBtn.style.color = '#888';
      toggleBtn.textContent = isComplex ? (isCollapsed ? '▶' : '▼') : '';
      
      const keySpan = document.createElement('span');
      keySpan.style.color = '#8e44ad';
      keySpan.style.fontWeight = 'bold';
      keySpan.textContent = isArray ? '' : `"${key}": `;
      
      line.appendChild(toggleBtn);
      line.appendChild(keySpan);
      
      if (isComplex) {
        const bracketStart = document.createElement('span');
        bracketStart.textContent = Array.isArray(obj[key]) ? '[' : '{';
        line.appendChild(bracketStart);
        
        const childContainer = this.buildJsonTree(obj[key], false, depth + 1);
        childContainer.style.display = isCollapsed ? 'none' : 'block';
        
        const bracketEnd = document.createElement('div');
        bracketEnd.textContent = (Array.isArray(obj[key]) ? ']' : '}') + (idx < keys.length - 1 ? ',' : '');
        bracketEnd.style.display = isCollapsed ? 'none' : 'block';
        
        const collapsedHint = document.createElement('span');
        collapsedHint.style.color = '#bbb';
        collapsedHint.style.display = isCollapsed ? 'inline' : 'none';
        collapsedHint.textContent = ' ... ' + (Array.isArray(obj[key]) ? ']' : '}') + (idx < keys.length - 1 ? ',' : '');
        line.appendChild(collapsedHint);
        
        const setCollapsed = (collapsed) => {
          isCollapsed = collapsed;
          toggleBtn.textContent = isCollapsed ? '▶' : '▼';
          childContainer.style.display = isCollapsed ? 'none' : 'block';
          bracketEnd.style.display = isCollapsed ? 'none' : 'block';
          collapsedHint.style.display = isCollapsed ? 'inline' : 'none';
        };
        
        childContainer.expandMe = () => setCollapsed(false);
        
        toggleBtn.addEventListener('click', () => {
          setCollapsed(!isCollapsed);
        });
        
        container.appendChild(line);
        container.appendChild(childContainer);
        container.appendChild(bracketEnd);
      } else {
        const valSpan = document.createElement('span');
        valSpan.style.color = typeof obj[key] === 'string' ? '#27ae60' : '#2980b9';
        valSpan.textContent = JSON.stringify(obj[key]) + (idx < keys.length - 1 ? ',' : '');
        line.appendChild(valSpan);
        container.appendChild(line);
      }
    });
    
    if (isRoot) {
      const rootWrap = document.createElement('div');
      rootWrap.textContent = isArray ? '[' : '{';
      rootWrap.appendChild(container);
      const end = document.createElement('div');
      end.textContent = isArray ? ']' : '}';
      rootWrap.appendChild(end);
      return rootWrap;
    }
    
    return container;
  }

  setStatus(text, color = '#64748b') {
    if (this.statusArea) {
      this.statusArea.innerHTML = `<span style="color: ${color}">${escapeHtml(text)}</span>`;
    }
  }

  updateEnhanceButtonState() {
    if (!this.enhanceBtn) return;
    const ready = Boolean(this.lastEvalResult && !this.isEnhancing);
    this.enhanceBtn.disabled = !ready;
    this.enhanceBtn.classList.toggle('ready', ready);
    this.enhanceBtn.style.opacity = ready ? '1' : '0.92';
    this.enhanceBtn.style.cursor = ready ? 'pointer' : 'not-allowed';
  }

  resetEnhancementState() {
    this.lastEnhancementResult = null;
    this.lastEnhancementRuns = [];
    this.isEnhancing = false;

    const placeholder = document.getElementById('termEnhancePlaceholder');
    const metaHost = document.getElementById('termEnhanceMeta');
    const treeHost = document.getElementById('termEnhanceTree');
    if (placeholder) {
      placeholder.style.display = 'block';
      placeholder.textContent = this.lastEvalResult ? '等待执行增量解析...' : '等待本体论评估后进行增量解析...';
    }
    if (metaHost) {
      metaHost.style.display = 'none';
      metaHost.innerHTML = '';
    }
    if (treeHost) {
      treeHost.style.display = 'none';
      treeHost.innerHTML = '';
    }
    const changeNote = document.getElementById('termJsonChangeNote');
    if (changeNote) {
      changeNote.style.display = 'none';
      changeNote.textContent = '';
    }
    this.renderVersionRail([], 'v0');
    store.setState({
      parseVersions: [],
      parseActiveVersionId: 'v0',
      parseEnhancementRuns: [],
      parseEnhancementPreviewActive: false,
      parseEnhancementPreviewRunId: null,
      parseEnhancementPreviewPatch: null,
      parseMergeHighlight: null,
    });
    this.resetRetrievalState();
    this.updateEnhanceButtonState();
  }

  async handleParse() {
    const text = this.inputArea ? this.inputArea.value.trim() : '';
    if (!text) {
      this.setStatus('请输入需要解析的文本', '#e74c3c');
      return;
    }
    
    this.setStatus('解析中，请稍候...', '#2980b9');
    if (this.parseBtn) {
      this.parseBtn.disabled = true;
      this.parseBtn.style.opacity = '0.6';
    }
    
    try {
      // Direct fetch call mapped from frontend
      const res = await fetch('/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const result = await res.json();
      
      if (result.error) throw new Error(result.error);
      
      this.lastResult = result;
      this.lastEvalResult = null;
      this.lastQualityResult = null;
      this.setStatus(`解析成功 (得分: ${result.score})`, '#27ae60');
      this.resetEnhancementState();
      this.resetRetrievalState();
      
      this.renderJson(result.json_result);
      
      if (this.evalBtn) this.evalBtn.disabled = false;
      if (this.saveBtn) this.saveBtn.disabled = false;
      if (this.saveBtnBottom) this.saveBtnBottom.disabled = false;

      if (result.json_result) {
        const baseVersion = {
          version_id: 'v0',
          label: '初始解析',
          version_type: 'base',
          source_run_id: null,
          created_at: new Date().toISOString(),
          change_summary: {},
          highlight_patch: {},
          json_result: result.json_result,
          nodes: result.nodes || [],
          edges: result.edges || [],
        };
        store.setState({ 
          parseGraphData: result,
          isParseResultAvailable: true,
          isOntologyVisible: true,
          workspaceLayoutMode: 'parse_primary',
          parseVersions: [baseVersion],
          parseActiveVersionId: 'v0',
          parseMergeHighlight: null,
        });
        this.renderVersionRail([baseVersion], 'v0');
        
        // Auto-run quality analysis
        this.switchTab('termIssuesTabContent');
        await this.handleQualityAnalysis(result.json_result);
      }
    } catch (err) {
      this.setStatus(`解析失败: ${err.message}`, '#e74c3c');
    } finally {
      if (this.parseBtn) {
        this.parseBtn.disabled = false;
        this.parseBtn.style.opacity = '1';
      }
    }
  }

  highlightJsonKey(key) {
    if (!key) return;
    
    // Switch to JSON tab to ensure it's visible
    this.switchTab('termJsonArea');
    
    const treeHost = document.getElementById('termJsonTree');
    if (!treeHost) return;
    
    // Find the first line that matches this key
    const line = treeHost.querySelector(`[data-json-key="${key}"]`);
    if (line) {
      // Expand all parent containers
      let parent = line.parentElement;
      while (parent && parent !== treeHost) {
        if (typeof parent.expandMe === 'function') {
          parent.expandMe();
        }
        parent = parent.parentElement;
      }
      
      // Scroll into view
      setTimeout(() => {
        line.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Highlight effect
        const originalBg = line.style.backgroundColor;
        line.style.transition = 'background-color 0.4s ease';
        line.style.backgroundColor = '#fef08a'; // yellow highlight
        line.style.borderRadius = '4px';
        line.style.padding = '2px 4px';
        
        setTimeout(() => {
          line.style.backgroundColor = originalBg || 'transparent';
          setTimeout(() => {
            line.style.transition = '';
            line.style.padding = '';
            line.style.borderRadius = '';
          }, 400);
        }, 2000);
      }, 50);
    }
  }

  buildLocateButtonHtml(targetInfo, label) {
    // Generate an HTML string for a locate button
    const dataAttrs = `data-target="${escapeHtml(targetInfo.typeKey || targetInfo.nodeType || targetInfo.label || '')}" data-source-graph="${targetInfo.sourceGraph || 'parse'}"`;
    return `<span class="qa-locate-btn" ${dataAttrs} style="display:inline-flex;align-items:center;justify-content:center;font-size:10px;color:#2980b9;background:#e1f0fa;padding:2px 8px;border-radius:10px;cursor:pointer;margin-left:8px;font-weight:600;transition:all 0.2s;">${escapeHtml(label)} ⌕</span>`;
  }

  renderQualityIssues(qa, focusNodeData) {
    const issuesTab = document.getElementById('termIssuesTabContent');
    if (!issuesTab) return;
    
    const scroll = issuesTab.querySelector('#termIssuesScroll') || issuesTab;
    if (scroll.id === 'termIssuesScroll') scroll.style.padding = '0';
    
    let html = '';
    
    // ── Global Score Header ──
    const bgColor = qa.total_score >= 80 ? '#27ae60' : (qa.total_score >= 60 ? '#e67e22' : '#e74c3c');
    html += `<div style="position:sticky;top:0;z-index:10;background:#fff;padding:12px 14px 8px;border-bottom:2px solid ${bgColor};margin-bottom:0;">`;
    html += '<div style="display:flex;align-items:center;justify-content:space-between;">';
    html += '<div><span style="font-weight:700;font-size:16px;">📊 解析质量分析</span>';
    html += ' <span style="font-size:12px;color:#999;">(纯本地统计)</span></div>';
    html += '<div style="text-align:right;">';
    html += `<span style="font-size:24px;font-weight:700;color:${bgColor};">${qa.total_score || 0}</span>`;
    html += '<span style="font-size:13px;color:#999;">/100</span>';
    html += ` <span class="term-eval-score-badge" style="background:${bgColor}20;color:${bgColor};font-size:13px;">${qa.confidence || ''}</span>`;
    html += '</div></div>';
    html += '<div class="term-eval-dim-bar" style="margin-top:6px;height:6px;">';
    html += `<div class="term-eval-dim-fill" style="width:${qa.total_score || 0}%;background:${bgColor};height:6px;"></div>`;
    html += '</div></div>';

    // ── Issues Alert Bar ──
    if (qa.issues && qa.issues.length > 0) {
      const criticalCount = qa.issues.filter(i => i.severity === 'critical').length;
      const majorCount = qa.issues.filter(i => i.severity === 'major').length;
      html += '<div style="padding:8px 14px;background:#fff8f0;border-bottom:1px solid #f0e0c0;font-size:12px;display:flex;gap:12px;flex-wrap:wrap;">';
      if (criticalCount > 0) html += `<span style="color:#e74c3c;">🚨 严重: ${criticalCount}</span>`;
      if (majorCount > 0) html += `<span style="color:#e67e22;">⚠ 主要: ${majorCount}</span>`;
      html += `<span style="color:#f1c40f;">🔸 次要: ${qa.issues.length - criticalCount - majorCount}</span>`;
      html += `<span style="color:#999;margin-left:auto;">共 ${qa.issues.length} 项</span>`;
      html += '</div>';
    }

    // ── Focus Section ──
    if (focusNodeData) {
      const targetLabel = focusNodeData.label || focusNodeData.id;
      const targetType = focusNodeData.nodeType || '';
      
      const relatedEntities = [];
      const relatedIssues = qa.issues ? qa.issues.filter(i => i.target === targetLabel || i.entity === targetLabel) : [];
      
      if (qa.categories) {
        qa.categories.forEach(cat => {
          (cat.entities || []).forEach(ent => {
            if (ent.type === targetType || ent.type_label === targetType || ent.type_label === targetLabel) {
              relatedEntities.push({
                type: ent.type,
                typeLabel: ent.type_label,
                category: cat.category_label,
                score: ent.score,
                missing: ent.missing_fields || []
              });
            }
          });
        });
      }

      html += '<div style="padding:12px 14px;background:#f8fafc;border-bottom:1px solid #e2e8f0;">';
      html += '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">';
      html += '<span style="font-size:11px;color:#64748b;font-weight:700;">当前分析对象</span>';
      html += `<span style="font-size:13px;font-weight:700;color:#0f172a;">${escapeHtml(targetLabel)}</span>`;
      if (targetType) html += `<span style="font-size:11px;color:#64748b;">${escapeHtml(targetType)}</span>`;
      html += this.buildLocateButtonHtml({ label: targetLabel, typeKey: targetType, sourceGraph: 'parse' }, '回到图谱');
      html += `<span style="margin-left:auto;font-size:10px;color:#94a3b8;">命中实体 ${relatedEntities.length} · 相关问题 ${relatedIssues.length}</span>`;
      html += '</div>';
      
      if (relatedEntities.length || relatedIssues.length) {
        if (relatedEntities.length) {
          html += '<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px;">';
          relatedEntities.slice(0, 4).forEach(entity => {
            html += '<div style="padding:10px;border:1px solid #e2e8f0;border-radius:10px;background:#fff;">';
            html += `<div style="font-size:12px;font-weight:700;color:#0f172a;">${escapeHtml(entity.typeLabel)}</div>`;
            html += `<div style="font-size:11px;color:#64748b;margin-top:4px;">${escapeHtml(entity.category)} · 得分 ${entity.score}/100</div>`;
            if (entity.missing && entity.missing.length) {
              html += `<div style="font-size:11px;color:#e67e22;margin-top:6px;">待补字段：${escapeHtml(entity.missing.join('、'))}</div>`;
            }
            html += `<div style="margin-top:8px;">${this.buildLocateButtonHtml({ typeKey: entity.type || entity.typeLabel, sourceGraph: 'parse' }, '定位图谱')}</div>`;
            html += '</div>';
          });
          html += '</div>';
        }
        if (relatedIssues.length) {
          html += '<div style="margin-top:10px;">';
          relatedIssues.slice(0, 5).forEach(iss => {
            const sevClass = iss.severity || 'minor';
            const icon = sevClass === 'critical' ? '🚨' : (sevClass === 'major' ? '⚠' : '🔸');
            const msg = iss.message || iss.description || iss.msg || '';
            html += `<div class="term-eval-issue ${sevClass}" style="display:flex;align-items:center;justify-content:space-between;gap:8px;">`;
            html += `<span>${icon} <b>${escapeHtml(targetLabel)}</b>: ${escapeHtml(msg)}</span>`;
            html += this.buildLocateButtonHtml({ typeKey: targetLabel, sourceGraph: 'parse' }, '定位');
            html += '</div>';
          });
          html += '</div>';
        }
      } else {
        html += '<div style="margin-top:8px;font-size:12px;color:#94a3b8;">当前对象暂无直接问题条目，下方保留全局分析结果供继续排查。</div>';
      }
      html += '</div>';
    }

    // ── Category / Entity Tree ──
    html += '<div style="padding:6px 14px 80px;">';

    if (qa.categories && qa.categories.length > 0) {
      qa.categories.forEach(cat => {
        const catBg = cat.score >= 80 ? '#27ae60' : (cat.score >= 60 ? '#e67e22' : '#e74c3c');
        const catId = 'cat_' + (cat.category || '').replace(/[^a-zA-Z0-9]/g, '_');
        
        html += '<div style="margin-top:14px;">';
        html += `<div class="qa-cat-header" data-target="${catId}" style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:#f0f4f8;border-radius:6px;border-left:4px solid ${catBg};cursor:pointer;user-select:none;">`;
        html += '<span class="qa-toggle" style="font-size:10px;color:#888;transition:transform 0.2s;">▼</span>';
        html += `<span style="font-weight:700;font-size:15px;color:#2c3e50;">${escapeHtml(cat.category_label || cat.category)}</span>`;
        html += `<span style="font-size:11px;color:#888;">(${escapeHtml(cat.category)})</span>`;
        html += `<span style="margin-left:auto;font-size:13px;font-weight:600;color:${catBg};">${cat.score}/100</span>`;
        html += '</div>';
        
        html += `<div class="qa-cat-body" id="${catId}">`;
        html += '<div class="term-eval-dim-bar" style="margin:4px 10px 8px;height:4px;">';
        html += `<div class="term-eval-dim-fill" style="width:${cat.score}%;background:${catBg};height:4px;"></div>`;
        html += '</div>';

        if (cat.entities) {
          cat.entities.forEach(entity => {
            if (entity.fields_count === 0 && entity.instance_count === 0) return;
            const entBg = entity.score >= 80 ? '#27ae60' : (entity.score >= 60 ? '#e67e22' : '#e74c3c');
            const entIcon = entity.status === 'ok' ? '✅' : (entity.status === 'partial' ? '⚠️' : '❌');
            const entId = catId + '_' + (entity.type || '').replace(/[^a-zA-Z0-9]/g, '_');
            
            html += '<div style="margin-bottom:8px;">';
            html += `<div class="qa-ent-header" data-target="${entId}" style="display:flex;align-items:center;gap:6px;padding:6px 8px;background:#fafafa;border-radius:4px;cursor:pointer;user-select:none;">`;
            html += '<span class="qa-toggle" style="font-size:10px;color:#888;margin-right:2px;transition:transform 0.2s;">▼</span>';
            html += `<span>${entIcon}</span>`;
            html += `<span style="font-weight:600;font-size:13px;color:#34495e;">${escapeHtml(entity.type_label || entity.type)}</span>`;
            html += `<span style="font-size:11px;color:#999;">(${escapeHtml(entity.type)})</span>`;
            if (entity.instance_count > 1) {
              html += `<span style="font-size:11px;color:#888;background:#eef;padding:1px 6px;border-radius:8px;">×${entity.instance_count}</span>`;
            }
            html += this.buildLocateButtonHtml({ typeKey: entity.type || entity.type_label, sourceGraph: 'parse' }, '定位');
            html += `<span style="margin-left:auto;font-size:12px;font-weight:600;color:${entBg};">${entity.score}/100</span>`;
            html += '</div>';
            
            html += `<div class="qa-ent-body" id="${entId}">`;
            html += '<div class="term-eval-dim-bar" style="margin:3px 8px 4px;height:3px;">';
            html += `<div class="term-eval-dim-fill" style="width:${entity.score}%;background:${entBg};height:3px;"></div>`;
            html += '</div>';
            
            if (entity.items && entity.items.length > 0) {
              entity.items.forEach(item => {
                html += '<div style="margin-left:20px;margin-bottom:4px;">';
                html += '<div style="font-size:12px;color:#555;padding:2px 0;">';
                if (item.label) html += `<span style="color:#888;font-size:11px;">📄 ${escapeHtml(item.label)}</span>`;
                html += '</div>';
                
                if (item.fields && item.fields.length > 0) {
                  item.fields.forEach(f => {
                    const fIcon = f.status === 'ok' ? '✅' : (f.status === 'partial' ? '⚠️' : '❌');
                    const fColor = f.status === 'ok' ? '#27ae60' : (f.status === 'partial' ? '#e67e22' : '#e74c3c');
                    html += `<div style="margin-left:24px;padding:2px 0;font-size:12px;display:flex;align-items:center;gap:4px;">`;
                    html += `<span>${fIcon}</span><span style="color:${fColor};">${escapeHtml(f.label || f.code)}</span>`;
                    if (f.status === 'missing' && f.value !== null && f.value !== undefined) {
                      html += `<span style="color:#999;font-size:11px;">(值: ${escapeHtml(JSON.stringify(f.value))})</span>`;
                    }
                    if (f.required && f.status !== 'ok') {
                      html += '<span style="color:#e74c3c;font-size:10px;background:#ffe0e0;padding:0 4px;border-radius:2px;">必填</span>';
                    }
                    html += '</div>';
                  });
                }
                html += '</div>';
              });
            }

            if (entity.relations && entity.relations.length > 0) {
              entity.relations.forEach(rel => {
                const rIcon = rel.status === 'ok' ? '🔗' : '🔗';
                html += `<div style="margin-left:44px;padding:2px 0;font-size:11px;color:#888;">${rIcon} ${escapeHtml(rel.label)} → ${escapeHtml(rel.target)}</div>`;
              });
            }
            
            html += '</div></div>';
          });
        }
        html += '</div></div>';
      });
    }

    // ── Detailed Issues List ──
    if (qa.issues && qa.issues.length > 0) {
      html += '<div style="margin-top:16px;padding-top:12px;border-top:2px solid #eee;">';
      html += '<div style="font-weight:600;font-size:14px;color:#e74c3c;margin-bottom:8px;">⚠ 问题详情</div>';
      qa.issues.forEach(iss => {
        const sevClass = iss.severity || 'minor';
        const icon = sevClass === 'critical' ? '🚨' : (sevClass === 'major' ? '⚠' : '🔸');
        html += `<div class="term-eval-issue ${sevClass}" style="display:flex;align-items:center;justify-content:space-between;gap:8px;">`;
        html += `<span>${icon} <b>${escapeHtml(iss.entity || '')}</b>: ${escapeHtml(iss.msg || iss.description || iss.message || '')} <span style="font-size:10px;color:#999;">[${sevClass}]</span></span>`;
        html += this.buildLocateButtonHtml({ label: iss.entity || '', typeKey: iss.entity || '', sourceGraph: 'parse' }, '定位');
        html += '</div>';
      });
      html += '</div>';
    }
    
    html += '</div>';
    scroll.innerHTML = html;
    this.bindJumpEvents(scroll);
  }

  async handleQualityAnalysis(jsonResult) {
    const issuesTab = document.getElementById('termIssuesTabContent');
    const issuesPlaceholder = document.getElementById('termIssuesPlaceholder');
    if (!issuesTab) return;
    
    if (issuesPlaceholder) issuesPlaceholder.style.display = 'none';
    issuesTab.innerHTML = '<div style="color: #94a3b8;">分析中...</div>';
    
    try {
      const qa = await parseQuality(this.inputArea?.value?.trim() || '', jsonResult, this.lastResult?.row_id || '');
      if (qa.error) throw new Error(qa.error);
      
      this.lastQualityResult = qa;
      this.renderQualityIssues(qa, store.getState().parseNodeData);
    } catch (err) {
      issuesTab.innerHTML = `<div style="color: #ef4444;">分析失败: ${escapeHtml(err.message)}</div>`;
    }
  }

  async handleSave() {
    if (!this.lastResult) return;
    const saveTarget = document.getElementById('termSaveTarget');
    const targetLayer = saveTarget ? saveTarget.value : 'manual';
    
    if (this.saveBtn) {
      this.saveBtn.disabled = true;
      this.saveBtn.textContent = '保存中...';
    }
    if (this.saveBtnBottom) {
      this.saveBtnBottom.disabled = true;
      this.saveBtnBottom.textContent = '保存中...';
    }
    
    try {
      const result = await saveResult({
        row_id: this.lastResult.row_id,
        json_result: this.lastResult.json_result,
        case_name: this.lastResult.case_name,
        score: this.lastResult.score,
        issues: this.lastResult.issues,
        text: this.inputArea ? this.inputArea.value : '',
        ontology_eval: this.lastEvalResult,
        quality_result: this.lastQualityResult,
        enhancement_result: this.lastEnhancementResult,
        enhancement_runs: store.getState().parseEnhancementRuns || [],
        parse_versions: store.getState().parseVersions || [],
        active_version_id: store.getState().parseActiveVersionId || 'v0',
        retrieval_bundle: this.lastRetrievalBundle,
        retrieval_write_manifest: this.lastRetrievalWriteManifest,
        target_layer: targetLayer,
      });
      
      if (this.saveBtn) {
        this.saveBtn.textContent = '✅ 已保存';
      }
      if (this.saveBtnBottom) {
        this.saveBtnBottom.textContent = '✅ 已保存';
      }
      this.setStatus(`保存成功 (${result.row_id || this.lastResult.row_id} -> ${result.target_layer || targetLayer})`, '#27ae60');
    } catch (err) {
      if (this.saveBtn) {
        this.saveBtn.textContent = '💾 保存';
        this.saveBtn.disabled = false;
      }
      if (this.saveBtnBottom) {
        this.saveBtnBottom.textContent = '💾 保存';
        this.saveBtnBottom.disabled = false;
      }
      this.setStatus(`保存失败: ${err.message}`, '#e74c3c');
    }
  }

  resetRetrievalState() {
    this.lastRetrievalBundle = null;
    this.lastRetrievalWriteManifest = null;
    store.setState({
      retrievalBundle: null,
      retrievalEntries: [],
      retrievalActiveEntryId: null,
      retrievalDirty: false,
      retrievalEmbeddingStatus: 'idle',
      retrievalWriteStatus: 'idle',
      retrievalSourceParseVersionId: null,
      retrievalWriteManifest: null,
      retrievalLastWriteSummary: null,
      retrievalFilters: { type: 'all', status: 'all', search: '' },
      retrievalPreviewMode: 'vector',
    });
    const pane = document.getElementById('termRetrievalPane');
    if (pane) {
      pane.innerHTML = '<div id="termRetrievalPlaceholder" style="padding:16px; color:#94a3b8; display:flex; flex-direction:column; gap:12px; align-items:flex-start;"><div>等待解析结果后生成检索资产...</div><button data-retrieval-action="build" style="padding:7px 12px;border:none;border-radius:8px;background:#2563eb;color:#fff;cursor:pointer;">生成检索资产</button></div>';
    }
  }

  getActiveRetrievalEntry() {
    const state = store.getState();
    const entries = state.retrievalEntries || [];
    if (!entries.length) return null;
    return entries.find(item => item?.entry_id === state.retrievalActiveEntryId) || entries[0] || null;
  }

  getRetrievalStorageKey() {
    const rowId = this.lastResult?.row_id || store.getState().parseGraphData?.row_id || 'default';
    return `workspace:retrieval-ui:${rowId}`;
  }

  readPersistedRetrievalUIState() {
    try {
      const raw = window.localStorage.getItem(this.getRetrievalStorageKey());
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  persistRetrievalUIState(extra = {}) {
    try {
      const state = store.getState();
      const payload = {
        activeEntryId: state.retrievalActiveEntryId || null,
        filters: state.retrievalFilters || { type: 'all', status: 'all', search: '' },
        previewMode: state.retrievalPreviewMode || 'vector',
        lastWriteSummary: state.retrievalLastWriteSummary || null,
        ...extra,
      };
      window.localStorage.setItem(this.getRetrievalStorageKey(), JSON.stringify(payload));
    } catch {}
  }

  getRetrievalFilters() {
    return store.getState().retrievalFilters || { type: 'all', status: 'all', search: '' };
  }

  getFilteredRetrievalEntries(entries, filters = null) {
    const currentFilters = filters || this.getRetrievalFilters();
    const search = String(currentFilters.search || '').trim().toLowerCase();
    return (entries || []).filter((item) => {
      const embeddingStatus = item?.edit_state?.embedding_status || 'pending';
      const dirty = Boolean(item?.edit_state?.dirty);
      const written = Boolean(item?.write_state?.written);
      const statusMatch = currentFilters.status === 'all'
        || (currentFilters.status === 'edited' && dirty)
        || (currentFilters.status === 'stale' && ['pending', 'stale', 'failed'].includes(embeddingStatus))
        || (currentFilters.status === 'ready' && embeddingStatus === 'ready')
        || (currentFilters.status === 'written' && written);
      const typeMatch = currentFilters.type === 'all' || item?.entry_type === currentFilters.type;
      const haystack = [
        item?.title,
        item?.summary,
        item?.retrieval_text,
        ...(item?.keywords || []),
        ...(item?.scene_tags || []),
      ].join(' ').toLowerCase();
      const searchMatch = !search || haystack.includes(search);
      return statusMatch && typeMatch && searchMatch;
    });
  }

  buildRetrievalValidation(bundle) {
    const issues = [];
    for (const item of (bundle?.entries || [])) {
      const title = item?.primary_entity?.label || item?.title || item?.entry_id || '未命名条目';
      const embeddingStatus = item?.edit_state?.embedding_status || 'pending';
      const hasValidChain = Boolean(item?.graph_payload?.is_valid_chain);
      if (!hasValidChain) {
        issues.push({ level: 'error', label: title, message: item?.graph_payload?.warning_text || '未形成有效实体关系链，不能生成主检索正文' });
      }
      if (!String(item?.retrieval_text || '').trim()) {
        issues.push({ level: 'error', label: title, message: '检索正文为空' });
      }
      if (['pending', 'stale', 'failed'].includes(embeddingStatus)) {
        issues.push({ level: 'warn', label: title, message: `向量状态为 ${embeddingStatus}` });
      }
    }
    return issues;
  }

  getRetrievalPreviewDoc(mode, bundle, activeEntry) {
    const manifest = this.lastRetrievalWriteManifest || store.getState().retrievalWriteManifest || {};
    if (mode === 'bundle') return bundle || {};
    if (mode === 'manifest') return manifest;
    if (!activeEntry) return {};
    if (mode === 'exact') {
      return {
        entry_id: activeEntry.entry_id,
        title: activeEntry.title,
        meta_header: activeEntry.meta_header || {},
        exact_payload: activeEntry.exact_payload || {},
        scene_tags: activeEntry.scene_tags || [],
        keywords: activeEntry.keywords || [],
      };
    }
    if (mode === 'vector') {
      return {
        entry_id: activeEntry.entry_id,
        title: activeEntry.title,
        view_label: activeEntry.view_label || activeEntry.entry_type,
        meta_header: activeEntry.meta_header || {},
        summary_text: activeEntry?.vector_payload?.summary_text || '',
        retrieval_text: activeEntry?.vector_payload?.retrieval_text || '',
        expanded_text: activeEntry?.vector_payload?.expanded_text || '',
        embedding_meta: activeEntry?.vector_payload?.embedding_meta || {},
      };
    }
    if (mode === 'graph') {
      return {
        entry_id: activeEntry.entry_id,
        title: activeEntry.title,
        view_label: activeEntry.view_label || activeEntry.entry_type,
        meta_header: activeEntry.meta_header || {},
        graph_payload: activeEntry.graph_payload || {},
        ontology_payload: activeEntry.ontology_payload || {},
      };
    }
    return activeEntry;
  }

  buildRetrievalWriteSummary(bundle) {
    const manifest = this.lastRetrievalWriteManifest || store.getState().retrievalWriteManifest || {};
    const lastWriteSummary = store.getState().retrievalLastWriteSummary || this.readPersistedRetrievalUIState()?.lastWriteSummary || null;
    const baseDir = lastWriteSummary?.outputDir || manifest?.target?.base_dir || '-';
    const files = [
      { name: 'bundle.json', count: bundle?.stats?.entry_total ?? 0 },
      { name: 'exact_docs.jsonl', count: bundle?.stats?.exact_doc_total ?? 0 },
      { name: 'vector_docs.jsonl', count: bundle?.stats?.vector_doc_total ?? 0 },
      { name: 'graph_docs.jsonl', count: bundle?.stats?.graph_doc_total ?? 0 },
      { name: 'manifest.json', count: 1 },
    ];
    return {
      baseDir,
      writtenAt: lastWriteSummary?.writtenAt || manifest?.written_at || '-',
      fileCount: files.length,
      files,
      remoteEmbeddingTotal: manifest?.remote_embedding_total ?? bundle?.stats?.remote_embedding_total ?? 0,
      fallbackEmbeddingTotal: manifest?.fallback_embedding_total ?? bundle?.stats?.fallback_embedding_total ?? 0,
    };
  }


  getRetrievalFieldHelp() {
    return {
      title: '用于快速识别这份检索资产，方便人工浏览、筛选和后续管理。',
      summary: '用一句话概括这份资产的核心含义，适合快速扫读，不替代完整正文。',
      retrieval_text: '这是最核心的检索文本，后续做向量化或检索测试时主要基于这里。',
      expanded_text: '用于补充主检索正文未展开的图谱链路、背景事实或额外上下文。',
      keywords: '补充关键词和人工标签，便于过滤、测试和后续管理。',
      notes: '记录人工调整说明、版本备注或特殊提醒，不直接等于主检索正文。',
      scene_tags: '表示这份资产当前的视角或测试标签，主要用于后续筛选和管理。',
    };
  }

  buildRetrievalFieldLabel(label, key) {
    const help = this.getRetrievalFieldHelp()[key] || '';
    return `${escapeHtml(label)} <span title="${escapeHtml(help)}" style="display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:999px;border:1px solid #cbd5e1;color:#64748b;font-size:10px;cursor:help;vertical-align:middle;">?</span>`;
  }

  buildRetrievalMetaHeaderLines(metaHeader = {}) {
    return [
      ['案件类型', metaHeader.case_type],
      ['一级案由', metaHeader.reason_level1],
      ['二级案由', metaHeader.reason_level2],
      ['三级案由', metaHeader.reason_level3],
      ['审级', metaHeader.trial_level],
      ['裁判年份', metaHeader.judgment_year],
      ['发布时间', metaHeader.publication_year],
    ].filter(([, value]) => value);
  }

  getRetrievalBuildActionLabel(bundle, versionMismatch) {
    if (!bundle?.entries?.length) return '生成检索资产';
    if (versionMismatch) return '按当前版本重生成';
    return '重新生成检索资产';
  }

  renderRetrievalBundle(bundle, { activeEntryId = null } = {}) {
    const pane = document.getElementById('termRetrievalPane');
    if (!pane) return;
    if (!bundle || !Array.isArray(bundle.entries) || !bundle.entries.length) {
      pane.innerHTML = '<div id="termRetrievalPlaceholder" style="padding:16px; color:#94a3b8; display:flex; flex-direction:column; gap:12px; align-items:flex-start;"><div>等待解析结果后生成检索资产...</div><button data-retrieval-action="build" style="padding:7px 12px;border:none;border-radius:8px;background:#2563eb;color:#fff;cursor:pointer;">生成检索资产</button></div>';
      this.lastRetrievalBundle = null;
      store.setState({
        retrievalBundle: null,
        retrievalEntries: [],
        retrievalActiveEntryId: null,
        retrievalDirty: false,
        retrievalEmbeddingStatus: 'idle',
        retrievalWriteStatus: 'idle',
        retrievalSourceParseVersionId: null,
        retrievalFilters: { type: 'all', status: 'all', search: '' },
        retrievalPreviewMode: 'vector',
        retrievalLastWriteSummary: null,
      });
      return;
    }
    this.lastRetrievalBundle = bundle;
    const entries = bundle.entries || [];
    const persistedUiState = this.readPersistedRetrievalUIState() || {};
    const filters = store.getState().retrievalFilters || persistedUiState.filters || { type: 'all', status: 'all', search: '' };
    const filteredEntries = this.getFilteredRetrievalEntries(entries, filters);
    const selectedId = activeEntryId || store.getState().retrievalActiveEntryId || persistedUiState.activeEntryId || filteredEntries[0]?.entry_id || entries[0]?.entry_id || null;
    const activeEntry = filteredEntries.find(item => item?.entry_id === selectedId) || entries.find(item => item?.entry_id === selectedId) || filteredEntries[0] || entries[0];
    const previewMode = store.getState().retrievalPreviewMode || persistedUiState.previewMode || 'vector';
    const previewDoc = this.getRetrievalPreviewDoc(previewMode, bundle, activeEntry);
    const validationIssues = this.buildRetrievalValidation(bundle);
    const blockingIssues = validationIssues.filter((item) => item.level === 'error' || item.message.includes('pending') || item.message.includes('stale') || item.message.includes('failed'));
    const editedCount = entries.filter(item => item?.edit_state?.dirty).length;
    const invalidChainCount = entries.filter(item => !item?.graph_payload?.is_valid_chain).length;
    const currentParseVersionId = store.getState().parseActiveVersionId || 'v0';
    const versionMismatch = (bundle.source_parse_version_id || 'v0') !== currentParseVersionId;
    const writeSummary = this.buildRetrievalWriteSummary(bundle);
    const hasWritten = Boolean(bundle.status?.write_status === 'written' || this.lastRetrievalWriteManifest || writeSummary.writtenAt !== '-');
    const statusChips = [
      { label: bundle.status?.draft === false ? '已定稿' : '草稿', color: '#1d4ed8', bg: '#eff6ff' },
      { label: editedCount ? `已编辑 ${editedCount}` : '无未保存编辑', color: editedCount ? '#c2410c' : '#475569', bg: editedCount ? '#fff7ed' : '#f8fafc' },
      { label: invalidChainCount ? `缺链 ${invalidChainCount}` : '关系链完整', color: invalidChainCount ? '#b91c1c' : '#166534', bg: invalidChainCount ? '#fef2f2' : '#ecfdf5' },
      { label: hasWritten ? '已写入资产文件' : '尚未写入文件', color: hasWritten ? '#166534' : '#475569', bg: hasWritten ? '#ecfdf5' : '#f8fafc' },
      { label: versionMismatch ? `版本落后于 ${currentParseVersionId}` : `绑定版本 ${bundle.source_parse_version_id || 'v0'}`, color: versionMismatch ? '#92400e' : '#4338ca', bg: versionMismatch ? '#fffbeb' : '#eef2ff' },
    ];
    const activeMetaHeader = activeEntry?.meta_header || {};
    const activeGraphPayload = activeEntry?.graph_payload || {};
    const activeOntologyPayload = activeEntry?.ontology_payload || {};
    const activePrimaryEntity = activeEntry?.primary_entity || {};
    const activeChainWarning = activeGraphPayload.warning_text || '当前未形成有效的实体关系链，暂不能自动生成主检索正文。';
    const activeChainMissingItems = Array.isArray(activeGraphPayload.missing_items) ? activeGraphPayload.missing_items.filter(Boolean) : [];
    const metaHeaderLines = this.buildRetrievalMetaHeaderLines(activeMetaHeader);
    const previewDocText = escapeHtml(JSON.stringify(previewDoc || {}, null, 2));
    const typeOptions = ['all', ...Array.from(new Set(entries.map(item => item?.entry_type).filter(Boolean)))];
    const previewModes = [
      { key: 'bundle', label: 'Bundle' },
      { key: 'exact', label: 'Exact' },
      { key: 'vector', label: 'Vector' },
      { key: 'graph', label: 'Graph' },
      { key: 'manifest', label: 'Manifest' },
    ];
    const buildActionLabel = this.getRetrievalBuildActionLabel(bundle, versionMismatch);
    pane.innerHTML = `
      <div style="display:flex;flex-direction:column;flex:1;min-height:0;">
        <div style="padding:12px 14px;border-bottom:1px solid #e5e7eb;background:#fbfdff;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex:1 1 420px;">
            <button data-retrieval-action="${entries.length ? 'regenerate' : 'build'}" style="padding:7px 12px;border:none;border-radius:8px;background:#2563eb;color:#fff;cursor:pointer;">${escapeHtml(buildActionLabel)}</button>
            <button data-retrieval-action="save-entry" style="padding:7px 12px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#334155;cursor:pointer;">保存编辑</button>
            <button data-retrieval-action="reembed" style="padding:7px 12px;border:none;border-radius:8px;background:#7c3aed;color:#fff;cursor:pointer;">重新向量化</button>
            <button data-retrieval-action="write" style="padding:7px 12px;border:none;border-radius:8px;background:#16a34a;color:#fff;cursor:pointer;">确认写入</button>
            <span style="font-size:12px;color:#64748b;">筛选：</span>
            <input id="retrievalSearchInput" value="${escapeHtml(filters.search || '')}" placeholder="搜索标题、摘要、关键词、场景" style="min-width:220px;flex:1;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;" />
            <select id="retrievalFilterType" style="padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;background:#fff;">
              ${typeOptions.map((item) => `<option value="${escapeHtml(item)}" ${filters.type === item ? 'selected' : ''}>${escapeHtml(item === 'all' ? '全部类型' : item)}</option>`).join('')}
            </select>
            <select id="retrievalFilterStatus" style="padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;background:#fff;">
              ${[
                ['all', '全部状态'],
                ['edited', '已编辑'],
                ['stale', '待向量化'],
                ['ready', '已就绪'],
                ['written', '已写入'],
              ].map(([value, label]) => `<option value="${value}" ${filters.status === value ? 'selected' : ''}>${label}</option>`).join('')}
            </select>
          </div>
          <div style="font-size:12px;color:#64748b;display:flex;gap:10px;flex-wrap:wrap;">
            <span>来源版本：${escapeHtml(bundle.source_parse_version_id || 'v0')}</span>
            <span>条目：${entries.length}</span>
            <span>筛后：${filteredEntries.length}</span>
            <span>已编辑：${editedCount}</span>
            <span>缺链：${invalidChainCount}</span>
            <span>状态：${escapeHtml(bundle.status?.write_status || 'pending')}</span>
          </div>
        </div>
        <div style="padding:10px 14px;border-bottom:1px solid #e5e7eb;background:#ffffff;display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;">
          <div style="display:flex;gap:8px;flex-wrap:wrap;flex:1 1 420px;">
            ${statusChips.map((item) => `<span style="font-size:11px;padding:4px 10px;border-radius:999px;background:${item.bg};color:${item.color};font-weight:700;">${escapeHtml(item.label)}</span>`).join('')}
          </div>
          <div style="font-size:12px;color:#64748b;min-width:260px;line-height:1.7;">
            <div>当前工作态：${escapeHtml(hasWritten ? '已写入稿，可继续编辑并再次写出' : '内存草稿，需确认写入后落盘')}</div>
            <div>最近写出：${escapeHtml(writeSummary.writtenAt || '-')}</div>
          </div>
        </div>
        ${versionMismatch ? `
          <div style="padding:10px 14px;border-bottom:1px solid #fde68a;background:#fffbeb;color:#92400e;font-size:12px;">
            当前检索资产来源于解析版本 ${escapeHtml(bundle.source_parse_version_id || 'v0')}，当前解析版本是 ${escapeHtml(currentParseVersionId)}。可直接使用上方主按钮按当前版本重新生成。
          </div>
        ` : ''}
        <div style="display:flex;flex:1;min-height:0;">
          <div style="width:30%;border-right:1px solid #e5e7eb;overflow:auto;background:#fcfdff;">
            ${filteredEntries.map(item => {
              const active = item.entry_id === activeEntry?.entry_id;
              const dirty = item?.edit_state?.dirty;
              const embeddingStatus = item?.edit_state?.embedding_status || 'pending';
              const hasValidChain = Boolean(item?.graph_payload?.is_valid_chain);
              const primaryEntityLabel = item?.primary_entity?.label || item?.title || item?.entry_id || '';
              return `
                <div data-entry-id="${escapeHtml(item.entry_id)}" style="padding:10px 12px;border-bottom:1px solid #eef2f7;cursor:pointer;background:${active ? '#eef6ff' : '#fff'};box-shadow:${hasValidChain ? 'none' : 'inset 3px 0 0 #dc2626'};">
                  <div style="font-size:12px;color:#6366f1;font-weight:700;">${escapeHtml(item.view_label || item.entry_type || '')}</div>
                  <div style="margin-top:4px;font-size:13px;color:#0f172a;font-weight:600;line-height:1.5;">${escapeHtml(primaryEntityLabel)}</div>
                  <div style="margin-top:4px;font-size:11px;color:#64748b;">${escapeHtml(item.title || '')}</div>
                  <div style="margin-top:4px;font-size:11px;color:#64748b;">${escapeHtml(item?.meta_header?.reason_level2 || item?.meta_header?.reason_level1 || item?.meta_header?.case_type || '')}</div>
                  <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
                    ${dirty ? '<span style="font-size:11px;padding:2px 8px;border-radius:999px;background:#fff7ed;color:#c2410c;">已编辑</span>' : ''}
                    ${hasValidChain ? '<span style="font-size:11px;padding:2px 8px;border-radius:999px;background:#ecfdf5;color:#166534;">关系链完整</span>' : '<span style="font-size:11px;padding:2px 8px;border-radius:999px;background:#fef2f2;color:#b91c1c;">缺少关系链</span>'}
                    <span style="font-size:11px;padding:2px 8px;border-radius:999px;background:${embeddingStatus === 'ready' ? '#ecfdf5' : '#fef3c7'};color:${embeddingStatus === 'ready' ? '#166534' : '#92400e'};">${escapeHtml(embeddingStatus)}</span>
                  </div>
                </div>
              `;
            }).join('')}
            ${filteredEntries.length === 0 ? '<div style="padding:16px;color:#94a3b8;font-size:13px;">当前筛选条件下没有匹配条目。</div>' : ''}
          </div>
          <div style="width:40%;padding:14px 16px;overflow:auto;display:flex;flex-direction:column;gap:10px;">
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              <span style="font-size:11px;padding:3px 8px;border-radius:999px;background:#eef2ff;color:#4338ca;">${escapeHtml(activeEntry?.view_label || activeEntry?.entry_type || '')}</span>
              <span style="font-size:11px;padding:3px 8px;border-radius:999px;background:#f8fafc;color:#475569;">首要实体：${escapeHtml(activePrimaryEntity.label || activeEntry?.title || '-')}</span>
            </div>
            <div style="padding:10px 12px;border:1px solid #dbeafe;border-radius:10px;background:#f8fbff;display:flex;flex-direction:column;gap:6px;">
              <div style="font-size:12px;font-weight:700;color:#1e3a8a;">统一元数据头</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;">
                ${metaHeaderLines.map(([label, value]) => `<span style="font-size:11px;padding:3px 8px;border-radius:999px;background:#fff;color:#334155;border:1px solid #dbeafe;">${escapeHtml(label)}：${escapeHtml(String(value))}</span>`).join('') || '<span style="font-size:12px;color:#64748b;">暂无元数据</span>'}
              </div>
            </div>
            <label style="font-size:12px;color:#475569;font-weight:700;">${this.buildRetrievalFieldLabel('标题', 'title')}</label>
            <input id="retrievalTitleInput" value="${escapeHtml(activeEntry?.title || '')}" style="padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;" />
            <label style="font-size:12px;color:#475569;font-weight:700;">${this.buildRetrievalFieldLabel('主检索正文', 'retrieval_text')}</label>
            ${activeGraphPayload.is_valid_chain ? '' : `
              <div style="padding:10px 12px;border:1px solid #fecaca;border-radius:10px;background:#fef2f2;color:#b91c1c;font-size:12px;line-height:1.7;">
                <div>${escapeHtml((activeChainWarning || '').split('\n')[0] || activeChainWarning)}</div>
                ${activeChainMissingItems.length ? `<div style="margin-top:6px;display:flex;flex-direction:column;gap:4px;">${activeChainMissingItems.map((item) => `<div>• ${escapeHtml(item)}</div>`).join('')}</div>` : ''}
              </div>
            `}
            <textarea id="retrievalTextInput" style="min-height:160px;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;resize:vertical;font-family:monospace;">${escapeHtml(activeEntry?.retrieval_text || '')}</textarea>
            <label style="font-size:12px;color:#475569;font-weight:700;">${this.buildRetrievalFieldLabel('补充上下文', 'expanded_text')}</label>
            <textarea id="retrievalExpandedInput" style="min-height:120px;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;resize:vertical;font-family:monospace;">${escapeHtml(activeEntry?.expanded_text || '')}</textarea>
            <label style="font-size:12px;color:#475569;font-weight:700;">${this.buildRetrievalFieldLabel('标签（逗号分隔）', 'keywords')}</label>
            <input id="retrievalKeywordsInput" value="${escapeHtml((activeEntry?.keywords || []).join('，'))}" style="padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;" />
          </div>
          <div style="width:30%;border-left:1px solid #e5e7eb;padding:14px 14px 16px;overflow:auto;background:#fafcff;">
            <div style="font-size:12px;color:#475569;font-weight:700;">知识图谱链路</div>
            <div style="margin-top:6px;padding:10px;border:1px solid ${activeGraphPayload.is_valid_chain ? '#e5e7eb' : '#fecaca'};border-radius:8px;background:${activeGraphPayload.is_valid_chain ? '#fff' : '#fef2f2'};font-size:12px;color:#334155;line-height:1.7;">
              <div>链路名称：${escapeHtml(activeGraphPayload.path_label || activeGraphPayload.path_type || '-')}</div>
              <div>链路说明：${escapeHtml(activeGraphPayload.description || '-')}</div>
              <div>首要实体：${escapeHtml(activePrimaryEntity.label || '-')}</div>
              <div style="margin-top:6px;color:${activeGraphPayload.is_valid_chain ? '#1e293b' : '#b91c1c'};white-space:pre-wrap;">${escapeHtml(activeGraphPayload.is_valid_chain ? (activeGraphPayload.chain_text || '暂无链路文本') : (((activeChainWarning || '').split('\n')[0]) || activeChainWarning))}</div>
              ${activeGraphPayload.is_valid_chain || !activeChainMissingItems.length ? '' : `<div style="margin-top:6px;display:flex;flex-direction:column;gap:4px;color:#b91c1c;">${activeChainMissingItems.map((item) => `<div>• ${escapeHtml(item)}</div>`).join('')}</div>`}
            </div>
            <div style="margin-top:10px;font-size:12px;color:#475569;font-weight:700;">本体结构</div>
            <div style="margin-top:6px;padding:10px;border:1px solid #e5e7eb;border-radius:8px;background:#fff;font-size:12px;color:#334155;line-height:1.7;">
              <div>视角：${escapeHtml(activeOntologyPayload.view_label || activeEntry?.view_label || '-')}</div>
              <div>结构说明：${escapeHtml(activeOntologyPayload.structure_text || '-')}</div>
              <div>实体：${escapeHtml((activeOntologyPayload.entity_types || []).join(' / ') || '-')}</div>
              <div>关系：${escapeHtml((activeOntologyPayload.relation_types || []).join(' / ') || '-')}</div>
            </div>
            <div style="margin-top:10px;font-size:12px;color:#475569;font-weight:700;">写入前校验</div>
            ${validationIssues.length ? `
              <div style="margin-top:6px;padding:10px;border:1px solid #fde68a;border-radius:8px;background:#fffdf5;">
                <div style="font-size:12px;color:#92400e;">当前共有 ${validationIssues.length} 项校验提醒，其中阻塞项 ${blockingIssues.length} 项。</div>
                <div style="margin-top:6px;display:flex;flex-direction:column;gap:6px;max-height:132px;overflow:auto;">
                  ${validationIssues.slice(0, 10).map((issue) => `
                    <div style="font-size:12px;color:${issue.level === 'error' ? '#b91c1c' : '#92400e'};background:${issue.level === 'error' ? '#fef2f2' : '#fffbeb'};border:1px solid ${issue.level === 'error' ? '#fecaca' : '#fde68a'};border-radius:8px;padding:7px 10px;">
                      <span style="font-weight:700;">${escapeHtml(issue.label)}</span>：${escapeHtml(issue.message)}
                    </div>
                  `).join('')}
                  ${validationIssues.length > 10 ? `<div style="font-size:12px;color:#92400e;">其余 ${validationIssues.length - 10} 项问题未展开显示。</div>` : ''}
                </div>
              </div>
            ` : `
              <div style="margin-top:6px;padding:10px;border:1px solid #bbf7d0;border-radius:8px;background:#f0fdf4;color:#166534;font-size:12px;">写入前校验通过，当前没有发现空正文、缺失关系链或待向量化条目。</div>
            `}
            <div style="margin-top:10px;font-size:12px;color:#475569;font-weight:700;">导出预览</div>
            <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
              ${previewModes.map((item) => `
                <button data-retrieval-action="preview-mode" data-preview-mode="${item.key}" style="padding:5px 10px;border-radius:999px;border:${previewMode === item.key ? 'none' : '1px solid #cbd5e1'};background:${previewMode === item.key ? '#2563eb' : '#fff'};color:${previewMode === item.key ? '#fff' : '#334155'};cursor:pointer;font-size:11px;">${item.label}</button>
              `).join('')}
            </div>
            <div style="font-size:12px;color:#475569;font-weight:700;">来源引用</div>
            <pre style="white-space:pre-wrap;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px;font-size:12px;color:#334155;">${escapeHtml(JSON.stringify(activeEntry?.source_refs || {}, null, 2))}</pre>
            <div style="margin-top:10px;font-size:12px;color:#475569;font-weight:700;">本体/图谱元数据</div>
            <pre style="white-space:pre-wrap;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px;font-size:12px;color:#334155;">${escapeHtml(JSON.stringify({
              ontology_payload: activeEntry?.ontology_payload || {},
              graph_payload: activeEntry?.graph_payload || {},
            }, null, 2))}</pre>
            <div style="margin-top:10px;font-size:12px;color:#475569;font-weight:700;">当前预览：${escapeHtml(previewModes.find((item) => item.key === previewMode)?.label || previewMode)}</div>
            <pre style="white-space:pre-wrap;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px;font-size:12px;color:#334155;">${previewDocText}</pre>
            <div style="margin-top:10px;font-size:12px;color:#475569;font-weight:700;">写出结果摘要</div>
            <div style="margin-top:6px;padding:10px;border:1px solid #e5e7eb;border-radius:8px;background:#fff;font-size:12px;color:#334155;line-height:1.7;">
              <div>输出目录：${escapeHtml(writeSummary.baseDir || '-')}</div>
              <div>最近写出：${escapeHtml(writeSummary.writtenAt || '-')}</div>
              <div>文件数：${escapeHtml(String(writeSummary.fileCount || 0))}</div>
              <div>真实向量：${escapeHtml(String(writeSummary.remoteEmbeddingTotal || 0))}</div>
              <div>兜底向量：${escapeHtml(String(writeSummary.fallbackEmbeddingTotal || 0))}</div>
              <div style="margin-top:6px;display:flex;flex-direction:column;gap:4px;">
                ${writeSummary.files.map((item) => `<div style="display:flex;justify-content:space-between;gap:10px;"><span>${escapeHtml(item.name)}</span><span style="color:#64748b;">${escapeHtml(String(item.count))}</span></div>`).join('')}
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    store.setState({
      retrievalBundle: bundle,
      retrievalEntries: entries,
      retrievalActiveEntryId: activeEntry?.entry_id || null,
      retrievalDirty: Boolean(bundle.status?.has_manual_edits),
      retrievalEmbeddingStatus: bundle.status?.has_stale_embeddings ? 'stale' : 'ready',
      retrievalWriteStatus: bundle.status?.write_status || 'pending',
      retrievalSourceParseVersionId: bundle.source_parse_version_id || null,
      retrievalWriteManifest: this.lastRetrievalWriteManifest || store.getState().retrievalWriteManifest || null,
      retrievalLastWriteSummary: writeSummary,
      retrievalFilters: filters,
      retrievalPreviewMode: previewMode,
    });
    this.persistRetrievalUIState({
      activeEntryId: activeEntry?.entry_id || null,
      filters,
      previewMode,
      lastWriteSummary: writeSummary,
    });
  }

  async handleBuildRetrieval(force = false) {
    if (!this.lastResult?.json_result) {
      this.setStatus('请先完成解析，再生成检索资产', '#ef4444');
      return;
    }
    if (force && this.lastRetrievalBundle) {
      const currentParseVersionId = store.getState().parseActiveVersionId || 'v0';
      const bundleVersionId = this.lastRetrievalBundle?.source_parse_version_id || 'v0';
      const hasManualEdits = Boolean(this.lastRetrievalBundle?.status?.has_manual_edits);
      const hasWritten = Boolean(
        this.lastRetrievalBundle?.status?.write_status === 'written'
        || this.lastRetrievalWriteManifest
        || store.getState().retrievalLastWriteSummary
      );
      const warnings = [];
      if (hasManualEdits) warnings.push('当前草稿包含手动编辑，重新生成会覆盖这些修改。');
      if (hasWritten) warnings.push('当前草稿对应的资产已经写出过，重新生成后工作台会切回新的未写出草稿。');
      if (bundleVersionId !== currentParseVersionId) warnings.push(`当前草稿来源版本是 ${bundleVersionId}，即将按当前解析版本 ${currentParseVersionId} 重新生成。`);
      if (warnings.length && !window.confirm(`${warnings.join('\n')}\n\n确定继续重新生成吗？`)) {
        return;
      }
    }
    this.setStatus('正在生成检索资产...', '#2563eb');
    try {
      const activeVersionId = store.getState().parseActiveVersionId || 'v0';
      const result = await buildRetrievalBundle({
        row_id: this.lastResult.row_id || 'manual_case',
        version_id: activeVersionId,
        case_name: this.lastResult.case_name || '',
        json_result: this.lastResult.json_result,
      });
      this.lastRetrievalWriteManifest = null;
      store.setState({
        retrievalWriteManifest: null,
        retrievalLastWriteSummary: null,
      });
      this.persistRetrievalUIState({
        activeEntryId: result.bundle?.entries?.[0]?.entry_id || null,
        lastWriteSummary: null,
      });
      this.renderRetrievalBundle(result.bundle, { activeEntryId: result.bundle?.entries?.[0]?.entry_id || null });
      this.switchTab('termRetrievalTabContent');
      this.setStatus('检索资产已生成', '#16a34a');
    } catch (err) {
      this.setStatus(`生成检索资产失败: ${err.message}`, '#ef4444');
    }
  }

  collectRetrievalEntryPatch() {
    const activeEntry = this.getActiveRetrievalEntry();
    if (!activeEntry) return null;
    const splitList = (value) => String(value || '')
      .split(/[，,]/)
      .map(item => item.trim())
      .filter(Boolean);
    return {
      title: document.getElementById('retrievalTitleInput')?.value || '',
      retrieval_text: document.getElementById('retrievalTextInput')?.value || '',
      expanded_text: document.getElementById('retrievalExpandedInput')?.value || '',
      keywords: splitList(document.getElementById('retrievalKeywordsInput')?.value || ''),
    };
  }

  async handleSaveRetrievalEntry() {
    const activeEntry = this.getActiveRetrievalEntry();
    if (!activeEntry || !this.lastRetrievalBundle) return;
    const patch = this.collectRetrievalEntryPatch();
    this.setStatus('正在保存检索条目编辑...', '#2563eb');
    try {
      const result = await updateRetrievalEntry({
        bundle: this.lastRetrievalBundle,
        entry_id: activeEntry.entry_id,
        patch,
      });
      this.renderRetrievalBundle(result.bundle, { activeEntryId: activeEntry.entry_id });
      this.setStatus('检索条目已更新，待重新向量化', '#16a34a');
    } catch (err) {
      this.setStatus(`保存检索条目失败: ${err.message}`, '#ef4444');
    }
  }

  async handleReembedRetrieval() {
    if (!this.lastRetrievalBundle) return;
    this.setStatus('正在重新向量化检索资产...', '#7c3aed');
    try {
      const staleEntries = (this.lastRetrievalBundle.entries || [])
        .filter(item => ['pending', 'stale', 'failed'].includes(item?.edit_state?.embedding_status))
        .map(item => item.entry_id);
      const result = await reembedRetrievalBundle({
        bundle: this.lastRetrievalBundle,
        entry_ids: staleEntries,
      });
      this.renderRetrievalBundle(result.bundle);
      const remoteCount = result.bundle?.stats?.remote_embedding_total || 0;
      const fallbackCount = result.bundle?.stats?.fallback_embedding_total || 0;
      this.setStatus(`检索资产向量化完成：真实 ${remoteCount}，兜底 ${fallbackCount}`, fallbackCount ? '#d97706' : '#16a34a');
    } catch (err) {
      this.setStatus(`重新向量化失败: ${err.message}`, '#ef4444');
    }
  }

  async handleWriteRetrieval() {
    if (!this.lastRetrievalBundle) return;
    const issues = this.buildRetrievalValidation(this.lastRetrievalBundle);
    const blockingIssues = issues.filter((item) => item.level === 'error' || item.message.includes('pending') || item.message.includes('stale') || item.message.includes('failed'));
    if (blockingIssues.length) {
      const preview = blockingIssues.slice(0, 5).map((item) => `${item.label}：${item.message}`).join('\n');
      window.alert(`当前仍有 ${blockingIssues.length} 项阻塞问题，暂不能写入：\n\n${preview}${blockingIssues.length > 5 ? `\n\n其余 ${blockingIssues.length - 5} 项请在右侧写入前校验中查看。` : ''}`);
      this.setStatus(`写入前仍有 ${blockingIssues.length} 项待处理问题，请先处理右侧写入前校验中的阻塞项`, '#d97706');
      return;
    }
    this.setStatus('正在写入检索资产文件...', '#16a34a');
    try {
      const result = await writeRetrievalBundle({ bundle: this.lastRetrievalBundle });
      this.lastRetrievalWriteManifest = result.manifest || null;
      const lastWriteSummary = {
        outputDir: result.output_dir || result.manifest?.target?.base_dir || '-',
        writtenAt: result.manifest?.written_at || new Date().toISOString(),
      };
      store.setState({
        retrievalWriteManifest: result.manifest || null,
        retrievalLastWriteSummary: lastWriteSummary,
      });
      this.persistRetrievalUIState({ lastWriteSummary });
      this.renderRetrievalBundle(result.bundle);
      this.setStatus(`检索资产已写入 ${result.output_dir}`, '#16a34a');
    } catch (err) {
      this.setStatus(`写入检索资产失败: ${err.message}`, '#ef4444');
    }
  }

  renderEvalResult(result) {
    this.lastEvalResult = result;
    const evalTab = document.getElementById('termEvalTabContent') || document.getElementById('termEvalArea');
    if (!evalTab) return;
    
    const scroll = evalTab.querySelector('#termEvalScroll') || evalTab;
    const ph = document.getElementById('termEvalPlaceholder');
    if (ph) ph.style.display = 'none';

    const pe = result.parsing_evaluation || {};
    const oc = result.ontology_coverage || {};
    
    // Attempt to extract focus info (mock)
    const bg = (score) => score >= 80 ? '#27ae60' : (score >= 60 ? '#e67e22' : '#e74c3c');

    let html = '';

    // ── Section 1: Parsing Evaluation ──
    html += '<div class="term-eval-section">';
    html += '<div class="term-eval-section-title">🔍 解析结果评估';
    html += ` <span class="term-eval-score-badge" style="background:${bg(pe.total_score || 0)}20;color:${bg(pe.total_score || 0)};">${pe.total_score || 0}/100</span>`;
    html += ` <span style="font-size:11px;color:#999;">${escapeHtml(pe.confidence || '')}</span>`;
    html += '</div>';

    if (pe.dimensions && pe.dimensions.length > 0) {
      pe.dimensions.forEach(d => {
        const ds = d.score || 0;
        html += '<div class="term-eval-dim">';
        html += `<div style="display:flex;justify-content:space-between;"><span><b>${escapeHtml(d.code || '')}</b> ${escapeHtml(d.name || '')}</span><span style="color:${bg(ds)};">${ds}</span></div>`;
        html += `<div class="term-eval-dim-bar"><div class="term-eval-dim-fill" style="width:${ds}%;background:${bg(ds)};"></div></div>`;
        if (d.detail || d.feedback) html += `<div class="term-eval-subscore">${escapeHtml(d.detail || d.feedback)}</div>`;
        html += '</div>';
      });
    } else if (pe.dimensions && typeof pe.dimensions === 'object') {
      for (const [key, d] of Object.entries(pe.dimensions)) {
        const ds = d.score || 0;
        html += '<div class="term-eval-dim">';
        html += `<div style="display:flex;justify-content:space-between;"><span><b>${escapeHtml(key)}</b> ${escapeHtml(d.name || key)}</span><span style="color:${bg(ds)};">${ds}</span></div>`;
        html += `<div class="term-eval-dim-bar"><div class="term-eval-dim-fill" style="width:${ds}%;background:${bg(ds)};"></div></div>`;
        if (d.feedback) html += `<div class="term-eval-subscore">${escapeHtml(d.feedback)}</div>`;
        html += '</div>';
      }
    }

    if (pe.issues && pe.issues.length > 0) {
      html += '<div style="font-size:12px;font-weight:600;color:#e74c3c;margin-top:8px;margin-bottom:4px;">问题列表</div>';
      pe.issues.forEach(iss => {
        const msg = typeof iss === 'string' ? iss : (iss.msg || iss.description || '');
        const sev = iss.severity || 'minor';
        const issueField = iss.field || iss.field_path || iss.entity || iss.target || '';
        const icon = sev === 'critical' || sev === 'high' ? '🚨' : (sev === 'major' || sev === 'medium' ? '⚠' : '🔸');
        html += `<div class="term-eval-issue ${sev}" style="display:flex;align-items:center;justify-content:space-between;gap:8px;">`;
        html += `<span>${icon} ${escapeHtml(msg)}</span>`;
        if (issueField) html += this.buildLocateButtonHtml({ label: issueField, typeKey: issueField, sourceGraph: 'parse' }, '定位');
        html += '</div>';
      });
    }
    
    if (pe.suggestions && pe.suggestions.length > 0) {
      html += '<div style="font-size:12px;font-weight:600;color:#8e44ad;margin-top:8px;margin-bottom:4px;">改进建议</div>';
      pe.suggestions.forEach(s => {
        html += `<div class="term-eval-suggestion">💡 ${escapeHtml(s)}</div>`;
      });
    }
    html += '</div>';

    // ── Section 2: Ontology Coverage ──
    html += '<div class="term-eval-section">';
    const ocBg = bg(oc.total_score || 0);
    html += '<div class="term-eval-section-title">🧩 本体论覆盖评估';
    html += ` <span class="term-eval-score-badge" style="background:${ocBg}20;color:${ocBg};">${oc.total_score || 0}/100</span>`;
    html += '</div>';

    if (oc.coverage_items && oc.coverage_items.length > 0) {
      html += '<div style="font-size:12px;font-weight:600;color:#27ae60;margin-bottom:4px;">已覆盖</div>';
      oc.coverage_items.forEach(c => {
        html += '<div class="term-eval-dim" style="color:#27ae60;display:flex;align-items:center;justify-content:space-between;gap:8px;">';
        html += `<span>✅ ${escapeHtml(c.entity || '')} — ${escapeHtml(c.relation || '')}</span>`;
        html += this.buildLocateButtonHtml({ typeKey: c.entity || '', sourceGraph: 'parse' }, '定位');
        html += '</div>';
      });
    }

    if (oc.uncovered && oc.uncovered.length > 0) {
      html += '<div style="font-size:12px;font-weight:600;color:#3498db;margin-top:6px;margin-bottom:4px;">未覆盖项</div>';
      oc.uncovered.forEach(u => {
        html += `<div class="term-eval-uncovered" style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;"><div>📌 <b>${escapeHtml(u.entity || '')}</b>`;
        if (u.relation) html += ` — ${escapeHtml(u.relation)}`;
        if (u.detail) html += `<div style="font-size:11px;color:#666;margin-top:2px;">${escapeHtml(u.detail)}</div>`;
        html += '</div>' + this.buildLocateButtonHtml({ typeKey: u.entity || '', sourceGraph: 'parse' }, '定位') + '</div>';
      });
    } else if (pe.uncovered_critical_elements && pe.uncovered_critical_elements.length > 0) {
      html += `<div class="term-eval-section"><div class="term-eval-section-title">🔍 缺失的核心要素</div>`;
      pe.uncovered_critical_elements.forEach(elem => {
        html += `<div class="term-eval-uncovered" style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;"><div>📌 <b>缺少要素: ${escapeHtml(elem)}</b></div>${this.buildLocateButtonHtml({ typeKey: elem, sourceGraph: 'ontology' }, '本体论')}</div>`;
      });
      html += `</div>`;
    } else {
      html += '<div style="font-size:12px;color:#27ae60;padding:4px 0;">✅ 本体论覆盖充分，未发现未覆盖实体或关系</div>';
    }

    if (oc.suggestions && oc.suggestions.length > 0) {
      html += '<div style="font-size:12px;font-weight:600;color:#8e44ad;margin-top:8px;margin-bottom:4px;">本体论扩展建议</div>';
      oc.suggestions.forEach(s => {
        html += `<div class="term-eval-suggestion">💡 ${escapeHtml(s)}</div>`;
      });
    }
    html += '</div>';

    scroll.innerHTML = html;
    this.bindJumpEvents(scroll);
    this.updateEnhanceButtonState();
  }

  async handleEvaluate() {
    if (!this.lastResult || !this.inputArea.value.trim()) return;
    
    if (this.evalBtn) { 
      this.evalBtn.disabled = true; 
      this.evalBtn.style.opacity = '0.5'; 
      this.evalBtn.style.cursor = 'wait';
    }
    
    this.setStatus('评估中...', '#8e44ad');
    this.switchTab('termEvalTabContent');
    
    const evalTab = document.getElementById('termEvalTabContent') || document.getElementById('termEvalArea');
    if (evalTab) {
      evalTab.innerHTML = '<div style="color: #94a3b8; padding: 10px;">评估中...</div>';
    }
    
    try {
      const result = await ontologyEvaluate(this.inputArea.value.trim(), this.lastResult.json_result, this.lastResult.row_id);
      this.setStatus('评估完成', '#22c55e');
      this.renderEvalResult(result);
    } catch (err) {
      this.setStatus(`评估失败: ${err.message}`, '#ef4444');
      if (evalTab) {
        evalTab.innerHTML = `<div style="color: #ef4444; padding: 10px;">评估失败: ${escapeHtml(err.message)}</div>`;
      }
    } finally {
      if (this.evalBtn) { 
        this.evalBtn.disabled = false; 
        this.evalBtn.style.opacity = '1'; 
        this.evalBtn.style.cursor = 'pointer';
      }
      this.updateEnhanceButtonState();
    }
  }

  renderEnhancementResult(result) {
    this.lastEnhancementResult = result;
    this.syncEnhancementRuns(result);
    const placeholder = document.getElementById('termEnhancePlaceholder');
    const metaHost = document.getElementById('termEnhanceMeta');
    const treeHost = document.getElementById('termEnhanceTree');
    if (!metaHost || !treeHost) return;

    if (placeholder) placeholder.style.display = 'none';
    metaHost.style.display = 'block';
    treeHost.style.display = 'block';

    const targets = result.targets || [];
    const targetHtml = targets.length
      ? targets.map(item => `
          <span style="display:inline-flex;align-items:center;border-radius:999px;padding:4px 10px;margin:0 8px 8px 0;background:${item.priority === 'high' ? '#fee2e2' : '#eef2ff'};color:${item.priority === 'high' ? '#b91c1c' : '#3730a3'};font-size:12px;">
            ${escapeHtml(item.label || item.entity || '')}
          </span>
        `).join('')
      : '<span style="color:#94a3b8;">本轮未识别到明确补强目标。</span>';
    const formatDeltaSummary = (counts, emptyText) => {
      const added = counts?.added || {};
      const updated = counts?.updated || {};
      const parts = [];
      if (Object.keys(added).length) {
        parts.push(`新增：${Object.entries(added).map(([key, value]) => `${escapeHtml(key)} +${value}`).join('，')}`);
      }
      if (Object.keys(updated).length) {
        parts.push(`更新：${Object.entries(updated).map(([key, value]) => `${escapeHtml(key)} +${value}`).join('，')}`);
      }
      return parts.length ? parts.join('；') : emptyText;
    };
    const entitySummary = formatDeltaSummary(result.delta?.entity_counts, '暂无实体变化');
    const relationSummary = formatDeltaSummary(result.delta?.relation_type_counts, '暂无关系变化');
    const previewActive = store.getState().parseEnhancementPreviewActive && store.getState().parseEnhancementPreviewRunId === result.run_id;
    const appliedVersion = result.merged_version_id ? `版本 ${result.merged_version_id}` : '';
    const appliedStamp = result.apply_status === 'merged'
      ? `<div style="position:absolute;top:10px;right:12px;padding:4px 10px;border:1px solid #16a34a;border-radius:999px;color:#166534;background:#f0fdf4;font-size:11px;font-weight:700;">已应用${appliedVersion ? ` · ${escapeHtml(appliedVersion)}` : ''}</div>`
      : '';

    metaHost.innerHTML = `
      <div style="position:relative;">
        ${appliedStamp}
        <div style="font-size:14px;font-weight:700;color:#0f172a;">✨ 增量解析结果</div>
        <div style="margin-top:6px;font-size:13px;color:#475569;line-height:1.7;">${escapeHtml(result.summary || '已生成专项补强结果。')}</div>
        <div style="margin-top:10px;font-size:12px;color:#334155;font-weight:700;">增强目标</div>
        <div style="margin-top:6px;">${targetHtml}</div>
        <div style="margin-top:6px;font-size:12px;color:#334155;font-weight:700;">差异摘要</div>
        <div style="margin-top:4px;font-size:12px;color:#64748b;line-height:1.7;">实体差异：${entitySummary}</div>
        <div style="margin-top:2px;font-size:12px;color:#64748b;line-height:1.7;">关系差异：${relationSummary}</div>
        <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;">
          <button id="btnEnhancementPreview" style="padding:7px 14px;border:none;border-radius:8px;background:${previewActive ? '#cbd5e1' : '#2563eb'};color:#fff;cursor:${result.apply_status === 'merged' || previewActive ? 'default' : 'pointer'};" ${result.apply_status === 'merged' || previewActive ? 'disabled' : ''}>应用预览</button>
          <button id="btnEnhancementExitPreview" style="padding:7px 14px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#475569;display:${previewActive ? 'inline-flex' : 'none'};">退出预览</button>
          <button id="btnEnhancementMerge" style="padding:7px 14px;border:none;border-radius:8px;background:${result.apply_status === 'merged' ? '#cbd5e1' : '#16a34a'};color:#fff;cursor:${result.apply_status === 'merged' ? 'default' : 'pointer'};" ${result.apply_status === 'merged' ? 'disabled' : ''}>数据合并</button>
        </div>
      </div>
    `;

    const previewBtn = metaHost.querySelector('#btnEnhancementPreview');
    const exitPreviewBtn = metaHost.querySelector('#btnEnhancementExitPreview');
    const mergeBtn = metaHost.querySelector('#btnEnhancementMerge');
    if (previewBtn) previewBtn.addEventListener('click', () => this.handlePreviewEnhancementApply());
    if (exitPreviewBtn) exitPreviewBtn.addEventListener('click', () => this.handleExitPreview());
    if (mergeBtn) mergeBtn.addEventListener('click', () => this.handleMergeEnhancement());

    const enhancementData = result.changed_enhancement_payload || {};
    treeHost.innerHTML = '';
    if (Object.keys(enhancementData).length) {
      treeHost.appendChild(this.buildJsonTree(enhancementData, true));
    } else {
      treeHost.innerHTML = '<div style="padding: 4px 0; color: #94a3b8;">本轮增量结果与原解析一致，未产生需要单独展示的变化项。</div>';
    }
  }

  async handleEnhanceParse() {
    if (!this.lastResult || !this.lastEvalResult || !this.inputArea?.value.trim()) return;

    this.isEnhancing = true;
    this.updateEnhanceButtonState();
    if (this.enhanceBtn) {
      this.enhanceBtn.textContent = '✨ 增量解析中...';
      this.enhanceBtn.classList.add('loading');
    }

    const placeholder = document.getElementById('termEnhancePlaceholder');
    const metaHost = document.getElementById('termEnhanceMeta');
    const treeHost = document.getElementById('termEnhanceTree');
    if (placeholder) {
      placeholder.style.display = 'block';
      placeholder.textContent = '正在根据问题与评估缺口进行增量解析...';
    }
    if (metaHost) {
      metaHost.style.display = 'none';
      metaHost.innerHTML = '';
    }
    if (treeHost) {
      treeHost.style.display = 'none';
      treeHost.innerHTML = '';
    }
    this.switchTab('termEnhanceTabContent');
    this.setStatus('专项增量解析中...', '#2563eb');

    try {
      const result = await parseEnhancement(
        this.inputArea.value.trim(),
        this.lastResult.json_result,
        this.lastResult.row_id,
        this.lastQualityResult,
        this.lastEvalResult
      );
      store.setState({
        parseEnhancementPreviewActive: false,
        parseEnhancementPreviewRunId: null,
        parseEnhancementPreviewPatch: null,
      });
      this.renderEnhancementResult(result);
      this.setStatus('专项增量解析完成', '#22c55e');
    } catch (err) {
      this.setStatus(`增量解析失败: ${err.message}`, '#ef4444');
      if (placeholder) {
        placeholder.style.display = 'block';
        placeholder.textContent = `增量解析失败: ${err.message}`;
      }
    } finally {
      this.isEnhancing = false;
      if (this.enhanceBtn) {
        this.enhanceBtn.textContent = '✨ 增量解析';
        this.enhanceBtn.classList.remove('loading');
      }
      this.updateEnhanceButtonState();
    }
  }
  
  switchTab(targetId) {
    const termBody = document.getElementById('termBody');
    if (!termBody) return;
    
    // Find the tab element to determine its group
    const tabEl = termBody.querySelector(`.term-tab[data-target="${targetId}"]`);
    if (!tabEl) return;
    
    const tabGroup = tabEl.closest('.term-col');
    if (!tabGroup) return;
    
    tabGroup.querySelectorAll('.term-tab').forEach(t => {
      if (t.getAttribute('data-target') === targetId) t.classList.add('active');
      else t.classList.remove('active');
    });
    
    tabGroup.querySelectorAll('.term-content-pane, .term-json-area').forEach(p => {
      if (p.id === targetId) p.style.display = 'flex';
      else p.style.display = 'none';
    });
    store.setState({ activeTab: targetId });

    // Handle "图" Tab specially if needed, currently rendered by ParseGraph toolbar
    if (targetId === 'termVisContainer' || targetId === 'termGraphInfo') {
          const graphNote = this.container ? this.container.querySelector('#graphFooterNote') : null;
          if (graphNote) graphNote.textContent = '图谱控制台已启用';
          
          // Show the tools
          const termGraphInfo = document.getElementById('termGraphInfo');
          if (termGraphInfo) {
            termGraphInfo.style.display = 'block';
          }
          const termGraphModeBar = document.getElementById('termGraphModeBar');
          if (termGraphModeBar) {
            termGraphModeBar.style.display = 'flex';
          }
          this.notifyGraphTabVisible(false);
        } else {
          const termGraphInfo = document.getElementById('termGraphInfo');
          if (termGraphInfo) {
            termGraphInfo.style.display = 'none';
          }
          const termGraphModeBar = document.getElementById('termGraphModeBar');
          if (termGraphModeBar) {
            termGraphModeBar.style.display = 'none';
          }
        }
  }

  bindJumpEvents(container) {
    if (!container) return;
    const btns = container.querySelectorAll('.qa-locate-btn, .term-eval-uncovered');
    btns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const target = btn.getAttribute('data-target');
        const sourceGraph = btn.getAttribute('data-source-graph') || 'parse';
        if (target) {
          store.setState({ 
            locateTarget: { 
              typeKey: target, 
              nodeType: target,
              sourceGraph: sourceGraph,
              timestamp: Date.now()
            }
          });
        }
      });
    });
  }
}
