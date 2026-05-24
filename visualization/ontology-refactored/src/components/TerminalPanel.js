import { store } from '../store/index.js';
import { safeGetElement } from '../utils/dom.js';
import { escapeHtml } from '../utils/formatter.js';
import { parseQuality, saveResult, ontologyEvaluate } from '../api/backend.js';

export class TerminalPanel {
  constructor() {
    this.panel = safeGetElement('parseTerminal');
    this.container = document.getElementById('termBody'); // use termBody as container
    this.dragHandle = safeGetElement('termDragHandle');
    this.closeBtn = safeGetElement('btnTermClose');
    
    this.ensureTerminalUI();
    
    this.inputArea = safeGetElement('termInputArea');
    this.parseBtn = safeGetElement('btnTermParse');
    this.saveBtn = safeGetElement('btnTermSave');
    this.saveBtnBottom = safeGetElement('btnTermSaveBottom');
    this.clearBtn = safeGetElement('btnTermClear');
    this.evalBtn = safeGetElement('btnTermEvaluate');
    this.statusArea = safeGetElement('termStatusArea');
    
    this.lastResult = null;
    this.lastQualityResult = null;
    this.lastEvalResult = null;
    
    this.bindEvents();
    
    // Listen for cross-graph focus to update issues view
    store.subscribe(state => {
      if (state.selectedGraph === 'parse' && state.selectedNodeId && this.lastQualityResult) {
        // Rerender issues to update the focus section
        this.renderQualityIssues(this.lastQualityResult, state.parseNodeData);
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
          
          <div id="termJsonColumn" class="term-col term-col-middle" style="width: 35%; flex: none; background: #fff;">
            <div class="term-col-header" style="border-bottom: 1px solid #e0e0e0; background: #fbfcfe;">
              <div class="term-tab-group" id="jsonTabGroup">
                <span class="term-tab active" data-target="termJsonArea">
                  <span class="term-tab-label">📄 解析数据</span>
                </span>
                <!-- More tabs can be added here in the future -->
              </div>
            </div>
            <div style="flex: 1; position: relative; overflow: hidden; display: flex; flex-direction: column;">
              <div class="term-json-area term-content-pane" id="termJsonArea" style="flex: 1; display: flex; flex-direction: column;">
                <div class="term-json-placeholder" id="termJsonPlaceholder">等待解析结果...</div>
                <div id="termJsonTree" style="display:none; font-family: monospace; font-size: 12px; line-height: 1.5; color: #333; padding: 10px; flex: 1; overflow: auto;"></div>
              </div>
            </div>
            <div class="term-eval-row">
              <button class="btn-eval" id="btnTermEvaluate" disabled>🔍 本体论评估</button>
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
          
          // Ensure termGraphInfo exists for the toolbar
          if (!document.getElementById('termGraphInfo')) {
            const graphInfo = document.createElement('div');
            graphInfo.id = 'termGraphInfo';
            graphInfo.style.padding = '12px';
            graphInfo.style.flex = '1';
            graphInfo.style.height = '100%';
            graphInfo.style.boxSizing = 'border-box';
            graphInfo.style.background = '#fff';
            visContainer.appendChild(graphInfo);
          }
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
      splitterLeft.addEventListener('mousedown', (e) => {
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
      splitterRight.addEventListener('mousedown', (e) => {
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
        // Sync main view bottom
        const mainView = document.getElementById('kgMainView');
        if (mainView) {
          mainView.style.height = `calc(100vh - ${newHeight}px)`;
        }

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
        isDragging = false;
        document.body.style.cursor = '';
      });
    }

    if (this.closeBtn) {
      this.closeBtn.addEventListener('click', () => {
        this.panel.classList.remove('expanded');
        const bar = document.getElementById('termCollapsedBar');
        const termPanel = this.panel.querySelector('.terminal-panel');
        if (bar) bar.style.display = 'flex';
        if (termPanel) termPanel.style.display = 'none';
        const mainView = document.getElementById('kgMainView');
        if (mainView) mainView.style.height = 'calc(100vh - 40px)'; // collapsed bar height
      });
    }

    const collapsedBar = document.getElementById('termCollapsedBar');
    if (collapsedBar) {
      collapsedBar.addEventListener('click', () => {
        this.panel.classList.add('expanded');
        collapsedBar.style.display = 'none';
        const termPanel = this.panel.querySelector('.terminal-panel');
        if (termPanel) termPanel.style.display = 'flex';
        const mainView = document.getElementById('kgMainView');
        if (mainView) mainView.style.height = `calc(100vh - ${this.panel.offsetHeight}px)`;
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

    const heightBtns = this.panel?.querySelectorAll('.term-height-btn');
    if (heightBtns) {
      heightBtns.forEach(btn => {
        btn.addEventListener('click', () => {
          heightBtns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const h = btn.getAttribute('data-height');
          const newHeight = (window.innerHeight * parseInt(h, 10)) / 100;
          this.panel.style.height = `${newHeight}px`;
          const mainView = document.getElementById('kgMainView');
          if (mainView) {
            mainView.style.height = `calc(100vh - ${newHeight}px)`;
          }

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
  }

  ensureTerminalExpanded() {
    if (this.panel && !this.panel.classList.contains('expanded')) {
      this.panel.classList.add('expanded');
      const bar = document.getElementById('termCollapsedBar');
      const termPanel = this.panel.querySelector('.terminal-panel');
      if (bar) bar.style.display = 'none';
      if (termPanel) termPanel.style.display = 'flex';
      const mainView = document.getElementById('kgMainView');
      if (mainView) mainView.style.height = `calc(100vh - ${this.panel.offsetHeight}px)`;
    }
  }

  renderJson(jsonResult) {
    const treeHost = document.getElementById('termJsonTree');
    const placeholder = document.getElementById('termJsonPlaceholder');
    
    if (treeHost && placeholder) {
      if (jsonResult) {
        placeholder.style.display = 'none';
        treeHost.style.display = 'block';
        
        try {
          const jsonObj = typeof jsonResult === 'string' ? JSON.parse(jsonResult) : jsonResult;
          treeHost.innerHTML = '';
          treeHost.appendChild(this.buildJsonTree(jsonObj, true));
        } catch (e) {
          treeHost.innerHTML = `<pre style="color:red">JSON parse error: ${e.message}</pre>`;
        }
      } else {
        placeholder.style.display = 'block';
        treeHost.style.display = 'none';
      }
    }
  }

  buildJsonTree(obj, isRoot = false) {
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
        
        const childContainer = this.buildJsonTree(obj[key]);
        childContainer.style.display = isCollapsed ? 'none' : 'block';
        
        const bracketEnd = document.createElement('div');
        bracketEnd.textContent = (Array.isArray(obj[key]) ? ']' : '}') + (idx < keys.length - 1 ? ',' : '');
        bracketEnd.style.display = isCollapsed ? 'none' : 'block';
        
        const collapsedHint = document.createElement('span');
        collapsedHint.style.color = '#bbb';
        collapsedHint.style.display = isCollapsed ? 'inline' : 'none';
        collapsedHint.textContent = ' ... ' + (Array.isArray(obj[key]) ? ']' : '}') + (idx < keys.length - 1 ? ',' : '');
        line.appendChild(collapsedHint);
        
        toggleBtn.addEventListener('click', () => {
          isCollapsed = !isCollapsed;
          toggleBtn.textContent = isCollapsed ? '▶' : '▼';
          childContainer.style.display = isCollapsed ? 'none' : 'block';
          bracketEnd.style.display = isCollapsed ? 'none' : 'block';
          collapsedHint.style.display = isCollapsed ? 'inline' : 'none';
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
      this.setStatus(`解析成功 (得分: ${result.score})`, '#27ae60');
      
      this.renderJson(result.json_result);
      
      if (this.evalBtn) this.evalBtn.disabled = false;
      if (this.saveBtn) this.saveBtn.disabled = false;
      if (this.saveBtnBottom) this.saveBtnBottom.disabled = false;

      if (result.json_result) {
        store.setState({ 
          parseGraphData: result,
          isParseResultAvailable: true,
          isOntologyVisible: true
        });
        
        // Auto-run quality analysis
        this.switchTab('termIssuesArea');
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
      const qa = await parseQuality(jsonResult);
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
    const focus = { target: null, parsingIssues: [], coverageItems: [], uncoveredItems: [], parsingSuggestions: [], ontologySuggestions: [] };

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
  }

  async handleEvaluate() {
    if (!this.lastResult || !this.inputArea.value.trim()) return;
    
    if (this.evalBtn) { 
      this.evalBtn.disabled = true; 
      this.evalBtn.style.opacity = '0.5'; 
      this.evalBtn.style.cursor = 'wait';
    }
    
    this.setStatus('评估中...', '#8e44ad');
    this.switchTab('termEvalArea');
    
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

    // Handle "图" Tab specially if needed, currently rendered by ParseGraph toolbar
    if (targetId === 'termVisContainer' || targetId === 'termGraphInfo') {
          const graphNote = this.container ? this.container.querySelector('#graphFooterNote') : null;
          if (graphNote) graphNote.textContent = '图谱控制台已启用';
          
          // Show the tools
          const termGraphInfo = document.getElementById('termGraphInfo');
          if (termGraphInfo) {
            termGraphInfo.style.display = 'block';
          }
        } else {
          const termGraphInfo = document.getElementById('termGraphInfo');
          if (termGraphInfo) {
            termGraphInfo.style.display = 'none';
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
