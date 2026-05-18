import { store } from '../store/index.js';
import { ENTITY_DATA, ZH_LABELS, RELATION_EDGES } from '../data/schema.js';
import { safeGetElement } from '../utils/dom.js';
import { escapeHtml } from '../utils/formatter.js';

function parseNodeTitleLines(title) {
  if (!title) return [];
  return String(title).split(/<br\s*\/?>/i).map(line => {
    return line.replace(/<[^>]+>/g, '').trim();
  }).filter(Boolean);
}

function buildBusinessSummaryText(parts) {
  return parts.filter(Boolean).join('，');
}

export class DetailPanel {
  constructor() {
    this.panel = safeGetElement('detailPanel');
    this.title = safeGetElement('panelTitle');
    this.tabInfo = safeGetElement('panelTabInfo');
    this.tabNeighbors = safeGetElement('panelTabNeighbors');
    this.panelTabs = safeGetElement('panelTabs');
    this.closeBtn = safeGetElement('panelClose');
    
    this.bindEvents();
    store.subscribe(state => this.render(state));
  }
  
  bindEvents() {
    if(this.closeBtn) {
      this.closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        store.setState({ isPanelOpen: false });
      });
    }
    
    // Tab switching
    if (this.panelTabs) {
      this.panelTabs.addEventListener('click', (e) => {
        if (e.target.classList.contains('panel-tab')) {
          this.panelTabs.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
          e.target.classList.add('active');
          
          const targetId = e.target.getAttribute('data-target');
          const contents = this.panel.querySelectorAll('.panel-tab-content');
          contents.forEach(c => c.classList.remove('active'));
          const targetContent = document.getElementById(targetId);
          if (targetContent) targetContent.classList.add('active');
          
          if (targetId === 'panelTabNeighbors' && !targetContent.hasAttribute('data-rendered')) {
            this.renderNeighbors(store.getState());
            targetContent.setAttribute('data-rendered', 'true');
          }
        }
      });
    }
  }

  buildSummaryCard(title, subtitle, chips, statsHtml) {
    let html = '<div class="panel-section">';
    html += '<div class="summary-kicker">当前分析对象</div>';
    html += '<div class="summary-title">' + escapeHtml(title || '未命名对象') + '</div>';
    if (subtitle) html += '<div class="summary-subtitle">' + subtitle + '</div>';
    if (chips && chips.length) {
      html += '<div class="summary-chip-row">';
      chips.forEach(chip => {
        if (!chip) return;
        html += '<span class="summary-chip">' + escapeHtml(chip) + '</span>';
      });
      html += '</div>';
    }
    if (statsHtml) html += '<div class="summary-grid" style="margin-top:12px;">' + statsHtml + '</div>';
    html += '</div>';
    return html;
  }

  buildSummaryMetric(value, label) {
    return `<div class="summary-card"><div class="summary-card-value">${escapeHtml(String(value))}</div><div class="summary-card-label">${escapeHtml(label)}</div></div>`;
  }

  buildKeyValueSection(title, items) {
    const valid = (items || []).filter(item => item && item.value !== undefined && item.value !== null && String(item.value).trim() !== '');
    let html = `<div class="panel-section"><div class="panel-section-title">${escapeHtml(title)}</div>`;
    if (!valid.length) {
      html += '<div class="empty-hint">暂无可展示信息</div></div>';
      return html;
    }
    html += '<div class="kv-list">';
    valid.forEach(item => {
      html += `<div class="kv-item"><div class="kv-key">${escapeHtml(item.label)}</div><div class="kv-val">${escapeHtml(String(item.value))}</div></div>`;
    });
    html += '</div></div>';
    return html;
  }

  renderNeighbors(state) {
    if (!this.tabNeighbors) return;
    
    let html = '';
    
    if (state.selectedGraph === 'ontology' && state.selectedNodeId) {
      const typeName = state.selectedNodeId;
      const outgoing = RELATION_EDGES.filter(r => r[1] === typeName);
      const incoming = RELATION_EDGES.filter(r => r[2] === typeName);
      
      html += `<div class="panel-section"><div class="panel-section-title">关联路径</div>`;
      if (outgoing.length > 0) {
        html += '<div style="margin-bottom: 12px;"><strong>发起的关联 (Out)</strong><ul>';
        outgoing.forEach(r => {
          html += `<li>→ ${escapeHtml(r[2])} <span style="color:#888; font-size:12px;">(${escapeHtml(r[0])})</span></li>`;
        });
        html += '</ul></div>';
      }
      if (incoming.length > 0) {
        html += '<div><strong>被指向的关联 (In)</strong><ul>';
        incoming.forEach(r => {
          html += `<li>← ${escapeHtml(r[1])} <span style="color:#888; font-size:12px;">(${escapeHtml(r[0])})</span></li>`;
        });
        html += '</ul></div>';
      }
      if (outgoing.length === 0 && incoming.length === 0) {
        html += '<div class="empty-hint">暂无直接关联的实体路径</div>';
      }
      html += '</div>';
    } else if (state.selectedGraph === 'parse' && state.selectedNodeId && state.parseGraphData) {
      const nodeId = state.selectedNodeId;
      const edges = state.parseGraphData.edges || [];
      const nodesMap = {};
      (state.parseGraphData.nodes || []).forEach(n => nodesMap[n.id] = n);
      
      const outgoing = edges.filter(e => e.from === nodeId);
      const incoming = edges.filter(e => e.to === nodeId);
      const allConnectedEdges = [...outgoing, ...incoming];
      const allConnectedNodeIds = new Set([...outgoing.map(e => e.to), ...incoming.map(e => e.from)]);
      
      const centerNode = nodesMap[nodeId] || { id: nodeId, label: nodeId };
      const centerLabel = centerNode.label || centerNode.title || nodeId;
      const centerType = centerNode.nodeType || '未分类';

      let paths = [];
      allConnectedNodeIds.forEach(cid => {
        const neighborNode = nodesMap[cid];
        const neighborLabel = neighborNode ? (neighborNode.label || neighborNode.title || cid) : cid;
        const neighborType = (neighborNode && neighborNode.nodeType) || '';
        
        let relLabel = '';
        let relEdgeId = '';
        let direction = 'unknown';
        
        const outEdge = outgoing.find(e => e.to === cid);
        const inEdge = incoming.find(e => e.from === cid);
        
        if (outEdge) {
          relLabel = outEdge.label || outEdge.relationName || '关联';
          relEdgeId = outEdge.id;
          direction = 'outgoing';
        } else if (inEdge) {
          relLabel = inEdge.label || inEdge.relationName || '关联';
          relEdgeId = inEdge.id;
          direction = 'incoming';
        }
        
        paths.push({
          neighborId: cid,
          neighborLabel: neighborLabel,
          neighborType: neighborType,
          relLabel: relLabel,
          relEdgeId: relEdgeId,
          direction: direction
        });
      });

      const groupedPaths = {};
      paths.forEach(p => {
        const key = p.neighborType || '未分类';
        if (!groupedPaths[key]) groupedPaths[key] = [];
        groupedPaths[key].push(p);
      });

      html += '<div class="panel-section">';
      html += '<div class="panel-section-title">当前焦点</div>';
      html += '<div class="summary-highlight"><strong>' + escapeHtml(centerLabel) + '</strong>';
      if (centerType) html += ' · ' + escapeHtml(centerType);
      html += '。当前共发现 <strong>' + paths.length + '</strong> 条直接关联路径。</div>';
      html += '</div>';

      html += '<div class="panel-section"><div class="panel-section-title">🛤️ 关联路径 (' + paths.length + ')</div>';
      if (paths.length === 0) {
        html += '<div class="empty-hint">无关联路径</div>';
      } else {
        Object.keys(groupedPaths).sort().forEach(groupName => {
          html += '<div style="margin-bottom:10px;">';
          html += '<div style="font-size:11px;color:#64748b;font-weight:700;margin-bottom:6px;">' + escapeHtml(groupName) + ' · ' + groupedPaths[groupName].length + '</div>';
          groupedPaths[groupName].forEach(p => {
            let actualFrom = '', actualTo = '';
            const eData = edges.find(e => e.id === p.relEdgeId);
            if (eData) { actualFrom = eData.from; actualTo = eData.to; }
            
            const fromLabel = (actualFrom === nodeId) ? centerLabel : p.neighborLabel;
            const toLabel = (actualTo === nodeId) ? centerLabel : p.neighborLabel;
            const accent = p.direction === 'incoming' ? '#e74c3c' : '#2980b9';
            
            html += '<div class="path-item" data-path-edge="' + escapeHtml(String(p.relEdgeId)) + '" data-path-to="' + escapeHtml(String(p.neighborId)) + '"';
            html += ' style="cursor:pointer;padding:10px 12px;border:1px solid #e2e8f0;border-radius:10px;background:#fff;margin-bottom:8px;box-shadow:0 4px 12px rgba(15,23,42,0.04);">';
            html += '<div style="display:flex;align-items:center;gap:8px;">';
            html += '<span style="font-size:11px;color:' + accent + ';font-weight:700;">' + (p.direction === 'incoming' ? '进入路径' : '发出路径') + '</span>';
            html += '<span style="margin-left:auto;font-size:10px;color:#999;">' + escapeHtml(p.neighborType || '未分类') + '</span>';
            html += '</div>';
            html += '<div style="display:flex;align-items:center;gap:6px;margin-top:6px;font-size:12px;line-height:1.6;">';
            html += '<span style="font-weight:600;color:#0f172a;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + escapeHtml(String(fromLabel)) + '">' + escapeHtml(String(fromLabel)) + '</span>';
            html += '<span style="color:' + accent + ';font-weight:700;">→</span>';
            html += '<span style="border:1px solid ' + accent + ';border-radius:999px;padding:1px 8px;font-size:10px;color:' + accent + ';">' + escapeHtml(p.relLabel) + '</span>';
            html += '<span style="color:' + accent + ';font-weight:700;">→</span>';
            html += '<span style="font-weight:600;color:#0f172a;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + escapeHtml(String(toLabel)) + '">' + escapeHtml(String(toLabel)) + '</span>';
            html += '</div>';
            html += '</div>';
          });
          html += '</div>';
        });
      }
      html += '</div>';

      html += '<div class="panel-section"><div class="panel-section-title">🔗 邻居节点 (' + allConnectedNodeIds.size + ')</div>';
      if (allConnectedNodeIds.size === 0) {
        html += '<div class="empty-hint">无关联节点</div>';
      } else {
        allConnectedNodeIds.forEach(cid => {
          const cNode = nodesMap[cid];
          const cLabel = cNode ? (cNode.label || cNode.title || cid) : cid;
          html += '<div class="rel-item" data-target="' + cid + '" style="cursor:pointer; display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">';
          html += '<span class="rel-source">' + escapeHtml(String(cLabel)) + '</span>';
          html += '<span class="rel-meta" style="font-size:11px;color:#888;">' + escapeHtml(cNode && cNode.nodeType ? cNode.nodeType : '') + '</span>';
          html += '</div>';
        });
      }
      html += '</div>';

      html += '<div class="panel-section"><div class="panel-section-title">🔗 关系边 (' + allConnectedEdges.length + ')</div>';
      if (allConnectedEdges.length === 0) {
        html += '<div class="empty-hint">无关系边</div>';
      } else {
        allConnectedEdges.forEach(eData => {
          const fromNode = nodesMap[eData.from];
          const toNode = nodesMap[eData.to];
          const fLabel = fromNode ? (fromNode.label || fromNode.title || eData.from) : eData.from;
          const tLabel = toNode ? (toNode.label || toNode.title || eData.to) : eData.to;
          html += '<div class="rel-item" data-edge="' + eData.id + '" style="cursor:pointer; margin-bottom:4px; font-size:12px;">';
          html += '<span>' + escapeHtml(String(fLabel)) + '</span>';
          html += '<span style="color:#aaa;margin:0 4px;">→</span>';
          html += '<span style="color:#2980b9;">' + escapeHtml(eData.label || eData.relationName || '关联') + '</span>';
          html += '<span style="color:#aaa;margin:0 4px;">→</span>';
          html += '<span>' + escapeHtml(String(tLabel)) + '</span>';
          html += '</div>';
        });
      }
      html += '</div>';

    } else {
      html += '<div class="empty-hint">当前节点无关联路径数据</div>';
    }
    
    this.tabNeighbors.innerHTML = html;
  }
  
  render(state) {
    if (!this.panel) return;
    
    if (this.tabNeighbors) this.tabNeighbors.removeAttribute('data-rendered');
    
    if (this.panelTabs) {
      this.panelTabs.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
      const firstTab = this.panelTabs.querySelector('.panel-tab');
      if (firstTab) firstTab.classList.add('active');
      
      const contents = this.panel.querySelectorAll('.panel-tab-content');
      contents.forEach(c => c.classList.remove('active'));
      if (this.tabInfo) this.tabInfo.classList.add('active');
    }
    
    if (state.isPanelOpen) {
      this.panel.classList.add('open');
      this.panel.style.setProperty('right', '0', 'important');
      
      if (state.selectedGraph === 'ontology' && state.selectedNodeId) {
        const data = ENTITY_DATA[state.selectedNodeId];
        const zh = ZH_LABELS[state.selectedNodeId] || state.selectedNodeId;
        this.title.textContent = `📋 ${state.selectedNodeId} — ${zh}`;
        
        if (data) {
          this.panelTabs.style.display = 'flex';
          this.tabInfo.innerHTML = `
            <div class="panel-section">
              <div class="panel-section-title">业务摘要</div>
              <div class="summary-highlight">${escapeHtml(data.description || '无描述')}</div>
            </div>
            <div class="panel-section">
              <div class="panel-section-title">结构属性</div>
              <div>包含 ${data.required?.length || 0} 个必填项和 ${data.optional?.length || 0} 个可选项。</div>
            </div>
          `;
        } else {
          this.panelTabs.style.display = 'none';
          this.tabInfo.innerHTML = `<div class="empty-hint">未找到实体数据: ${escapeHtml(state.selectedNodeId)}</div>`;
        }
      } else if (state.selectedGraph === 'ontology' && state.selectedEdgeId) {
        const edgeId = state.selectedEdgeId;
        const idx = parseInt(edgeId.split('_')[1], 10);
        const edgeData = !isNaN(idx) ? RELATION_EDGES[idx] : null;
        
        if (edgeData) {
          this.title.textContent = `🔗 关系边: ${escapeHtml(edgeData[0])}`;
          this.panelTabs.style.display = 'none';
          this.tabInfo.innerHTML = `
            <div class="panel-section">
              <div class="panel-section-title">关系方向</div>
              <div class="field-row">
                <span style="font-weight:500;">${escapeHtml(edgeData[1])}</span>
                <span style="color:#888;font-size:18px;margin:0 10px;">→</span>
                <span style="font-weight:500;">${escapeHtml(edgeData[2])}</span>
              </div>
            </div>
            <div class="panel-section">
              <div class="panel-section-title">关系名称</div>
              <div class="summary-highlight">${escapeHtml(edgeData[0])}</div>
            </div>
          `;
        } else {
          this.title.textContent = `🔗 关系边`;
          this.panelTabs.style.display = 'none';
          this.tabInfo.innerHTML = `<div class="empty-hint">无法识别关系类型</div>`;
        }
      } else if (state.selectedGraph === 'parse' && state.parseNodeData) {
        const node = state.parseNodeData;
        const label = node.label || node.id;
        const nodeType = node.nodeType || node.group || '未知类型';
        this.title.textContent = `📋 解析节点: ${escapeHtml(label)}`;
        this.panelTabs.style.display = 'flex';
        
        this.tabNeighbors.removeAttribute('data-rendered');
        const tabRaw = document.getElementById('panelTabRaw');
        if (tabRaw) tabRaw.removeAttribute('data-rendered');

        let extraFields = {
          '案号': node.case_number || node.caseNumber || '',
          '角色': node.role_name || node.roleName || '',
          '证据类型': node.evidence_type || node.evidenceType || '',
          '当事人类型': node.party_type || node.partyType || '',
          '身份': node.identity || '',
          '案由': node.case_type || node.caseType || '',
          '总得分': node.score !== undefined ? node.score : undefined,
        };
        const titleLines = parseNodeTitleLines(node.title || '');
        const extraEntries = Object.keys(extraFields).filter(k => extraFields[k] !== undefined && extraFields[k] !== null && String(extraFields[k]).trim() !== '');

        let html = '';

        html += this.buildSummaryCard(
          label,
          buildBusinessSummaryText([
            '解析类型：' + nodeType,
            extraFields['案号'] ? ('案号：' + extraFields['案号']) : '',
            titleLines.length ? ('已提取 ' + titleLines.length + ' 条结构化说明') : '等待进一步补充结构化说明'
          ]),
          [
            nodeType,
            node.group ? ('分组 ' + node.group) : '',
            extraFields['角色'] ? ('角色 ' + extraFields['角色']) : '',
            extraFields['证据类型'] ? ('证据 ' + extraFields['证据类型']) : ''
          ].filter(Boolean),
          this.buildSummaryMetric(extraEntries.length, '关键字段') +
          this.buildSummaryMetric(titleLines.length, '说明条目') +
          this.buildSummaryMetric(node.score !== undefined && node.score !== '' ? node.score : 'N/A', '抽取得分') +
          this.buildSummaryMetric(node.id, '节点 ID')
        );

        html += '<div class="panel-section">';
        html += '<div class="panel-section-title">业务摘要</div>';
        html += '<div class="summary-highlight"><strong>' + escapeHtml(label) + '</strong> 当前作为 <strong>' + escapeHtml(nodeType) + '</strong> 出现在解析图中。建议先核对关键字段，再通过“关联路径”查看它与其他实体的关系。</div>';
        html += '</div>';

        const kvItems = [
          { label: '节点名称', value: label },
          { label: '实体类型', value: nodeType },
          { label: '所属分组', value: node.group || '' },
          { label: '节点 ID', value: node.id }
        ].concat(extraEntries.map(k => ({ label: k, value: extraFields[k] })));

        html += this.buildKeyValueSection('关键字段', kvItems);

        if (nodeType === 'Evidence') {
          const admissionStatus = node.admission_status || '';
          const admissionReason = node.admission_reason || '';
          const probativeForce = node.probative_force || '';
          const isAccepted = admissionStatus === 'admitted';
          const isRejected = admissionStatus === 'not_admitted';
          const statusIcon = isAccepted ? '✅' : (isRejected ? '❌' : '❓');
          const statusColor = isAccepted ? '#27ae60' : (isRejected ? '#e74c3c' : '#f39c12');
          const statusLabel = isAccepted ? '已采信' : (isRejected ? '未采信' : '待确定');

          html += '<div style="margin:12px 0;padding:10px 12px;background:' + statusColor + '15;border:2px solid ' + statusColor + ';border-radius:8px;">';
          html += '<div style="display:flex;align-items:center;gap:10px;">';
          html += '<span style="font-size:28px;">' + statusIcon + '</span>';
          html += '<div><div style="font-weight:700;font-size:16px;color:' + statusColor + ';">' + escapeHtml(statusLabel) + '</div>';
          html += '<div style="font-size:11px;color:#888;">法院采信意见</div></div></div>';
          if (admissionReason) {
            html += '<div style="margin-top:6px;font-size:12px;color:#555;border-top:1px solid ' + statusColor + '30;padding-top:6px;">📝 ' + escapeHtml(admissionReason) + '</div>';
          }
          if (probativeForce) {
            const pfLabel = probativeForce === 'valid' ? '证明力有效' : '证明力无效';
            html += '<div style="margin-top:4px;"><span class="badge" style="background:' + (probativeForce === 'valid' ? '#e8f5e9' : '#fbe9e7') + ';color:' + (probativeForce === 'valid' ? '#2e7d32' : '#bf360c') + ';">' + pfLabel + '</span></div>';
          }
          html += '</div>';
        }

        if (titleLines.length) {
          html += this.buildKeyValueSection('抽取说明', titleLines.map((line, idx) => {
            let colonIdx = line.indexOf('：');
            if (colonIdx === -1) colonIdx = line.indexOf(':');
            if (colonIdx > 0 && colonIdx < line.length - 1) {
              return { label: line.substring(0, colonIdx).trim(), value: line.substring(colonIdx + 1).trim() };
            }
            return { label: '说明 ' + (idx + 1), value: line };
          }));
        }

        let titleStr = node.title || '';
        if (titleStr && titleStr.charAt(0) === '{') {
          try {
            const props = JSON.parse(titleStr);
            const propKeys = Object.keys(props);
            if (propKeys.length > 0) {
              html += this.buildKeyValueSection('结构化属性', propKeys.map(k => {
                let v = props[k];
                if (typeof v === 'object') v = JSON.stringify(v);
                return { label: k, value: String(v) };
              }));
            }
          } catch(e) {}
        }

        html += '<div class="panel-section">';
        html += '<div class="panel-section-title">图形样式</div>';
        html += '<div class="field-row"><span class="field-name">形状</span><span style="margin-left:8px;">' + escapeHtml(node.shape || 'ellipse') + '</span></div>';
        if (node.color && node.color.background) {
          html += '<div class="field-row" style="align-items:center;"><span class="field-name">颜色</span>';
          html += '<span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:' + node.color.background + ';border:1px solid ' + (node.color.border || '#ccc') + ';margin-left:8px;vertical-align:middle;"></span>';
          html += '<span style="margin-left:6px;font-family:monospace;font-size:11px;">' + node.color.background + '</span></div>';
        }
        html += '</div>';

        this.tabInfo.innerHTML = html;
        
        if (tabRaw) {
          tabRaw.innerHTML = `<pre style="font-size: 11px; padding: 10px; background: #f8fafc; overflow-x: auto;">${escapeHtml(JSON.stringify(node, null, 2))}</pre>`;
        }
      } else if (state.selectedGraph === 'parse' && state.selectedEdgeId && state.parseEdgeData) {
        const e = state.parseEdgeData;
        const fromNode = state.parseGraphData?.nodes?.find(n => n.id === e.from);
        const toNode = state.parseGraphData?.nodes?.find(n => n.id === e.to);
        const fromLabel = fromNode ? (fromNode.label || fromNode.id) : e.from;
        const toLabel = toNode ? (toNode.label || toNode.id) : e.to;
        const edgeLabel = e.label || e.relationName || '相关';

        this.title.textContent = `🔗 解析关系: ${escapeHtml(edgeLabel)}`;
        this.panelTabs.style.display = 'flex';
        
        const tabRaw = document.getElementById('panelTabRaw');
        if (tabRaw) tabRaw.removeAttribute('data-rendered');

        let html = '';
        html += this.buildSummaryCard(
          edgeLabel,
          `#${e.id || ''}`,
          [edgeLabel, '关系边'],
          this.buildSummaryMetric(fromLabel, '源节点') + this.buildSummaryMetric(toLabel, '目标节点')
        );

        html += `
          <div class="panel-section">
            <div class="panel-section-title">业务作用</div>
            <div class="summary-highlight">
              该关系展示解析结果中两个实体之间的连接，用于说明 <strong>${escapeHtml(fromLabel)}</strong> 与 <strong>${escapeHtml(toLabel)}</strong> 的语义联系。
            </div>
          </div>
          <div class="panel-section">
            <div class="panel-section-title">关系方向</div>
            <div class="field-row" style="font-size:14px;">
              <span style="font-weight:500;">${escapeHtml(fromLabel)}</span>
              <span style="color:#888;font-size:18px;margin:0 10px;">→</span>
              <span style="font-weight:500;">${escapeHtml(toLabel)}</span>
            </div>
            <div class="desc-text" style="font-size:12px;color:#888;margin-top:4px;">${escapeHtml(edgeLabel)}</div>
          </div>
          <div class="panel-section">
            <div class="panel-section-title">边信息</div>
            <div class="field-row">
              <span class="field-label">ID</span>
              <span class="field-value" style="font-family:monospace;font-size:11px;color:#666;">${escapeHtml(e.id)}</span>
            </div>
          </div>
        `;
        this.tabInfo.innerHTML = html;

        if (tabRaw) {
          tabRaw.innerHTML = `<pre style="font-size: 11px; padding: 10px; background: #f8fafc; overflow-x: auto;">${escapeHtml(JSON.stringify(e, null, 2))}</pre>`;
        }
      }
    } else {
      this.panel.classList.remove('open');
      this.panel.style.removeProperty('right');
    }
  }
}
