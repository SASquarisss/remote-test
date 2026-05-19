import os
import re

code = """import { store } from '../store/index.js';
import { safeGetElement } from '../utils/dom.js';
import { escapeHtml } from '../utils/formatter.js';
import { parseQuality, saveResult, ontologyEvaluate } from '../api/backend.js';

export class TerminalPanel {
  constructor() {
    this.panel = safeGetElement('parseTerminal');
    this.container = safeGetElement('terminalPanelContainer');
    this.dragHandle = safeGetElement('terminalDragHandle');
    this.closeBtn = safeGetElement('termCloseBtn');
    
    this.inputArea = safeGetElement('termInputArea');
    this.parseBtn = safeGetElement('btnTermParse');
    this.saveBtn = safeGetElement('btnTermSave');
    this.evalBtn = safeGetElement('btnTermEvaluate');
    this.statusArea = safeGetElement('termStatusArea');
    
    this.lastResult = null;
    this.lastQualityResult = null;
    this.lastEvalResult = null;
    
    this.bindEvents();
    this.ensureTerminalUI();
    
    // Listen for cross-graph focus to update issues view
    store.subscribe(state => {
      if (state.selectedGraph === 'parse' && state.selectedNodeId && this.lastQualityResult) {
        // Rerender issues to update the focus section
        this.renderQualityIssues(this.lastQualityResult, state.parseNodeData);
      }
    });
  }

  ensureTerminalUI() {
    // 确保终端有正确的布局
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
    }
  }

  bindEvents() {
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
      });
      
      document.addEventListener('mouseup', () => {
        isDragging = false;
        document.body.style.cursor = '';
      });
    }

    if (this.closeBtn) {
      this.closeBtn.addEventListener('click', () => {
        this.panel.style.display = 'none';
        const mainView = document.getElementById('kgMainView');
        if (mainView) mainView.style.height = '100vh';
      });
    }

    if (this.parseBtn) {
      this.parseBtn.addEventListener('click', () => this.handleParse());
    }

    if (this.saveBtn) {
      this.saveBtn.addEventListener('click', () => this.handleSave());
    }

    if (this.evalBtn) {
      this.evalBtn.addEventListener('click', () => this.handleEvaluate());
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
      
      if (result.json_result) {
        store.setState({ 
          parseGraphData: result.json_result,
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
    
    let html = '';
    
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
    } else {
      html += '<div style="padding:8px 14px;background:#e8f8f5;border-bottom:1px solid #c3e6cb;font-size:12px;color:#27ae60;">✅ 未发现明显解析问题</div>';
    }

    // ── Focus Section ──
    if (focusNodeData) {
      const targetLabel = focusNodeData.label || focusNodeData.id;
      const targetType = focusNodeData.nodeType || '';
      
      const relatedEntities = [];
      const relatedIssues = qa.issues ? qa.issues.filter(i => i.target === targetLabel || i.entity === targetLabel) : [];
      
      if (qa.categories) {
        qa.categories.forEach(cat => {
          cat.entities.forEach(ent => {
            if (ent.type === targetType || ent.type_label === targetType) {
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
            html += `<div class="term-eval-issue ${sevClass}" style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px;padding:6px;border-radius:4px;background:#fff;border-left:3px solid ${sevClass === 'critical' ? '#e74c3c' : (sevClass === 'major' ? '#e67e22' : '#f1c40f')}">`;
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
        const catId = 'cat_' + cat.category.replace(/[^a-zA-Z0-9]/g, '_');
        
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
            const entId = catId + '_' + entity.type.replace(/[^a-zA-Z0-9]/g, '_');
            
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
            
            html += '<div style="padding:4px 10px 8px;font-size:11px;color:#666;">';
            html += `<div style="display:flex;gap:12px;margin-bottom:4px;"><span>实例数量: <strong>${entity.instance_count}</strong></span><span>解析字段: <strong>${entity.fields_count}</strong></span></div>`;
            if (entity.missing_fields && entity.missing_fields.length > 0) {
              html += `<div style="color:#e67e22;margin-top:2px;">待补核心字段: <strong>${escapeHtml(entity.missing_fields.join('、'))}</strong></div>`;
            }
            html += '</div></div></div>';
          });
        }
        html += '</div></div>';
      });
    } else {
      // Fallback for simple issues list if no categories provided
      if (qa.issues && qa.issues.length > 0) {
        qa.issues.forEach(issue => {
          const msg = typeof issue === 'object' ? (issue.message || issue.description || issue.msg || JSON.stringify(issue)) : issue;
          const severity = typeof issue === 'object' ? (issue.severity || 'Error') : 'Error';
          const target = typeof issue === 'object' ? (issue.target || issue.entity || '') : '';
          html += `
            <div class="term-issues-item" data-target="${escapeHtml(target)}" style="cursor: ${target ? 'pointer' : 'default'}">
              <strong style="color: #e74c3c;">[${escapeHtml(severity)}]</strong> ${escapeHtml(msg)}
            </div>
          `;
        });
      }
    }
    
    html += '</div>';
    issuesTab.innerHTML = html;
    this.bindJumpEvents(issuesTab);
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
      this.setStatus(`保存成功 (${result.row_id || this.lastResult.row_id} -> ${result.target_layer || targetLayer})`, '#27ae60');
    } catch (err) {
      if (this.saveBtn) {
        this.saveBtn.textContent = '💾 保存';
        this.saveBtn.disabled = false;
      }
      this.setStatus(`保存失败: ${err.message}`, '#e74c3c');
    }
  }

  renderEvalResult(result) {
    this.lastEvalResult = result;
    const evalTab = document.getElementById('termEvalTabContent') || document.getElementById('termEvalArea');
    if (!evalTab) return;
    
    const pe = result.parsing_evaluation || {};
    
    // Header
    let html = `
      <div class="term-eval-section">
        <div class="term-eval-section-title">
          <span>🎯 本体论评分</span>
          <span class="term-eval-score-badge" style="background: #f3e5f5; color: #8e44ad; margin-left: 10px;">总分: ${pe.total_score || 0}/100</span>
          <span class="term-eval-score-badge" style="background: #e8f8f5; color: #27ae60;">置信度: ${pe.confidence || '-'}</span>
        </div>
        ${pe.comprehensive_feedback ? `<div style="font-size:12px;color:#555;margin-top:8px;line-height:1.6;">${escapeHtml(pe.comprehensive_feedback)}</div>` : ''}
      </div>
    `;

    // Dimensions
    if (pe.dimensions) {
      html += `<div class="term-eval-section"><div class="term-eval-section-title">📊 维度评估</div>`;
      for (const [key, dim] of Object.entries(pe.dimensions)) {
        const pct = Math.max(0, Math.min(100, (dim.score / 100) * 100));
        let color = '#27ae60';
        if (pct < 60) color = '#e74c3c';
        else if (pct < 80) color = '#f39c12';
        
        html += `
          <div class="term-eval-dim">
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
              <strong>${escapeHtml(key)}</strong>
              <span style="color: ${color}; font-weight: bold;">${dim.score}</span>
            </div>
            <div class="term-eval-dim-bar">
              <div class="term-eval-dim-fill" style="width: ${pct}%; background: ${color};"></div>
            </div>
            ${dim.feedback ? `<div style="font-size: 11px; color: #777; margin-top: 4px;">${escapeHtml(dim.feedback)}</div>` : ''}
          </div>
        `;
      }
      html += `</div>`;
    }

    // Issues
    if (pe.issues && pe.issues.length > 0) {
      html += `<div class="term-eval-section"><div class="term-eval-section-title">⚠️ 发现的问题</div>`;
      pe.issues.forEach(issue => {
        const levelClass = issue.severity === 'high' ? 'critical' : (issue.severity === 'medium' ? 'major' : 'minor');
        html += `
          <div class="term-eval-issue ${levelClass}" data-target="${escapeHtml(issue.target || '')}" style="cursor: ${issue.target ? 'pointer' : 'default'}">
            <strong>[${escapeHtml(issue.severity || 'info')}]</strong> ${escapeHtml(issue.description || '')}
            ${issue.target ? this.buildLocateButtonHtml({ typeKey: issue.target, sourceGraph: 'parse' }, '定位') : ''}
          </div>
        `;
      });
      html += `</div>`;
    }

    // Uncovered
    if (pe.uncovered_critical_elements && pe.uncovered_critical_elements.length > 0) {
      html += `<div class="term-eval-section"><div class="term-eval-section-title">🔍 缺失的核心要素</div>`;
      pe.uncovered_critical_elements.forEach(elem => {
        html += `
          <div class="term-eval-uncovered" data-target="${escapeHtml(elem)}" style="cursor: pointer;">
            缺少要素: <strong>${escapeHtml(elem)}</strong>
            ${this.buildLocateButtonHtml({ typeKey: elem, sourceGraph: 'ontology' }, '本体论')}
          </div>
        `;
      });
      html += `</div>`;
    }

    evalTab.innerHTML = html;
    this.bindJumpEvents(evalTab);
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
    
    termBody.querySelectorAll('.term-tab').forEach(t => {
      if (t.getAttribute('data-target') === targetId) t.classList.add('active');
      else t.classList.remove('active');
    });
    
    termBody.querySelectorAll('.term-content-pane').forEach(p => {
      if (p.id === targetId) p.style.display = 'flex';
      else p.style.display = 'none';
    });
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
"""

with open('/root/remote-test/visualization/ontology-refactored/src/components/TerminalPanel.js', 'w', encoding='utf-8') as f:
    f.write(code)
