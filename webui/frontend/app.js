/**
 * 法律知识图谱 WebUI 前端逻辑
 * Cytoscape.js 渲染 + API 交互
 */

const COLORS = {
    norm:   '#3b82f6',
    subject:'#22c55e',
    entity: '#f59e0b',
    meta:   '#a855f7',
    edge:   '#64748b'
};

let cy = null;
let currentElements = [];

// ===== DOM Refs =====
const $ = id => document.getElementById(id);
const inputText   = $('inputText');
const parseBtn    = $('parseBtn');
const loadSampleBtn=$('loadSampleBtn');
const clearBtn    = $('clearBtn');
const statsSection= $('statsSection');
const statGrid    = $('statGrid');
const jsonSection = $('jsonSection');
const jsonPreview = $('jsonPreview');
const emptyState  = $('emptyState');
const searchNode  = $('searchNode');
const fitBtn      = $('fitBtn');
const layoutBtn   = $('layoutBtn');
const layoutSelect= $('layoutSelect');
const detailPanel = $('detailPanel');
const detailType  = $('detailType');
const detailBody  = $('detailBody');
const closeDetail = $('closeDetail');

// ===== Sample Data (示例：行政-不履行职责) =====
const SAMPLE_TEXT = `案件类型：行政-不履行XX职责
法院：最高人民法院
案号：（2025）最高法行第一号

基本事实：
申请人王某于2024年3月向某市人民政府申请公开某项行政许可的实施情况。该市政府于同年4月收到申请后，在法定期限内未作出任何书面回复。王某于2024年7月向法院提起行政诉讼，请求确认该市政府不履行法定职责。

裁判理由：
一、关于政府信息公开职责。根据《中华人民共和国政府信息公开条例》第二十七条规定，行政机关收到政府信息公开申请，能当场回复的，应当场回复；不能当场回复的，应当在收到申请之日起20个工作日内予以书面回复。本案中，市政府收到申请后未在法定期限内回复，已构成不履行法定职责。
二、关于判决方式。根据《中华人民共和国行政诉讼法》第七十六条，行政机关不履行或者无正当理由拖延履行法定职责的，人民法院判决确认其不履行。

裁判结果：确认某市人民政府对王某的政府信息公开申请未在法定期限内予以回复的行为违法，责令其在判决生效之日起20日内书面回复王某。
`;

// ===== Init =====
function initCytoscape(elements = []) {
    if (cy) { cy.destroy(); }
    currentElements = elements;

    if (elements.length === 0) {
        emptyState.classList.remove('hidden');
        return;
    }
    emptyState.classList.add('hidden');

    cy = cytoscape({
        container: document.getElementById('cy'),
        elements: elements,
        style: [
            {
                selector: 'node',
                style: {
                    'background-color': 'data(category)',
                    'label': 'data(label)',
                    'width': 36,
                    'height': 36,
                    'font-size': '11px',
                    'color': '#e2e8f0',
                    'text-outline-color': '#0f172a',
                    'text-outline-width': 2,
                    'text-valign': 'bottom',
                    'text-halign': 'center',
                    'text-margin-y': 4,
                    'border-width': 2,
                    'border-color': '#1e293b'
                }
            },
            {
                selector: 'node[norm]',
                style: { 'background-color': COLORS.norm }
            },
            {
                selector: 'node[subject]',
                style: { 'background-color': COLORS.subject }
            },
            {
                selector: 'node[entity]',
                style: { 'background-color': COLORS.entity }
            },
            {
                selector: 'edge',
                style: {
                    'width': 1.5,
                    'line-color': COLORS.edge,
                    'target-arrow-color': COLORS.edge,
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier',
                    'label': 'data(label)',
                    'font-size': '9px',
                    'color': '#94a3b8',
                    'text-outline-color': '#0f172a',
                    'text-outline-width': 2,
                    'arrow-scale': 0.8
                }
            },
            {
                selector: ':selected',
                style: {
                    'border-width': 3,
                    'border-color': '#ffffff',
                    'line-color': '#ffffff',
                    'target-arrow-color': '#ffffff'
                }
            }
        ],
        layout: { name: 'cose', padding: 20, animate: true, animationDuration: 500 }
    });

    // 节点点击
    cy.on('tap', 'node', evt => {
        const node = evt.target;
        showDetail(node.data());
    });

    // 背景点击关闭详情
    cy.on('tap', evt => {
        if (evt.target === cy) {
            hideDetail();
        }
    });

    runLayout('cose');
}

function runLayout(name) {
    if (!cy) return;
    const opts = { name, padding: 30, animate: true, animationDuration: 600 };
    if (name === 'cose') {
        Object.assign(opts, {
            componentSpacing: 80,
            nodeOverlap: 20,
            refresh: 20,
            fit: true,
            randomize: false
        });
    }
    cy.layout(opts).run();
}

// ===== Detail Panel =====
function showDetail(data) {
    detailType.textContent = data.entity_type || 'Unknown';
    detailType.style.background = COLORS[data.category] || COLORS.meta;
    detailType.style.color = '#fff';

    const skip = ['id', 'label', 'entity_type', 'category'];
    let html = '';
    for (const [k, v] of Object.entries(data)) {
        if (skip.includes(k)) continue;
        let display = v;
        if (Array.isArray(v)) display = v.join(', ');
        else if (typeof v === 'object') display = JSON.stringify(v);
        html += `<div class="detail-row"><span class="detail-key">${k}</span><span class="detail-val">${escapeHtml(String(display))}</span></div>`;
    }
    detailBody.innerHTML = html;
    detailPanel.classList.remove('hidden');
}

function hideDetail() {
    detailPanel.classList.add('hidden');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== Stats =====
function updateStats(elements) {
    const nodes = elements.filter(e => !e.data.source);
    const edges = elements.filter(e => e.data.source);
    const cats = {};
    nodes.forEach(n => {
        const c = n.data.category || 'unknown';
        cats[c] = (cats[c] || 0) + 1;
    });

    let html = '';
    html += `<div class="stat-card"><div class="num">${nodes.length}</div><div class="label">节点</div></div>`;
    html += `<div class="stat-card"><div class="num">${edges.length}</div><div class="label">关系</div></div>`;
    for (const [c, n] of Object.entries(cats)) {
        html += `<div class="stat-card"><div class="num" style="color:${COLORS[c]||'#fff'}">${n}</div><div class="label">${c}</div></div>`;
    }
    statGrid.innerHTML = html;
    statsSection.classList.remove('hidden');
}

// ===== API =====
async function parseAndRender() {
    const text = inputText.value.trim();
    if (!text) { alert('请输入案例文本'); return; }

    setLoading(true);
    try {
        const res = await fetch('/api/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, model: 'deepseek-v4-pro' })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '解析失败');
        }
        const data = await res.json();

        // 显示 JSON
        jsonPreview.textContent = JSON.stringify(data.raw_json, null, 2);
        jsonSection.classList.remove('hidden');

        // 渲染图谱
        const elements = data.cytoscape_elements.elements || [];
        initCytoscape(elements);
        updateStats(elements);
    } catch (e) {
        alert('解析失败: ' + e.message);
        console.error(e);
    } finally {
        setLoading(false);
    }
}

function setLoading(isLoading) {
    parseBtn.disabled = isLoading;
    parseBtn.querySelector('.btn-text').classList.toggle('hidden', isLoading);
    parseBtn.querySelector('.spinner').classList.toggle('hidden', !isLoading);
}

// ===== Search =====
function searchNodes(query) {
    if (!cy) return;
    cy.nodes().unselect();
    if (!query) return;
    const matches = cy.nodes().filter(n => {
        const label = (n.data('label') || '').toLowerCase();
        const type = (n.data('entity_type') || '').toLowerCase();
        return label.includes(query.toLowerCase()) || type.includes(query.toLowerCase());
    });
    if (matches.length > 0) {
        matches.select();
        cy.fit(matches, 60);
    }
}

// ===== Event Listeners =====
parseBtn.addEventListener('click', parseAndRender);
loadSampleBtn.addEventListener('click', () => {
    inputText.value = SAMPLE_TEXT;
});
clearBtn.addEventListener('click', () => {
    inputText.value = '';
    if (cy) { cy.destroy(); cy = null; }
    emptyState.classList.remove('hidden');
    statsSection.classList.add('hidden');
    jsonSection.classList.add('hidden');
    hideDetail();
});
fitBtn.addEventListener('click', () => { if (cy) cy.fit(cy.nodes(), 40); });
layoutBtn.addEventListener('click', () => { runLayout(layoutSelect.value); });
layoutSelect.addEventListener('change', () => { runLayout(layoutSelect.value); });
closeDetail.addEventListener('click', hideDetail);
searchNode.addEventListener('input', e => searchNodes(e.target.value));

// 初始化
console.log('法律知识图谱 WebUI 已加载');
