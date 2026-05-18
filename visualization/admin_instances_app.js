(function () {
  'use strict';

  var ALL_GRAPHS = window.ALL_GRAPHS || [];
  var RAW_DATA = window.RAW_DATA || {};
  var network = null;
  var nodesDataset = null;
  var edgesDataset = null;
  var currentFilter = 'all';
  var currentLayoutMode = 'force';
  var currentGraphViewMode = 'all';
  var currentBrowseMode = 'recent_latest';
  var currentDensityMode = 'standard';
  var currentVisibleEntries = [];
  var currentFilteredEntries = [];
  var currentSelection = null;
  var currentRenderedNodeMap = new Map();
  var currentRenderedEdgeMap = new Map();
  var rawDataOpen = true;
  var rawViewMode = 'snippet';
  var legendDragData = null;

  var detailPanel = document.getElementById('detailPanel');
  var panelTitle = document.getElementById('panelTitle');
  var panelBody = document.getElementById('panelBody');
  var panelClose = document.getElementById('panelClose');
  var relatedBtn = document.getElementById('btnRelatedOnly');
  var rawDataPanel = document.getElementById('rawDataPanel');
  var caseListPanel = document.getElementById('caseListPanel');
  var caseSelect = document.getElementById('caseSelect');
  var versionWrapper = document.getElementById('versionWrapper');
  var versionSelect = document.getElementById('versionSelect');
  var versionPrevBtn = document.getElementById('versionPrevBtn');
  var versionNextBtn = document.getElementById('versionNextBtn');
  var versionMetaEl = document.getElementById('versionMeta');
  var statsEl = document.getElementById('stats');
  var totalCasesEl = document.getElementById('totalCases');
  var filterCountEl = document.getElementById('filterCount');
  var filterSummaryEl = document.getElementById('filterSummary');
  var rawContentEl = document.getElementById('rawContent');
  var rawDataLabelEl = document.getElementById('rawDataLabel');
  var rawDataSubtitleEl = document.getElementById('rawDataSubtitle');
  var rawModeSnippetBtn = document.getElementById('rawModeSnippet');
  var rawModeFullBtn = document.getElementById('rawModeFull');
  var caseListScroll = document.getElementById('caseListScroll');
  var caseListSummaryEl = document.getElementById('caseListSummary');

  var filterState = {
    sources: new Set(),
    types: new Set(),
    years: new Set(),
    procedures: new Set(),
  };

  var graphMeta = new Map();
  var staticEntries = [];
  var entryMap = new Map();
  var savedCaseList = [];
  var savedCaseMetaMap = new Map();

  var TYPE_ORDER = ['行政', '民事', '刑事'];
  var PROCEDURE_ORDER = ['一审', '二审', '再审', '再审审查'];
  var CASE_CATEGORY_MAP = { civil: '民事', criminal: '刑事', administrative: '行政' };
  var CASE_SOURCE_LABELS = {
    static: '指导性案例',
    manual: '网页手动保存',
    extracted_candidate: '网页候选保存',
  };
  var ROOT_COLORS = {
    LegalNorm: { bg: '#2980b9', border: '#1a5276' },
    JudicialEntity: { bg: '#d35400', border: '#a04000' },
    LegalSubject: { bg: '#27ae60', border: '#1e8449' },
    Person: { bg: '#16a085', border: '#0e6655' },
  };
  var ADMIN_TYPE_ROOT = {
    GuidingCase: 'LegalNorm',
    LegalProvision: 'LegalNorm',
    LegalProvisionElement: 'LegalNorm',
    CaseType: 'JudicialEntity',
    CourtCase: 'JudicialEntity',
    CaseSummary: 'JudicialEntity',
    Evidence: 'JudicialEntity',
    JudgmentResult: 'JudicialEntity',
    Fact: 'JudicialEntity',
    DisputeFocus: 'JudicialEntity',
    LegalSubject: 'LegalSubject',
    Judge: 'Person',
    Attorney: 'Person',
  };
  var ADMIN_SHAPES = {
    GuidingCase: 'hexagon',
    CourtCase: 'box',
    CaseType: 'diamond',
    LegalProvision: 'hexagon',
    LegalProvisionElement: 'square',
    LegalSubject: 'ellipse',
    Evidence: 'database',
    Judge: 'ellipse',
    Attorney: 'ellipse',
    JudgmentResult: 'box',
    CaseSummary: 'box',
    Fact: 'ellipse',
    DisputeFocus: 'star',
  };
  var REL_LABEL_MAP = {
    based_on: '依据',
    proves_fact: '证明',
    resolved_by: '裁判',
    has_fact: '事实',
    has_dispute_focus: '焦点',
    submitted_for: '提交',
    cites: '引用',
  };

  function safeParseJSON(value) {
    if (!value) return null;
    try { return typeof value === 'string' ? JSON.parse(value) : value; } catch (err) { return null; }
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function stripHtml(value) {
    return String(value == null ? '' : value).replace(/<[^>]+>/g, '').trim();
  }

  function shortText(value, maxLen) {
    var text = String(value == null ? '' : value).trim();
    return !maxLen || text.length <= maxLen ? text : text.slice(0, maxLen - 1) + '…';
  }

  function toCaseCategoryLabel(value) {
    return CASE_CATEGORY_MAP[value] || value || '';
  }

  function makeSavedCaseKey(info) {
    return 'saved:' + (info.source || 'manual') + ':' + info.row_id;
  }

  function isSavedCaseKey(value) {
    return typeof value === 'string' && value.indexOf('saved:') === 0;
  }

  function parseSavedCaseKey(value) {
    var parts = String(value || '').split(':');
    return { source: parts[1] || 'manual', rowId: parts.slice(2).join(':') };
  }

  function makeGraphPrefix(key) {
    return 'g_' + String(key).replace(/[^a-zA-Z0-9_]/g, '_') + '_';
  }

  function getAdminColor(typeName) {
    return ROOT_COLORS[ADMIN_TYPE_ROOT[typeName]] || { bg: '#7f8c8d', border: '#5d6d7e' };
  }

  function lightenColor(hex, percent) {
    var num = parseInt(hex.slice(1), 16);
    var amt = Math.round(2.55 * percent);
    var r = Math.min(255, (num >> 16) + amt);
    var g = Math.min(255, ((num >> 8) & 255) + amt);
    var b = Math.min(255, (num & 255) + amt);
    return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
  }

  function sortFilterValues(values, dimension) {
    var arr = (values || []).slice();
    if (dimension === 'types') {
      arr.sort(function (a, b) {
        var ai = TYPE_ORDER.indexOf(a);
        var bi = TYPE_ORDER.indexOf(b);
        if (ai !== -1 && bi !== -1) return ai - bi;
        if (ai !== -1) return -1;
        if (bi !== -1) return 1;
        return a.localeCompare(b, 'zh-CN');
      });
    } else if (dimension === 'procedures') {
      arr.sort(function (a, b) {
        var ai = PROCEDURE_ORDER.indexOf(a);
        var bi = PROCEDURE_ORDER.indexOf(b);
        if (ai === -1 && bi === -1) return a.localeCompare(b, 'zh-CN');
        if (ai === -1) return 1;
        if (bi === -1) return -1;
        return ai - bi;
      });
    } else if (dimension === 'years') {
      arr.sort(function (a, b) { return parseInt(b, 10) - parseInt(a, 10); });
    } else {
      arr.sort(function (a, b) { return a.localeCompare(b, 'zh-CN'); });
    }
    return arr;
  }

  function nodeTitle(parts) {
    return parts.filter(Boolean).join('<br>');
  }

  function sourceClassName(source) {
    return 'source-' + String(source || 'static').replace(/[^a-zA-Z0-9_-]/g, '_');
  }

  function countNonEmpty(list) {
    return (list || []).filter(function (item) { return !!item; }).length;
  }

  function getEntryGraphStats(entry) {
    var output = entry.output || {};
    var facts = countNonEmpty(output.facts);
    var focuses = countNonEmpty(output.dispute_focuses);
    var relations = countNonEmpty(output.relations);
    var evidence = countNonEmpty(output.evidence);
    var provisions = countNonEmpty(output.legal_provisions);
    return {
      facts: facts,
      focuses: focuses,
      relations: relations,
      evidence: evidence,
      provisions: provisions,
      nodes: (entry.nodes || []).length,
      edges: (entry.edges || []).length,
      graphReady: facts > 0 || focuses > 0 || relations > 0,
    };
  }

  function summarizeEntry(entry) {
    var meta = graphMeta.get(entry.key) || entry.meta || {};
    var stats = getEntryGraphStats(entry);
    return {
      sourceLabel: CASE_SOURCE_LABELS[entry.source] || entry.source || '未知来源',
      years: (meta.years || []).length ? meta.years.join(' / ') : '年份未标注',
      procedures: (meta.procedures || []).length ? meta.procedures.join(' / ') : '程序未标注',
      types: (meta.types || []).length ? meta.types.join(' / ') : (entry.case_type || '类型未标注'),
      stats: stats,
    };
  }

  function renderSourceTag(source) {
    var label = CASE_SOURCE_LABELS[source] || source || '未知来源';
    return '<span class="case-tag ' + sourceClassName(source) + '">' + escapeHtml(label) + '</span>';
  }

  function renderStructureTags(stats) {
    var tags = [];
    if (stats.facts) tags.push('<span class="case-tag graph-tag">facts ' + stats.facts + '</span>');
    if (stats.focuses) tags.push('<span class="case-tag graph-tag">focuses ' + stats.focuses + '</span>');
    if (stats.relations) tags.push('<span class="case-tag graph-tag">relations ' + stats.relations + '</span>');
    return tags.join('');
  }

  function buildFilterSummaryHtml() {
    var groups = [
      { label: '来源', values: Array.from(filterState.sources) },
      { label: '类型', values: Array.from(filterState.types) },
      { label: '年份', values: Array.from(filterState.years) },
      { label: '流程', values: Array.from(filterState.procedures) }
    ];
    var active = groups.filter(function (group) { return group.values.length > 0; });
    if (!active.length) {
      return '<span class="filter-summary-label">当前筛选</span><span class="filter-summary-empty">未设置额外筛选，默认展示当前结果集。</span>';
    }
    return '<span class="filter-summary-label">当前筛选</span>' + active.map(function (group) {
      return '<span class="filter-summary-chip"><strong>' + escapeHtml(group.label) + '</strong><span>' + escapeHtml(group.values.join(' / ')) + '</span></span>';
    }).join('');
  }

  function getBrowseModeLabel() {
    if (currentBrowseMode === 'latest_only') return '全部最新版本';
    if (currentBrowseMode === 'all_versions') return '全部版本';
    return '最近 5 个最新版本';
  }

  function getDensityModeLabel() {
    if (currentDensityMode === 'overview') return '概览';
    if (currentDensityMode === 'detail') return '细节';
    return '标准';
  }

  function getLatestEntries(entries) {
    var latestByRow = new Map();
    (entries || []).forEach(function (entry) {
      var existing = latestByRow.get(entry.row_id);
      if (!existing || (entry.version || 1) > (existing.version || 1)) latestByRow.set(entry.row_id, entry);
    });
    return Array.from(latestByRow.values());
  }

  function applyBrowseMode(entries) {
    if (currentBrowseMode === 'all_versions') return (entries || []).slice();
    var latestEntries = getLatestEntries(entries);
    if (currentBrowseMode === 'latest_only') return latestEntries;
    return getTopEntriesByYear(5, latestEntries);
  }

  function getNodeRelatedItems(nodeId) {
    var items = [];
    if (!edgesDataset) return items;
    edgesDataset.forEach(function (edge) {
      if (edge.from !== nodeId && edge.to !== nodeId) return;
      var isOutgoing = edge.from === nodeId;
      var otherId = isOutgoing ? edge.to : edge.from;
      var otherNode = currentRenderedNodeMap.get(otherId);
      items.push({
        direction: isOutgoing ? 'out' : 'in',
        relation: edge.label || edge.relationType || '关联',
        targetLabel: otherNode ? (otherNode.fullLabel || otherNode.label || otherId) : otherId,
        targetType: otherNode ? otherNode.nodeType : 'Unknown',
      });
    });
    return items;
  }

  function buildStructuredGraphFromOutput(output, ctx) {
    output = output || {};
    var nodes = [];
    var edges = [];
    var nodeIds = new Set();
    var edgeKeys = new Set();
    var localToGlobal = new Map();
    var caseNumberToNode = new Map();
    var prefix = makeGraphPrefix(ctx.key);
    var firstCourtLocalId = '';

    function globalId(localId) {
      return prefix + String(localId).replace(/[^a-zA-Z0-9_:-]/g, '_');
    }

    function addNode(localId, label, nodeType, level, title, extra) {
      var id = globalId(localId);
      if (nodeIds.has(id)) return id;
      nodeIds.add(id);
      localToGlobal.set(String(localId), id);
      nodes.push(Object.assign({
        id: id,
        label: shortText(label || nodeType || id, 48),
        fullLabel: label || '',
        title: title || '',
        level: level || 1,
        nodeType: nodeType || 'Unknown',
        caseKey: ctx.key,
        rowId: ctx.rowId,
        caseName: ctx.caseName,
        source: ctx.source,
      }, extra || {}));
      return id;
    }

    function resolveRef(ref) {
      if (ref == null || ref === '') return '';
      var key = String(ref);
      if (localToGlobal.has(key)) return localToGlobal.get(key);
      if (caseNumberToNode.has(key)) return caseNumberToNode.get(key);
      var fallback = globalId(key);
      return nodeIds.has(fallback) ? fallback : '';
    }

    function addEdge(fromRef, toRef, label, extra) {
      var fromId = resolveRef(fromRef);
      var toId = resolveRef(toRef);
      if (!fromId || !toId) return;
      var edgeKey = fromId + '|' + toId + '|' + (label || '');
      if (edgeKeys.has(edgeKey)) return;
      edgeKeys.add(edgeKey);
      edges.push(Object.assign({
        id: prefix + 'edge_' + edgeKeys.size,
        from: fromId,
        to: toId,
        label: label || '',
        relationType: (extra && extra.relationType) || label || '',
        caseKey: ctx.key,
        rowId: ctx.rowId,
        caseName: ctx.caseName,
        source: ctx.source,
      }, extra || {}));
    }

    (output.court_cases || []).forEach(function (cc, index) {
      cc = cc || {};
      var localId = 'cc_' + index;
      if (!firstCourtLocalId) firstCourtLocalId = localId;
      var caseNumber = cc.case_number || ('case_' + index);
      var ccId = addNode(localId, caseNumber, 'CourtCase', 0, nodeTitle([
        '<b>法院案件</b>',
        '案号: ' + escapeHtml(caseNumber),
        cc.court && cc.court.name ? '法院: ' + escapeHtml(cc.court.name) : '',
        cc.trial_level ? '审级: ' + escapeHtml(cc.trial_level) : '',
        cc.trial_procedure ? '程序: ' + escapeHtml(cc.trial_procedure) : '',
        cc.judgment_date ? '裁判日期: ' + escapeHtml(cc.judgment_date) : '',
      ]), { courtCaseNumber: caseNumber });
      caseNumberToNode.set(caseNumber, ccId);
    });

    var gc = output.guiding_case || {};
    if (gc.guiding_case_name) {
      addNode('gc', gc.guiding_case_name, 'GuidingCase', 0, nodeTitle([
        '<b>指导/典型案例</b>',
        gc.storage_no ? '入库编号: ' + escapeHtml(gc.storage_no) : '',
        gc.binding_force ? '效力: ' + escapeHtml(gc.binding_force) : '',
        gc.case_level ? '层级: ' + escapeHtml(gc.case_level) : '',
        gc.publication_date ? '发布日期: ' + escapeHtml(gc.publication_date) : '',
        gc.guiding_points ? '裁判要旨: ' + escapeHtml(shortText(gc.guiding_points, 180)) : '',
      ]));
      if (firstCourtLocalId) addEdge(firstCourtLocalId, 'gc', '关联');
    }

    var ct = output.case_type || {};
    if (ct.category || ct.level1 || ct.level2) {
      addNode('ct', ct.level2 || ct.level1 || toCaseCategoryLabel(ct.category) || '案件类型', 'CaseType', 0, nodeTitle([
        '<b>案件类型</b>',
        ct.category ? '类别: ' + escapeHtml(toCaseCategoryLabel(ct.category) || ct.category) : '',
        ct.level1 ? '一级: ' + escapeHtml(ct.level1) : '',
        ct.level2 ? '二级: ' + escapeHtml(ct.level2) : '',
      ]));
      if (ct.level1) addNode('ct_level1', ct.level1, 'CaseType', 1, '<b>一级案由</b><br>' + escapeHtml(ct.level1));
      if (ct.level2) addNode('ct_level2', ct.level2, 'CaseType', 1, '<b>二级案由</b><br>' + escapeHtml(ct.level2));
      if (ct.level1) addEdge('ct', 'ct_level1', '一级案由');
      if (ct.level2) addEdge('ct', 'ct_level2', '二级案由');
      (output.court_cases || []).forEach(function (_, index) { addEdge('ct', 'cc_' + index, '案由'); });
    }

    var subjects = output.legal_subjects || output.parties || [];
    subjects.forEach(function (subj, index) {
      subj = subj || {};
      addNode('subj_' + index, subj.name || ('当事人_' + index), 'LegalSubject', 0, nodeTitle([
        '<b>诉讼主体</b>',
        subj.name ? '名称: ' + escapeHtml(subj.name) : '',
        subj.subject_type ? '类型: ' + escapeHtml(subj.subject_type) : '',
        subj.org_type ? '组织性质: ' + escapeHtml(subj.org_type) : '',
      ]));
    });
    subjects.forEach(function (subj, index) {
      subj = subj || {};
      var roles = subj.roles || [];
      if (!roles.length) {
        if (firstCourtLocalId) addEdge(firstCourtLocalId, 'subj_' + index, '当事人');
        return;
      }
      roles.forEach(function (role) {
        role = role || {};
        addEdge(role.case_number || firstCourtLocalId, 'subj_' + index, role.role_name || '当事人');
      });
    });

    (output.judges || []).forEach(function (judge, index) {
      judge = judge || {};
      addNode('judge_' + index, judge.name || ('法官_' + index), 'Judge', 1, nodeTitle([
        '<b>法官</b>',
        judge.name ? '姓名: ' + escapeHtml(judge.name) : '',
        judge.case_number ? '案号: ' + escapeHtml(judge.case_number) : '',
      ]));
      addEdge(judge.case_number || firstCourtLocalId, 'judge_' + index, '审判');
    });

    (output.attorneys || []).forEach(function (atty, index) {
      atty = atty || {};
      addNode('atty_' + index, atty.name || ('律师_' + index), 'Attorney', 1, nodeTitle([
        '<b>律师</b>',
        atty.name ? '姓名: ' + escapeHtml(atty.name) : '',
        atty.case_number ? '案号: ' + escapeHtml(atty.case_number) : '',
      ]));
      addEdge(atty.case_number || firstCourtLocalId, 'atty_' + index, '代理');
    });

    (output.legal_provisions || []).forEach(function (prov, index) {
      prov = prov || {};
      var provLocal = 'prov_' + index;
      var provLabel = (prov.statute || '法规') + (prov.article ? ('第' + prov.article + '条') : '');
      addNode(provLocal, provLabel || ('法条_' + index), 'LegalProvision', 1, nodeTitle([
        '<b>法律条文</b>',
        prov.statute ? '法规: ' + escapeHtml(prov.statute) : '',
        prov.article ? '条号: ' + escapeHtml(prov.article) : '',
        prov.citation_purpose ? '目的: ' + escapeHtml(prov.citation_purpose) : '',
        prov.content ? '内容: ' + escapeHtml(shortText(prov.content, 180)) : '',
      ]));
      addEdge(prov.case_number || firstCourtLocalId, provLocal, '引用');
    });

    (output.evidence || []).forEach(function (evid, index) {
      evid = evid || {};
      var evidLocal = evid.id || ('evid_' + index);
      addNode(evidLocal, evid.content || ('证据_' + index), 'Evidence', 1, nodeTitle([
        '<b>证据</b>',
        evid.evidence_type ? '类型: ' + escapeHtml(evid.evidence_type) : '',
        evid.submitted_by ? '提交方: ' + escapeHtml(evid.submitted_by) : '',
        evid.admission_status ? '采信: ' + escapeHtml(evid.admission_status) : '',
        evid.probative_force ? '证明力: ' + escapeHtml(evid.probative_force) : '',
        evid.content ? '内容: ' + escapeHtml(shortText(evid.content, 180)) : '',
      ]));
      addEdge(evid.case_number || firstCourtLocalId, evidLocal, '证据');
    });

    (output.judgment_results || []).forEach(function (jr, index) {
      jr = jr || {};
      var jrLocal = jr.id || ('jr_' + index);
      addNode(jrLocal, jr.result_type || ('裁判结果_' + index), 'JudgmentResult', 0, nodeTitle([
        '<b>裁判结果</b>',
        jr.result_type ? '结果类型: ' + escapeHtml(jr.result_type) : '',
        jr.specific_judgment ? '具体裁判: ' + escapeHtml(shortText(jr.specific_judgment, 180)) : '',
        jr.reasoning ? '理由: ' + escapeHtml(shortText(jr.reasoning, 180)) : '',
      ]));
      addEdge(jr.case_number || firstCourtLocalId, jrLocal, '裁判');
    });

    (output.facts || []).forEach(function (fact, index) {
      fact = fact || {};
      var factLocal = fact.id || ('fact_' + index);
      addNode(factLocal, fact.content || ('事实_' + index), 'Fact', 1, nodeTitle([
        '<b>案件事实</b>',
        fact.fact_type ? '类型: ' + escapeHtml(fact.fact_type) : '',
        fact.case_number ? '案号: ' + escapeHtml(fact.case_number) : '',
        fact.content ? '内容: ' + escapeHtml(shortText(fact.content, 180)) : '',
      ]));
      addEdge(fact.case_number || firstCourtLocalId, factLocal, '事实');
    });

    (output.dispute_focuses || []).forEach(function (focus, index) {
      focus = focus || {};
      var focusLocal = focus.id || ('focus_' + index);
      addNode(focusLocal, focus.content || ('争议焦点_' + index), 'DisputeFocus', 0, nodeTitle([
        '<b>争议焦点</b>',
        focus.focus_type ? '类型: ' + escapeHtml(focus.focus_type) : '',
        focus.case_number ? '案号: ' + escapeHtml(focus.case_number) : '',
        focus.content ? '内容: ' + escapeHtml(shortText(focus.content, 180)) : '',
      ]));
      addEdge(focus.case_number || firstCourtLocalId, focusLocal, '争议焦点');
    });

    var summary = output.case_summary || {};
    if (summary.disputed_issues) {
      var issuesText = Array.isArray(summary.disputed_issues) ? summary.disputed_issues.join('；') : String(summary.disputed_issues);
      addNode('summary', issuesText, 'CaseSummary', 1, nodeTitle([
        '<b>案件摘要</b>',
        summary.key_facts ? '关键事实: ' + escapeHtml(shortText(summary.key_facts, 120)) : '',
        issuesText ? '争议问题: ' + escapeHtml(shortText(issuesText, 180)) : '',
        summary.conclusion ? '结论: ' + escapeHtml(shortText(summary.conclusion, 120)) : '',
      ]));
      addEdge(firstCourtLocalId, 'summary', '审理');
    }

    (output.relations || []).forEach(function (rel) {
      rel = rel || {};
      if (!rel.source_id || !rel.target_id) return;
      var label = rel.label || REL_LABEL_MAP[rel.relation_type] || rel.relation_type || '关联';
      addEdge(rel.source_id, rel.target_id, label, { relationType: rel.relation_type || label });
    });

    return { nodes: nodes, edges: edges };
  }

  function createEntryFromRecord(record, meta) {
    record = record || {};
    meta = meta || {};
    var output = record.output || record.json_result || {};
    var caseType = output.case_type || {};
    var caseName = meta.caseName || record.case_name || (output.guiding_case && output.guiding_case.guiding_case_name) || '未命名案例';
    var entry = {
      key: meta.key,
      row_id: String(meta.rowId || record.row_id || ''),
      case_name: caseName,
      case_type: caseType.level2 || caseType.level1 || toCaseCategoryLabel(caseType.category) || meta.caseType || '',
      version: meta.version || 1,
      source: meta.source || record.source || 'static',
      output: output,
      rawRecord: record,
      nodes: [],
      edges: [],
    };
    var graph = buildStructuredGraphFromOutput(output, {
      key: entry.key,
      rowId: entry.row_id,
      caseName: entry.case_name,
      source: entry.source,
    });
    entry.nodes = graph.nodes;
    entry.edges = graph.edges;
    return entry;
  }

  function extractEntryMeta(entry) {
    var output = entry.output || {};
    var input = entry.rawRecord && entry.rawRecord.input ? entry.rawRecord.input : {};
    var caseType = output.case_type || {};
    var years = new Set();
    var procedures = new Set();
    var types = new Set();
    (output.court_cases || []).forEach(function (cc) {
      cc = cc || {};
      var match = String(cc.judgment_date || cc.filing_date || '').match(/(\d{4})/);
      if (match) years.add(match[1]);
      if (cc.trial_procedure) procedures.add(cc.trial_procedure);
    });
    if (caseType.level1) types.add(caseType.level1);
    if (caseType.level2) types.add(caseType.level2);
    if (caseType.category) types.add(toCaseCategoryLabel(caseType.category));
    return {
      source: input.web_name || CASE_SOURCE_LABELS[entry.source] || '指导性案例',
      types: Array.from(types),
      years: Array.from(years),
      procedures: Array.from(procedures),
    };
  }

  function hydrateStaticEntries() {
    ALL_GRAPHS.forEach(function (summary) {
      var key = summary.version ? (summary.row_id + '__v' + summary.version) : summary.row_id;
      var raw = RAW_DATA[key] || RAW_DATA[summary.row_id] || '';
      var parsed = safeParseJSON(raw) || {};
      parsed.row_id = parsed.row_id || summary.row_id;
      var entry = createEntryFromRecord(parsed, {
        key: key,
        rowId: summary.row_id,
        caseName: summary.case_name,
        caseType: summary.case_type,
        version: summary.version || 1,
        source: 'static',
      });
      entry.meta = extractEntryMeta(entry);
      staticEntries.push(entry);
      entryMap.set(entry.key, entry);
      graphMeta.set(entry.key, entry.meta);
    });
  }

  function renderFilterTags(containerId, values, activeSet, onChange) {
    var container = document.getElementById(containerId);
    container.innerHTML = '';
    values.forEach(function (value) {
      var tag = document.createElement('span');
      tag.className = 'filter-tag' + (activeSet.has(value) ? ' active' : '');
      tag.textContent = value;
      tag.addEventListener('click', function () {
        if (activeSet.has(value)) {
          activeSet.delete(value);
          tag.classList.remove('active');
        } else {
          activeSet.add(value);
          tag.classList.add('active');
        }
        onChange();
      });
      container.appendChild(tag);
    });
  }

  function buildFilterOptions() {
    var sources = new Set();
    var types = new Set();
    var years = new Set();
    var procedures = new Set();
    graphMeta.forEach(function (meta) {
      if (meta.source) sources.add(meta.source);
      (meta.types || []).forEach(function (v) { if (v) types.add(v); });
      (meta.years || []).forEach(function (v) { if (v) years.add(v); });
      (meta.procedures || []).forEach(function (v) { if (v) procedures.add(v); });
    });
    renderFilterTags('sourceFilter', sortFilterValues(Array.from(sources), 'sources'), filterState.sources, onFilterChange);
    renderFilterTags('typeFilter', sortFilterValues(Array.from(types), 'types'), filterState.types, onFilterChange);
    renderFilterTags('yearFilter', sortFilterValues(Array.from(years), 'years'), filterState.years, onFilterChange);
    renderFilterTags('procedureFilter', sortFilterValues(Array.from(procedures), 'procedures'), filterState.procedures, onFilterChange);
    document.getElementById('resetFilters').addEventListener('click', function () {
      filterState.sources.clear();
      filterState.types.clear();
      filterState.years.clear();
      filterState.procedures.clear();
      document.querySelectorAll('.filter-tag.active').forEach(function (el) { el.classList.remove('active'); });
      onFilterChange();
    });
  }

  function applyFilters() {
    return staticEntries.filter(function (entry) {
      var meta = graphMeta.get(entry.key);
      if (!meta) return true;
      if (filterState.sources.size && !filterState.sources.has(meta.source)) return false;
      if (filterState.types.size && !(meta.types || []).some(function (v) { return filterState.types.has(v); })) return false;
      if (filterState.years.size && !(meta.years || []).some(function (v) { return filterState.years.has(v); })) return false;
      if (filterState.procedures.size && !(meta.procedures || []).some(function (v) { return filterState.procedures.has(v); })) return false;
      return true;
    });
  }

  function buildOptionLabel(entry) {
    var prefix = entry.source === 'static' ? '' : (entry.source === 'manual' ? '📝 ' : '🧪 ');
    var suffix = entry.version && entry.version > 1 ? ' (v' + entry.version + ')' : '';
    return prefix + '[' + entry.row_id + '] ' + entry.case_name + suffix;
  }

  function rebuildCaseSelect(visibleEntries) {
    var prev = currentFilter;
    caseSelect.innerHTML = '';
    var allOpt = document.createElement('option');
    allOpt.value = 'all';
    allOpt.textContent = '📌 全部案例（' + visibleEntries.length + '个匹配）';
    caseSelect.appendChild(allOpt);
    visibleEntries.slice().sort(function (a, b) {
      var ar = parseInt(a.row_id, 10);
      var br = parseInt(b.row_id, 10);
      if (ar !== br) return ar - br;
      return (b.version || 1) - (a.version || 1);
    }).forEach(function (entry) {
      var opt = document.createElement('option');
      opt.value = entry.key;
      opt.textContent = buildOptionLabel(entry);
      caseSelect.appendChild(opt);
    });
    savedCaseList.forEach(function (info) {
      var opt = document.createElement('option');
      opt.value = info.key;
      opt.textContent = buildOptionLabel(info);
      opt.setAttribute('data-source', info.source);
      caseSelect.appendChild(opt);
    });
    if (prev && prev !== 'all' && !isSavedCaseKey(prev) && !caseSelect.querySelector('option[value="' + CSS.escape(prev) + '"]')) {
      var selectedEntry = entryMap.get(prev);
      if (selectedEntry) {
        var selectedOpt = document.createElement('option');
        selectedOpt.value = selectedEntry.key;
        selectedOpt.textContent = buildOptionLabel(selectedEntry) + ' · 当前选中';
        caseSelect.appendChild(selectedOpt);
      }
    }
    if (prev && caseSelect.querySelector('option[value="' + CSS.escape(prev) + '"]')) caseSelect.value = prev;
    else caseSelect.value = 'all';
  }

  function rebuildCaseList(visibleEntries) {
    caseListSummaryEl.innerHTML =
      '<strong>' + visibleEntries.length + '</strong> 个静态案例正在展示，模式为 <strong>' + escapeHtml(getBrowseModeLabel()) + '</strong>' +
      (savedCaseList.length ? '，另有 <strong>' + savedCaseList.length + '</strong> 个网页保存案例可浏览。' : '。');
    var html = '<div class="case-list-item" data-case-key="all" onclick="selectFromList(\'all\')"><div class="case-item-top"><div class="case-name">📌 全部案例</div><div class="case-tags"><span class="case-tag">当前结果集</span></div></div><div class="case-meta">显示所有匹配案例，适合先看整体分布再逐案进入。</div></div>';
    visibleEntries.forEach(function (entry) {
      var summary = summarizeEntry(entry);
      html += '<div class="case-list-item" data-case-key="' + escapeHtml(entry.key) + '" onclick="selectFromList(\'' + escapeHtml(entry.key) + '\')">' +
        '<div class="case-item-top"><div class="case-name">' + escapeHtml(entry.case_name) + '</div>' +
        '<div class="case-tags">' + renderSourceTag(entry.source) +
        (entry.version > 1 ? '<span class="case-tag version-tag">v' + entry.version + '</span>' : '') +
        renderStructureTags(summary.stats) + '</div></div>' +
        '<div class="case-meta">#' + escapeHtml(entry.row_id) + ' · ' + escapeHtml(summary.types) + '<br>' +
        escapeHtml(summary.years) + ' · ' + escapeHtml(summary.procedures) + '</div>' +
        '<div class="case-metrics">' +
        '<span class="case-metric"><strong>' + summary.stats.nodes + '</strong><span>节点</span></span>' +
        '<span class="case-metric"><strong>' + summary.stats.edges + '</strong><span>关系</span></span>' +
        '<span class="case-metric"><strong>' + summary.stats.evidence + '</strong><span>证据</span></span>' +
        '<span class="case-metric"><strong>' + summary.stats.provisions + '</strong><span>法条</span></span>' +
        '</div></div>';
    });
    savedCaseList.forEach(function (info) {
      html += '<div class="case-list-item" data-case-key="' + escapeHtml(info.key) + '" onclick="selectFromList(\'' + escapeHtml(info.key) + '\')">' +
        '<div class="case-item-top"><div class="case-name">' + escapeHtml((info.source === 'manual' ? '📝 ' : '🧪 ') + info.case_name) + '</div>' +
        '<div class="case-tags">' + renderSourceTag(info.source) + '</div></div>' +
        '<div class="case-meta">#' + escapeHtml(info.row_id) + ' · 网页保存案例，点击后按需加载结构化图谱。</div></div>';
    });
    caseListScroll.innerHTML = html;
  }

  function updateSubtitle(totalCount, filteredCount) {
    var subtitle = document.querySelector('.header .subtitle');
    var suffix = ' · ' + getBrowseModeLabel() + ' · ' + getDensityModeLabel() + '阅读模式';
    subtitle.textContent = filteredCount === totalCount
      ? ('共 ' + totalCount + ' 个案例 · 展示真实结构化图谱' + suffix)
      : ('共 ' + totalCount + ' 个案例 · 当前匹配 ' + filteredCount + ' 个 · 展示真实结构化图谱' + suffix);
  }

  function getTopEntriesByYear(n, pool) {
    var scored = [];
    var seen = new Set();
    (pool || staticEntries).forEach(function (entry) {
      if (seen.has(entry.row_id)) return;
      seen.add(entry.row_id);
      var meta = graphMeta.get(entry.key) || entry.meta || {};
      var years = (meta.years || []).map(function (v) { return parseInt(v, 10); }).filter(Boolean);
      scored.push({ entry: entry, year: years.length ? Math.max.apply(null, years) : 0 });
    });
    scored.sort(function (a, b) { return b.year - a.year; });
    return scored.slice(0, n).map(function (item) { return item.entry; });
  }

  function normalizeSelectionValue(value, visibleEntries) {
    if (!value || value === 'all' || isSavedCaseKey(value)) return value || 'all';
    var exact = visibleEntries.find(function (entry) { return entry.key === value; });
    if (exact) return exact.key;
    var sameRow = visibleEntries.filter(function (entry) { return entry.row_id === value; });
    if (!sameRow.length) return value;
    sameRow.sort(function (a, b) { return (b.version || 1) - (a.version || 1); });
    return sameRow[0].key;
  }

  function getVersionEntriesForSelection(selectionValue) {
    if (!selectionValue || selectionValue === 'all' || isSavedCaseKey(selectionValue)) return [];
    var entry = entryMap.get(selectionValue);
    if (!entry) return [];
    return currentFilteredEntries.filter(function (item) { return item.row_id === entry.row_id; }).sort(function (a, b) { return (a.version || 1) - (b.version || 1); });
  }

  function updateVersionControl(selectionValue) {
    versionWrapper.style.display = 'none';
    versionSelect.innerHTML = '';
    if (versionMetaEl) versionMetaEl.textContent = '';
    if (versionPrevBtn) versionPrevBtn.disabled = true;
    if (versionNextBtn) versionNextBtn.disabled = true;
    if (!selectionValue || selectionValue === 'all' || isSavedCaseKey(selectionValue)) return;
    var entry = entryMap.get(selectionValue);
    if (!entry) return;
    var versions = getVersionEntriesForSelection(selectionValue);
    if (versions.length <= 1) return;
    versionWrapper.style.display = 'inline-flex';
    versions.forEach(function (item) {
      var opt = document.createElement('option');
      opt.value = item.key;
      opt.textContent = 'v' + (item.version || 1);
      if (item.key === selectionValue) opt.selected = true;
      versionSelect.appendChild(opt);
    });
    var currentIndex = versions.findIndex(function (item) { return item.key === selectionValue; });
    if (versionPrevBtn) versionPrevBtn.disabled = currentIndex <= 0;
    if (versionNextBtn) versionNextBtn.disabled = currentIndex === -1 || currentIndex >= versions.length - 1;
    if (versionMetaEl) {
      var newest = versions[versions.length - 1];
      versionMetaEl.textContent = '当前 v' + (entry.version || 1) + ' / 共 ' + versions.length + ' 版' + (newest && newest.key === selectionValue ? ' · 最新版' : ' · 历史版');
    }
  }

  function updateCaseListHighlight(caseKey) {
    document.querySelectorAll('.case-list-item').forEach(function (el) {
      var target = el.getAttribute('data-case-key') || '';
      el.classList.toggle('active', (caseKey === 'all' && target === 'all') || target === caseKey);
    });
  }

  function renderFilterState() {
    currentFilteredEntries = applyFilters();
    currentVisibleEntries = applyBrowseMode(currentFilteredEntries);
    filterCountEl.textContent = '匹配 ' + currentFilteredEntries.length + '/' + staticEntries.length + ' 个案例，当前展示 ' + currentVisibleEntries.length + ' 个';
    if (filterSummaryEl) filterSummaryEl.innerHTML = buildFilterSummaryHtml();
    updateSubtitle(staticEntries.length, currentFilteredEntries.length);
    rebuildCaseSelect(currentVisibleEntries);
    rebuildCaseList(currentVisibleEntries);
    currentFilter = normalizeSelectionValue(currentFilter, currentFilteredEntries);
    updateVersionControl(currentFilter);
  }

  function getSelectedEntries() {
    if (!currentFilter || currentFilter === 'all') return currentVisibleEntries.slice();
    if (isSavedCaseKey(currentFilter)) {
      var saved = entryMap.get(currentFilter);
      return saved ? [saved] : [];
    }
    return currentFilteredEntries.filter(function (entry) { return entry.key === currentFilter; });
  }

  function getNodeShapeIcon(shape) {
    if (shape === 'hexagon') return '⬡';
    if (shape === 'box') return '▢';
    if (shape === 'diamond') return '◇';
    if (shape === 'database') return '🗄';
    if (shape === 'triangle') return '△';
    if (shape === 'star') return '★';
    if (shape === 'square') return '□';
    return '○';
  }

  function buildAdminLegend() {
    var roots = ['LegalNorm', 'JudicialEntity', 'LegalSubject', 'Person'];
    var names = { LegalNorm: '规范层', JudicialEntity: '司法实体层', LegalSubject: '主体层', Person: '自然人' };
    var children = {
      LegalNorm: ['GuidingCase', 'LegalProvision', 'LegalProvisionElement'],
      JudicialEntity: ['CourtCase', 'CaseType', 'CaseSummary', 'Evidence', 'JudgmentResult', 'Fact', 'DisputeFocus'],
      LegalSubject: ['LegalSubject'],
      Person: ['Judge', 'Attorney'],
    };
    var html = '<div class="legend-title"><span>📋 实体类型</span><span class="legend-close" onclick="toggleLegend()">✕</span></div>';
    roots.forEach(function (root) {
      var color = ROOT_COLORS[root] || { bg: '#7f8c8d' };
      html += '<div class="legend-root"><span class="dot" style="background:' + color.bg + ';"></span><span>' + root + '（' + (names[root] || '') + '）</span></div><div class="legend-children">';
      (children[root] || []).forEach(function (type) {
        html += '<div class="legend-child"><span class="cdot" style="background:' + color.bg + ';"></span><span>' + getNodeShapeIcon(ADMIN_SHAPES[type] || 'ellipse') + ' ' + type + '</span></div>';
      });
      html += '</div>';
    });
    document.querySelector('.legend').innerHTML = html;
  }

  function toggleLegend() {
    var legend = document.querySelector('.legend');
    legend.classList.toggle('collapsed');
    localStorage.setItem('adminLegendCollapsed', legend.classList.contains('collapsed') ? 'true' : 'false');
  }

  function initLegendDrag() {
    var legend = document.querySelector('.legend');
    var trigger = document.querySelector('.legend-show-trigger');
    var saved = localStorage.getItem('adminLegendPos');
    if (saved) {
      try {
        var pos = JSON.parse(saved);
        legend.style.left = pos.left;
        legend.style.top = pos.top;
        trigger.style.left = pos.left;
        trigger.style.top = pos.top;
      } catch (err) {}
    }
    if (localStorage.getItem('adminLegendCollapsed') === 'true') legend.classList.add('collapsed');
    legend.addEventListener('mousedown', function (e) {
      if (e.target.closest('.legend-close')) return;
      legendDragData = {
        offsetX: e.clientX - legend.getBoundingClientRect().left,
        offsetY: e.clientY - legend.getBoundingClientRect().top,
      };
      legend.classList.add('dragging');
      e.preventDefault();
    });
    document.addEventListener('mousemove', function (e) {
      if (!legendDragData) return;
      var left = Math.max(0, Math.min(e.clientX - legendDragData.offsetX, window.innerWidth - 40));
      var top = Math.max(0, Math.min(e.clientY - legendDragData.offsetY, window.innerHeight - 40));
      legend.style.left = left + 'px';
      legend.style.top = top + 'px';
      trigger.style.left = left + 'px';
      trigger.style.top = top + 'px';
    });
    document.addEventListener('mouseup', function () {
      if (!legendDragData) return;
      legendDragData = null;
      legend.classList.remove('dragging');
      localStorage.setItem('adminLegendPos', JSON.stringify({ left: legend.style.left, top: legend.style.top }));
    });
  }

  function showRawData(selectionValue) {
    var subtitle = '';
    if (!selectionValue || selectionValue === 'all') {
      subtitle = '当前为结果集视图，建议选择单个案例查看完整原始记录。';
      rawContentEl.textContent = JSON.stringify({
        browse_mode: getBrowseModeLabel(),
        density_mode: getDensityModeLabel(),
        filtered_cases: currentFilteredEntries.length,
        displayed_cases: currentVisibleEntries.length,
        sample_cases: currentVisibleEntries.slice(0, 5).map(function (entry) {
          return { row_id: entry.row_id, case_name: entry.case_name, version: entry.version };
        })
      }, null, 2);
      if (rawDataSubtitleEl) rawDataSubtitleEl.textContent = subtitle;
      return;
    }
    var entry = entryMap.get(selectionValue);
    if (!entry) {
      rawContentEl.textContent = '未找到该案例的原始数据';
      if (rawDataSubtitleEl) rawDataSubtitleEl.textContent = '未找到对应案例记录';
      return;
    }
    if (rawViewMode === 'full') {
      rawContentEl.textContent = JSON.stringify(entry.rawRecord, null, 2);
      subtitle = '当前显示该案例的完整原始 JSON。';
    } else if (currentSelection && currentSelection.type === 'node') {
      var node = currentRenderedNodeMap.get(currentSelection.id);
      rawContentEl.textContent = JSON.stringify({
        mode: 'focus-snippet',
        selection_type: 'node',
        node: node ? {
          id: node.id,
          label: node.fullLabel || node.label,
          node_type: node.nodeType,
          case_name: node.caseName,
          row_id: node.rowId,
          detail: stripHtml(node.title || ''),
        } : { id: currentSelection.id },
        relations: getNodeRelatedItems(currentSelection.id),
        output_summary: getEntryGraphStats(entry),
      }, null, 2);
      subtitle = '当前显示所选节点的摘要片段与直接关系。';
    } else if (currentSelection && currentSelection.type === 'edge') {
      var edge = currentRenderedEdgeMap.get(currentSelection.id);
      rawContentEl.textContent = JSON.stringify({
        mode: 'focus-snippet',
        selection_type: 'edge',
        edge: edge ? {
          id: edge.id,
          relation: edge.label || edge.relationType,
          relation_type: edge.relationType || '',
          from: edge.from,
          to: edge.to,
          case_name: edge.caseName,
          row_id: edge.rowId,
        } : { id: currentSelection.id },
        output_summary: getEntryGraphStats(entry),
      }, null, 2);
      subtitle = '当前显示所选关系的摘要片段。';
    } else {
      rawContentEl.textContent = JSON.stringify({
        mode: 'case-snippet',
        case_name: entry.case_name,
        row_id: entry.row_id,
        source: CASE_SOURCE_LABELS[entry.source] || entry.source,
        version: entry.version,
        summary: summarizeEntry(entry),
        output_keys: Object.keys(entry.output || {}),
      }, null, 2);
      subtitle = '当前显示案例级摘要；点击节点或关系后会切换为聚焦片段。';
    }
    if (rawDataSubtitleEl) rawDataSubtitleEl.textContent = subtitle;
  }

  function toggleRawData() {
    rawDataOpen = !rawDataOpen;
    rawDataPanel.classList.toggle('open', rawDataOpen);
    rawDataLabelEl.textContent = rawDataOpen ? '收起' : '展开';
    if (network && currentSelection) setTimeout(function () { focusCurrentSelection(false); }, 20);
  }

  function setRawViewMode(mode) {
    rawViewMode = mode === 'full' ? 'full' : 'snippet';
    if (rawModeSnippetBtn) rawModeSnippetBtn.classList.toggle('active', rawViewMode === 'snippet');
    if (rawModeFullBtn) rawModeFullBtn.classList.toggle('active', rawViewMode === 'full');
    showRawData(currentFilter);
  }

  function getElementOverlapRect(baseRect, el) {
    if (!el) return null;
    var style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return null;
    var rect = el.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    var left = Math.max(baseRect.left, rect.left);
    var right = Math.min(baseRect.right, rect.right);
    var top = Math.max(baseRect.top, rect.top);
    var bottom = Math.min(baseRect.bottom, rect.bottom);
    if (right <= left || bottom <= top) return null;
    return { left: left, right: right, top: top, bottom: bottom };
  }

  function getNetworkViewportOffset() {
    if (!network || !network.body || !network.body.container) return { x: 0, y: 0 };
    var baseRect = network.body.container.getBoundingClientRect();
    var visible = { left: baseRect.left, right: baseRect.right, top: baseRect.top, bottom: baseRect.bottom };
    [document.querySelector('.header'), document.querySelector('.control-bar')].forEach(function (el) {
      var overlap = getElementOverlapRect(baseRect, el);
      if (overlap && overlap.top <= visible.top + 80) visible.top = Math.min(visible.bottom, overlap.bottom + 8);
    });
    var detailOverlap = getElementOverlapRect(baseRect, detailPanel);
    if (detailOverlap && detailPanel.classList.contains('open')) visible.right = Math.max(visible.left, detailOverlap.left - 8);
    var rawOverlap = getElementOverlapRect(baseRect, rawDataPanel);
    if (rawOverlap && rawDataPanel.classList.contains('open')) visible.bottom = Math.max(visible.top, rawOverlap.top - 8);
    var listOverlap = getElementOverlapRect(baseRect, caseListPanel);
    if (listOverlap && caseListPanel.classList.contains('open')) visible.right = Math.max(visible.left, listOverlap.left - 8);
    return {
      x: Math.round((visible.left + visible.right) / 2 - (baseRect.left + baseRect.right) / 2),
      y: Math.round((visible.top + visible.bottom) / 2 - (baseRect.top + baseRect.bottom) / 2),
    };
  }

  function centerNetworkOnNode(nodeId) {
    if (!network) return;
    var positions = network.getPositions([nodeId]);
    var pos = positions[nodeId];
    if (!pos) return;
    var offset = getNetworkViewportOffset();
    network.moveTo({
      position: { x: pos.x, y: pos.y },
      offset: { x: -offset.x, y: -offset.y },
      animation: { duration: 280, easingFunction: 'easeInOutQuad' },
      scale: network.getScale(),
    });
  }

  function centerNetworkOnEdge(edgeId) {
    if (!network || !edgesDataset) return;
    var edge = edgesDataset.get(edgeId);
    if (!edge) return;
    var positions = network.getPositions([edge.from, edge.to]);
    if (!positions[edge.from] || !positions[edge.to]) return;
    var offset = getNetworkViewportOffset();
    network.moveTo({
      position: {
        x: (positions[edge.from].x + positions[edge.to].x) / 2,
        y: (positions[edge.from].y + positions[edge.to].y) / 2,
      },
      offset: { x: -offset.x, y: -offset.y },
      animation: { duration: 280, easingFunction: 'easeInOutQuad' },
      scale: network.getScale(),
    });
  }

  function clearGraphFocus() {
    if (!nodesDataset || !edgesDataset) return;
    nodesDataset.forEach(function (node) {
      nodesDataset.update({ id: node.id, hidden: false, opacity: 1, color: node.originalColor || node.color, font: node.originalFont || node.font });
    });
    edgesDataset.forEach(function (edge) {
      edgesDataset.update({ id: edge.id, hidden: false, color: edge.originalColor || edge.color, width: edge.originalWidth || edge.width, font: edge.originalFont || edge.font });
    });
  }

  function applyGraphFocus(selection) {
    if (!selection || !nodesDataset || !edgesDataset) {
      clearGraphFocus();
      return;
    }
    var keepNodes = new Set();
    var keepEdges = new Set();
    if (selection.type === 'node') {
      keepNodes.add(selection.id);
      edgesDataset.forEach(function (edge) {
        if (edge.from === selection.id || edge.to === selection.id) {
          keepEdges.add(edge.id);
          keepNodes.add(edge.from);
          keepNodes.add(edge.to);
        }
      });
    } else {
      var target = edgesDataset.get(selection.id);
      if (target) {
        keepEdges.add(target.id);
        keepNodes.add(target.from);
        keepNodes.add(target.to);
        edgesDataset.forEach(function (edge) {
          if (edge.id !== target.id && (edge.from === target.from || edge.to === target.from || edge.from === target.to || edge.to === target.to)) {
            keepEdges.add(edge.id);
            keepNodes.add(edge.from);
            keepNodes.add(edge.to);
          }
        });
      }
    }
    nodesDataset.forEach(function (node) {
      nodesDataset.update({ id: node.id, hidden: false, opacity: keepNodes.has(node.id) ? 1 : 0.22 });
    });
    edgesDataset.forEach(function (edge) {
      var active = keepEdges.has(edge.id);
      edgesDataset.update({
        id: edge.id,
        hidden: false,
        color: Object.assign({}, edge.originalColor || edge.color, { opacity: active ? 0.95 : 0.08 }),
        width: active ? 2.4 : 1.1,
      });
    });
  }

  function getRelatedSubset(selection, nodes, edges) {
    if (!selection) return { nodes: nodes, edges: edges };
    var keepNodes = new Set();
    var keepEdges = new Set();
    if (selection.type === 'node') {
      keepNodes.add(selection.id);
      edges.forEach(function (edge) {
        if (edge.from === selection.id || edge.to === selection.id) {
          keepEdges.add(edge.id);
          keepNodes.add(edge.from);
          keepNodes.add(edge.to);
        }
      });
    } else {
      var target = edges.find(function (edge) { return edge.id === selection.id; });
      if (!target) return { nodes: nodes, edges: edges };
      keepEdges.add(target.id);
      keepNodes.add(target.from);
      keepNodes.add(target.to);
      edges.forEach(function (edge) {
        if (edge.id !== target.id && (edge.from === target.from || edge.to === target.from || edge.from === target.to || edge.to === target.to)) {
          keepEdges.add(edge.id);
          keepNodes.add(edge.from);
          keepNodes.add(edge.to);
        }
      });
    }
    return {
      nodes: nodes.filter(function (node) { return keepNodes.has(node.id); }),
      edges: edges.filter(function (edge) { return keepEdges.has(edge.id); }),
    };
  }

  function buildVisData(entries, selection) {
    var allNodes = [];
    var allEdges = [];
    entries.forEach(function (entry) {
      entry.nodes.forEach(function (node) { allNodes.push(node); });
      entry.edges.forEach(function (edge) { allEdges.push(edge); });
    });
    if (currentGraphViewMode === 'related' && selection) {
      var subset = getRelatedSubset(selection, allNodes, allEdges);
      allNodes = subset.nodes;
      allEdges = subset.edges;
    }
    var denseGraph = allEdges.length > 80 || entries.length > 3;
    var densityMode = currentDensityMode;
    var nodeIndex = new Map();
    var edgeIndex = new Map();
    var visNodes = allNodes.map(function (node) {
      var color = getAdminColor(node.nodeType);
      var bg = (node.level || 0) >= 2 ? lightenColor(color.bg, 35) : color.bg;
      var labelMax = densityMode === 'overview' ? 10 : densityMode === 'detail' ? 40 : (denseGraph ? 16 : 24);
      var fontSize = densityMode === 'overview' ? (node.level === 0 ? 12 : 10) : densityMode === 'detail' ? (node.level === 0 ? 16 : 13) : (node.level === 0 ? 14 : 12);
      var nodeSize = densityMode === 'overview' ? (node.level === 0 ? 31 : node.level === 1 ? 22 : 17) : densityMode === 'detail' ? (node.level === 0 ? 38 : node.level === 1 ? 28 : 22) : (node.level === 0 ? 35 : node.level === 1 ? 26 : 20);
      var visNode = Object.assign({}, node, {
        label: shortText(node.fullLabel || node.label || '', labelMax),
        shape: ADMIN_SHAPES[node.nodeType] || 'ellipse',
        size: nodeSize,
        color: { background: bg, border: color.border },
        font: { color: '#fff', size: fontSize, face: 'Microsoft YaHei, PingFang SC, sans-serif' },
        borderWidth: 2,
        opacity: 1,
      });
      visNode.originalColor = JSON.parse(JSON.stringify(visNode.color));
      visNode.originalFont = JSON.parse(JSON.stringify(visNode.font));
      nodeIndex.set(visNode.id, visNode);
      return visNode;
    });
    var visEdges = allEdges.map(function (edge) {
      var edgeFontSize = densityMode === 'overview' ? 0 : densityMode === 'detail' ? 11 : (denseGraph ? 0 : 10);
      var edgeStrokeWidth = edgeFontSize ? 2 : 0;
      var visEdge = Object.assign({}, edge, {
        color: { color: '#7f8c8d', highlight: '#333', hover: '#333', opacity: 0.72 },
        font: { size: edgeFontSize, color: '#555', strokeWidth: edgeStrokeWidth, strokeColor: '#fff' },
        width: densityMode === 'overview' ? 1.1 : denseGraph ? 1.2 : 1.5,
        smooth: { type: 'continuous' },
        arrows: { to: { enabled: true, scaleFactor: 0.6 } },
      });
      visEdge.originalColor = JSON.parse(JSON.stringify(visEdge.color));
      visEdge.originalFont = JSON.parse(JSON.stringify(visEdge.font));
      visEdge.originalWidth = visEdge.width;
      edgeIndex.set(visEdge.id, visEdge);
      return visEdge;
    });
    return { nodes: visNodes, edges: visEdges, nodeIndex: nodeIndex, edgeIndex: edgeIndex };
  }

  function buildNetworkOptions() {
    if (currentLayoutMode === 'hierarchical') {
      return {
        physics: { enabled: false },
        interaction: { hover: false, tooltipDelay: 100, navigationButtons: true, keyboard: true, zoomView: true, dragView: true },
        edges: { smooth: { type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.4 } },
        layout: { hierarchical: { enabled: true, direction: 'LR', sortMethod: 'directed', nodeSpacing: 150, levelSeparation: 200 } },
        nodes: { shadow: { enabled: true, size: 3, x: 0, y: 0 } },
      };
    }
    return {
      physics: {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.005, springLength: 180, springConstant: 0.08, damping: 0.4 },
        stabilization: { iterations: 150, fit: true },
        minVelocity: 0.5,
      },
      interaction: { hover: false, tooltipDelay: 100, navigationButtons: true, keyboard: true, zoomView: true, dragView: true },
      edges: { smooth: { type: 'continuous' } },
      layout: { improvedLayout: false, randomSeed: 42 },
      nodes: { shadow: { enabled: true, size: 3, x: 0, y: 0 } },
    };
  }

  function renderEmptyNetwork(message) {
    document.getElementById('mynetwork').innerHTML = '<div class="loading">' + escapeHtml(message || '无数据') + '</div>';
    statsEl.textContent = '0 nodes, 0 edges';
  }

  function renderEntityDetail(node) {
    var relatedItems = getNodeRelatedItems(node.id);
    var relatedHtml = relatedItems.length
      ? '<div class="relation-list">' + relatedItems.slice(0, 8).map(function (item) {
        return '<div class="relation-item"><div class="relation-item-title">' + escapeHtml(item.relation) + '</div><div class="relation-item-meta">' +
          (item.direction === 'out' ? '指向' : '来自') + ' · ' + escapeHtml(item.targetType) + ' · ' + escapeHtml(item.targetLabel) +
          '</div></div>';
      }).join('') + (relatedItems.length > 8 ? '<div class="desc-text">其余 ' + (relatedItems.length - 8) + ' 条关联可在图上继续查看。</div>' : '') + '</div>'
      : '<div class="empty-hint">当前对象没有直接相邻的关系节点。</div>';
    panelTitle.textContent = '📋 ' + (node.nodeType || '节点');
    detailPanel.classList.remove('edge-mode');
    panelBody.innerHTML =
      '<div class="panel-section"><div class="summary-card">' +
      '<div class="summary-card-title">' + escapeHtml(node.fullLabel || node.label || '') + '</div>' +
      '<div class="summary-card-subtitle">#' + escapeHtml(node.rowId || '') + ' · ' + escapeHtml(node.caseName || '') + '</div>' +
      '<div class="summary-badges">' +
      '<span class="summary-badge">' + escapeHtml(node.nodeType || '节点') + '</span>' +
      '<span class="summary-badge">' + escapeHtml(CASE_SOURCE_LABELS[node.source] || node.source || '') + '</span>' +
      '<span class="summary-badge">关联 ' + relatedItems.length + ' 条</span>' +
      '</div></div></div>' +
      '<div class="panel-section"><div class="panel-section-title">对象摘要</div>' +
      '<div class="field-row"><strong>名称</strong><span>' + escapeHtml(node.fullLabel || node.label || '') + '</span></div>' +
      '<div class="field-row"><strong>类型</strong><span>' + escapeHtml(node.nodeType || '') + '</span></div>' +
      '<div class="field-row"><strong>案例</strong><span>#' + escapeHtml(node.rowId || '') + '</span></div>' +
      '<div class="field-row"><strong>来源</strong><span>' + escapeHtml(CASE_SOURCE_LABELS[node.source] || node.source || '') + '</span></div></div>' +
      '<div class="panel-section"><div class="panel-section-title">图谱关联</div>' + relatedHtml + '</div>' +
      '<div class="panel-section"><div class="panel-section-title">详细信息</div><div class="desc-text">' + escapeHtml(stripHtml(node.title) || '暂无详细信息') + '</div></div>';
    detailPanel.classList.add('open');
  }

  function renderEdgeDetail(edge) {
    var fromNode = currentRenderedNodeMap.get(edge.from);
    var toNode = currentRenderedNodeMap.get(edge.to);
    panelTitle.textContent = '🔗 ' + (edge.label || edge.relationType || '关系');
    detailPanel.classList.add('edge-mode');
    panelBody.innerHTML =
      '<div class="panel-section"><div class="summary-card">' +
      '<div class="summary-card-title">' + escapeHtml(edge.label || edge.relationType || '关系') + '</div>' +
      '<div class="summary-card-subtitle">#' + escapeHtml(edge.rowId || '') + ' · ' + escapeHtml(edge.caseName || '') + '</div>' +
      '<div class="summary-badges">' +
      '<span class="summary-badge">' + escapeHtml(edge.relationType || edge.label || '关系边') + '</span>' +
      '<span class="summary-badge">' + escapeHtml(CASE_SOURCE_LABELS[edge.source] || edge.source || '') + '</span>' +
      '</div></div></div>' +
      '<div class="panel-section"><div class="panel-section-title">关系摘要</div>' +
      '<div class="field-row"><strong>关系</strong><span>' + escapeHtml(edge.label || edge.relationType || '') + '</span></div>' +
      '<div class="field-row"><strong>来源案例</strong><span>#' + escapeHtml(edge.rowId || '') + ' · ' + escapeHtml(edge.caseName || '') + '</span></div></div>' +
      '<div class="panel-section"><div class="panel-section-title">方向</div>' +
      '<div class="field-row"><strong>起点</strong><span>' + escapeHtml(fromNode ? (fromNode.fullLabel || fromNode.label) : edge.from) + '</span></div>' +
      '<div class="field-row"><strong>终点</strong><span>' + escapeHtml(toNode ? (toNode.fullLabel || toNode.label) : edge.to) + '</span></div>' +
      '<div class="field-row"><strong>方向说明</strong><span>' + escapeHtml((fromNode ? (fromNode.nodeType || '节点') : '节点') + ' → ' + (toNode ? (toNode.nodeType || '节点') : '节点')) + '</span></div></div>';
    detailPanel.classList.add('open');
  }

  function syncGraphActionState() {
    if (!relatedBtn) return;
    relatedBtn.disabled = !currentSelection;
    relatedBtn.classList.toggle('active', currentGraphViewMode === 'related');
  }

  function focusCurrentSelection(shouldCenter) {
    if (!currentSelection) {
      clearGraphFocus();
      syncGraphActionState();
      return;
    }
    if (currentSelection.type === 'node') {
      if (!currentRenderedNodeMap.has(currentSelection.id)) return;
      applyGraphFocus(currentSelection);
      if (shouldCenter) centerNetworkOnNode(currentSelection.id);
    } else {
      if (!currentRenderedEdgeMap.has(currentSelection.id)) return;
      applyGraphFocus(currentSelection);
      if (shouldCenter) centerNetworkOnEdge(currentSelection.id);
    }
    syncGraphActionState();
  }

  function hideAdminPanel(options) {
    options = options || {};
    detailPanel.classList.remove('open');
    detailPanel.classList.remove('edge-mode');
    panelTitle.textContent = '📋 详细信息';
    panelBody.innerHTML = '<div class="empty-hint">点击节点或关系查看详细信息</div>';
    currentSelection = null;
    clearGraphFocus();
    if (!options.keepRelatedMode && currentGraphViewMode === 'related') currentGraphViewMode = 'all';
    syncGraphActionState();
    showRawData(currentFilter);
    if (!options.silent) refreshCurrentView(false);
  }

  function openNode(nodeId, shouldCenter) {
    var node = currentRenderedNodeMap.get(nodeId);
    if (!node) return;
    currentSelection = { type: 'node', id: nodeId };
    renderEntityDetail(node);
    syncGraphActionState();
    showRawData(currentFilter);
    if (currentGraphViewMode === 'related') refreshCurrentView(false);
    else focusCurrentSelection(shouldCenter !== false);
  }

  function openEdge(edgeId, shouldCenter) {
    var edge = currentRenderedEdgeMap.get(edgeId);
    if (!edge) return;
    currentSelection = { type: 'edge', id: edgeId };
    renderEdgeDetail(edge);
    syncGraphActionState();
    showRawData(currentFilter);
    if (currentGraphViewMode === 'related') refreshCurrentView(false);
    else focusCurrentSelection(shouldCenter !== false);
  }

  function refreshCurrentView(shouldCenter) {
    var entries = getSelectedEntries();
    if (!entries.length) {
      renderEmptyNetwork('无匹配案例');
      syncGraphActionState();
      return;
    }
    var data = buildVisData(entries, currentSelection);
    currentRenderedNodeMap = data.nodeIndex;
    currentRenderedEdgeMap = data.edgeIndex;
    if (currentSelection) {
      var exists = currentSelection.type === 'node' ? currentRenderedNodeMap.has(currentSelection.id) : currentRenderedEdgeMap.has(currentSelection.id);
      if (!exists) currentSelection = null;
    }
    if (!data.nodes.length) {
      renderEmptyNetwork('当前案例暂无图谱结构');
      syncGraphActionState();
      return;
    }
    document.getElementById('mynetwork').innerHTML = '';
    nodesDataset = new vis.DataSet(data.nodes);
    edgesDataset = new vis.DataSet(data.edges);
    network = new vis.Network(document.getElementById('mynetwork'), { nodes: nodesDataset, edges: edgesDataset }, buildNetworkOptions());
    network.on('stabilizationIterationsDone', function () {
      if (currentLayoutMode === 'force') network.setOptions({ physics: { enabled: false } });
      network.fit({ animation: true });
    });
    network.on('click', function (params) {
      if (params.nodes && params.nodes.length) openNode(params.nodes[0], true);
      else if (params.edges && params.edges.length) openEdge(params.edges[0], true);
      else if (detailPanel.classList.contains('open')) hideAdminPanel({ keepRelatedMode: false, silent: true });
    });
    statsEl.textContent = data.nodes.length + ' nodes, ' + data.edges.length + ' edges';
    totalCasesEl.textContent = entries.length;
    updateCaseListHighlight(currentFilter);
    syncGraphActionState();
    if (currentSelection) {
      focusCurrentSelection(shouldCenter !== false);
      if (currentSelection.type === 'node') renderEntityDetail(currentRenderedNodeMap.get(currentSelection.id));
      else renderEdgeDetail(currentRenderedEdgeMap.get(currentSelection.id));
    }
    showRawData(currentFilter);
  }

  function ensureSavedEntryLoaded(caseKey) {
    if (entryMap.has(caseKey)) return Promise.resolve(entryMap.get(caseKey));
    var meta = savedCaseMetaMap.get(caseKey);
    if (!meta) return Promise.resolve(null);
    var parsedKey = parseSavedCaseKey(caseKey);
    return fetch('/api/saved-case/' + encodeURIComponent(parsedKey.rowId))
      .then(function (res) {
        if (!res.ok) throw new Error('案例未找到');
        return res.json();
      })
      .then(function (data) {
        var record = {
          row_id: data.row_id,
          case_name: data.case_name,
          output: data.json_result,
          input: { web_name: CASE_SOURCE_LABELS[meta.source] || meta.source },
          source: meta.source,
        };
        var entry = createEntryFromRecord(record, {
          key: caseKey,
          rowId: data.row_id,
          caseName: data.case_name,
          version: 1,
          source: meta.source,
        });
        entry.meta = extractEntryMeta(entry);
        entryMap.set(caseKey, entry);
        return entry;
      });
  }

  function renderCurrentSelection() {
    var needsFetch = isSavedCaseKey(currentFilter) && !entryMap.has(currentFilter);
    if (!needsFetch) {
      refreshCurrentView(false);
      return Promise.resolve();
    }
    renderEmptyNetwork('正在加载网页保存案例...');
    return ensureSavedEntryLoaded(currentFilter)
      .then(function () {
        refreshCurrentView(false);
      })
      .catch(function (err) {
        renderEmptyNetwork('加载失败: ' + err.message);
      });
  }

  function onFilterChange() {
    renderFilterState();
    if (currentFilter !== 'all' && !caseSelect.querySelector('option[value="' + CSS.escape(currentFilter) + '"]')) currentFilter = 'all';
    caseSelect.value = currentFilter;
    renderCurrentSelection();
  }

  function filterByCase(value) {
    currentFilter = normalizeSelectionValue(value, currentFilteredEntries);
    updateVersionControl(currentFilter);
    caseSelect.value = currentFilter;
    renderCurrentSelection();
  }

  function switchVersion(value) { filterByCase(value); }

  function stepVersion(direction) {
    var versions = getVersionEntriesForSelection(currentFilter);
    if (!versions.length) return;
    var currentIndex = versions.findIndex(function (item) { return item.key === currentFilter; });
    if (currentIndex === -1) return;
    var next = versions[currentIndex + direction];
    if (next) filterByCase(next.key);
  }

  function setBrowseMode(btn, mode) {
    currentBrowseMode = mode;
    document.querySelectorAll('#browseModeRecent, #browseModeLatest, #browseModeAll').forEach(function (el) {
      el.classList.toggle('active', el === btn);
    });
    renderFilterState();
    if (currentFilter === 'all') renderCurrentSelection();
    else {
      updateVersionControl(currentFilter);
      updateSubtitle(staticEntries.length, currentFilteredEntries.length);
      rebuildCaseList(currentVisibleEntries);
      showRawData(currentFilter);
    }
  }

  function setDensityMode(btn, mode) {
    currentDensityMode = mode;
    document.querySelectorAll('#densityModeOverview, #densityModeStandard, #densityModeDetail').forEach(function (el) {
      el.classList.toggle('active', el === btn);
    });
    updateSubtitle(staticEntries.length, currentFilteredEntries.length || staticEntries.length);
    refreshCurrentView(false);
  }

  function setLayout(btn, mode) {
    currentLayoutMode = mode;
    document.querySelectorAll('.btn-group .btn').forEach(function (el) {
      if (el.id !== 'btnRelatedOnly') el.classList.remove('active');
    });
    if (btn) btn.classList.add('active');
    refreshCurrentView(false);
  }

  function fitView() {
    if (network) network.fit({ animation: true });
  }

  function toggleCaseList() {
    caseListPanel.classList.toggle('open');
    if (network && currentSelection) setTimeout(function () { focusCurrentSelection(false); }, 20);
  }

  function selectFromList(caseKey) {
    filterByCase(caseKey);
    if (caseKey !== 'all') caseListPanel.classList.remove('open');
  }

  function toggleRelatedOnly() {
    if (!currentSelection) return;
    currentGraphViewMode = currentGraphViewMode === 'related' ? 'all' : 'related';
    syncGraphActionState();
    refreshCurrentView(false);
  }

  function populateSavedCases() {
    return fetch('/api/cases')
      .then(function (res) { return res.ok ? res.json() : []; })
      .then(function (all) {
        savedCaseList.length = 0;
        savedCaseMetaMap.clear();
        all.filter(function (item) { return item.source === 'manual' || item.source === 'extracted_candidate'; }).forEach(function (item) {
          var key = makeSavedCaseKey(item);
          var info = { key: key, row_id: String(item.row_id), case_name: item.case_name, version: 1, source: item.source };
          savedCaseList.push(info);
          savedCaseMetaMap.set(key, info);
        });
        rebuildCaseSelect(currentVisibleEntries);
        rebuildCaseList(currentVisibleEntries);
      })
      .catch(function (err) {
        console.warn('Failed to load saved cases:', err);
      });
  }

  function bindPanelEvents() {
    panelClose.addEventListener('click', function (e) {
      e.stopPropagation();
      hideAdminPanel({ keepRelatedMode: false, silent: true });
    });
    detailPanel.addEventListener('mousedown', function (e) { e.stopPropagation(); });
    document.addEventListener('click', function (e) {
      if (e.target.closest('#mynetwork') || detailPanel.contains(e.target)) return;
      if (detailPanel.classList.contains('open')) hideAdminPanel({ keepRelatedMode: false, silent: true });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && detailPanel.classList.contains('open')) hideAdminPanel({ keepRelatedMode: false, silent: true });
    });
  }

  function init() {
    buildAdminLegend();
    initLegendDrag();
    hydrateStaticEntries();
    buildFilterOptions();
    bindPanelEvents();
    currentFilteredEntries = staticEntries.slice();
    currentVisibleEntries = applyBrowseMode(currentFilteredEntries);
    rebuildCaseSelect(currentVisibleEntries);
    rebuildCaseList(currentVisibleEntries);
    if (filterSummaryEl) {
      filterSummaryEl.innerHTML = '<span class="filter-summary-label">当前筛选</span><span class="filter-summary-empty">未设置额外筛选，默认展示最近较新的 5 个案例。</span>';
    }
    updateSubtitle(staticEntries.length, currentFilteredEntries.length);
    filterCountEl.textContent = '匹配 ' + currentFilteredEntries.length + '/' + staticEntries.length + ' 个案例，当前展示 ' + currentVisibleEntries.length + ' 个';
    showRawData('all');
    refreshCurrentView(false);
    populateSavedCases();
  }

  window.toggleLegend = toggleLegend;
  window.toggleRawData = toggleRawData;
  window.setRawViewMode = setRawViewMode;
  window.filterByCase = filterByCase;
  window.switchVersion = switchVersion;
  window.stepVersion = stepVersion;
  window.setBrowseMode = setBrowseMode;
  window.setDensityMode = setDensityMode;
  window.setLayout = setLayout;
  window.fitView = fitView;
  window.toggleCaseList = toggleCaseList;
  window.selectFromList = selectFromList;
  window.toggleRelatedOnly = toggleRelatedOnly;
  window.addEventListener('resize', function () {
    if (network) network.fit({ animation: false });
  });

  init();
})();
