import re

with open('/root/remote-test/visualization/ontology-refactored/src/components/TerminalPanel.js', 'r', encoding='utf-8') as f:
    content = f.read()

def escape_repl(match):
    return match.group(0).replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')

# 1. Update renderQualityIssues
new_quality = """  renderQualityIssues(qa, focusNodeData) {
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
  }"""

# 2. Update renderEvalResult
new_eval = """  renderEvalResult(result) {
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
  }"""

content = re.sub(r'  renderQualityIssues\(qa, focusNodeData\) \{.*?\n  async handleQualityAnalysis', new_quality + '\n\n  async handleQualityAnalysis', content, flags=re.DOTALL)
content = re.sub(r'  renderEvalResult\(result\) \{.*?\n  async handleEvaluate', new_eval + '\n\n  async handleEvaluate', content, flags=re.DOTALL)

with open('/root/remote-test/visualization/ontology-refactored/src/components/TerminalPanel.js', 'w', encoding='utf-8') as f:
    f.write(content)
