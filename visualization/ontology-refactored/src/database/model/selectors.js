function normalizeType(value) {
  return value || '未标注类型';
}

function shortText(value, maxLen = 48) {
  const text = String(value == null ? '' : value).trim();
  return text.length <= maxLen ? text : `${text.slice(0, Math.max(0, maxLen - 1))}…`;
}

function toCaseCategoryLabel(value) {
  const mapping = {
    civil: '民事',
    criminal: '刑事',
    administrative: '行政'
  };
  return mapping[value] || value || '';
}

function nodeTitle(parts) {
  return (parts || []).filter(Boolean).join('<br>');
}

function normalizeSourceLabel(value, fallback = '未知来源') {
  return value || fallback;
}

function normalizeCaseCategoryLabel(value) {
  const mapping = {
    民事: '民事案件',
    刑事: '刑事案件',
    行政: '行政案件',
    civil: '民事案件',
    criminal: '刑事案件',
    administrative: '行政案件'
  };
  return mapping[value] || value || '';
}

function normalizeJudgmentResultType(value) {
  const mapping = {
    guilty: '有罪判决',
    not_guilty: '无罪判决',
    liable: '承担责任',
    not_liable: '不承担责任',
    dismissed: '驳回',
    withdrawn: '撤诉',
    partially_upheld: '部分维持',
    remanded: '发回重审',
    punitive_damages: '惩罚性赔偿',
    procedural_ruling: '程序性裁定',
    bankruptcy_declared: '宣告破产',
    mediation_agreement: '调解协议',
    arbitration_award: '仲裁裁决',
    administrative_decision: '行政决定'
  };
  return mapping[value] || value || '';
}

function uniqueText(values = []) {
  return [...new Set((values || []).filter(Boolean).map(value => String(value)))];
}

function normalizeMeta(item = {}, fallbackSource = '未知来源') {
  const baseMeta = item.meta || {};
  const sourceLabel = normalizeSourceLabel(baseMeta.source || item.source_label || item.source, fallbackSource);
  const caseCategories = uniqueText(
    (baseMeta.case_categories && baseMeta.case_categories.length
      ? baseMeta.case_categories
      : (baseMeta.category ? [baseMeta.category] : [])
    ).concat(baseMeta.types && !baseMeta.case_categories ? baseMeta.types.filter(value => ['民事', '刑事', '行政', '民事案件', '刑事案件', '行政案件', 'civil', 'criminal', 'administrative'].includes(value)) : [])
  ).map(normalizeCaseCategoryLabel);
  const caseReasons = uniqueText(
    (baseMeta.case_reasons && baseMeta.case_reasons.length
      ? baseMeta.case_reasons
      : []
    ).concat(baseMeta.types && !baseMeta.case_reasons ? baseMeta.types.filter(value => !['民事', '刑事', '行政', '民事案件', '刑事案件', '行政案件'].includes(value)) : [])
  );
  const trialLevels = uniqueText(baseMeta.trial_levels || baseMeta.trialLevels || []);
  const judgmentYears = uniqueText(baseMeta.judgment_years || baseMeta.judgmentYears || baseMeta.years || []);
  const publicationYears = uniqueText(baseMeta.publication_years || baseMeta.publicationYears || []);
  const displayTypes = uniqueText([
    ...caseCategories,
    ...caseReasons
  ]);

  return {
    source: sourceLabel,
    case_categories: caseCategories,
    case_reasons: caseReasons,
    trial_levels: trialLevels,
    judgment_years: judgmentYears,
    publication_years: publicationYears,
    types: displayTypes,
    years: uniqueText([...judgmentYears, ...publicationYears]),
    procedures: uniqueText(baseMeta.procedures || []),
    stats: baseMeta.stats || {}
  };
}

export function decorateStaticCases(cases = []) {
  return cases.map(item => ({
    ...item,
    source: item.source || 'static',
    caseKey: `static:${item.key || `${item.row_id}__v${item.version || 1}`}`,
    case_type: normalizeType(item.case_type),
    version: item.version || 1,
    recordSource: 'static',
    meta: normalizeMeta(item, '指导性案例库')
  }));
}

export function decorateSavedCases(cases = []) {
  return cases.map(item => ({
    ...item,
    source: item.source || 'manual',
    caseKey: `saved:${item.source || 'manual'}:${item.row_id}`,
    case_type: normalizeType(item.case_type),
    version: item.version || 1,
    recordSource: 'saved',
    meta: normalizeMeta(item, item.source === 'extracted_candidate' ? '网页候选保存' : '网页手动保存')
  }));
}

export function mergeCaseIndexes(staticCases = [], savedCases = []) {
  return [...staticCases, ...savedCases];
}

function sortText(values = []) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
}

function sortYears(values = []) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => Number(b) - Number(a));
}

function sortTrialLevels(values = []) {
  const order = new Map([
    ['一审', 1],
    ['二审', 2],
    ['再审', 3]
  ]);
  return [...new Set(values.filter(Boolean))].sort((a, b) => {
    const aOrder = order.get(a) || 99;
    const bOrder = order.get(b) || 99;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return a.localeCompare(b, 'zh-CN');
  });
}

export function getFilterOptions(cases = []) {
  const sources = [];
  const caseCategories = [];
  const caseReasons = [];
  const trialLevels = [];
  const judgmentYears = [];
  const publicationYears = [];

  cases.forEach(item => {
    const meta = item.meta || {};
    if (meta.source) sources.push(meta.source);
    (meta.case_categories || []).forEach(value => caseCategories.push(value));
    (meta.case_reasons || []).forEach(value => caseReasons.push(value));
    (meta.trial_levels || []).forEach(value => trialLevels.push(value));
    (meta.judgment_years || []).forEach(value => judgmentYears.push(value));
    (meta.publication_years || []).forEach(value => publicationYears.push(value));
  });

  return {
    sources: sortText(sources),
    caseCategories: sortText(caseCategories),
    caseReasons: sortText(caseReasons),
    trialLevels: sortTrialLevels(trialLevels),
    judgmentYears: sortYears(judgmentYears),
    publicationYears: sortYears(publicationYears)
  };
}

export function getFilteredCases(cases = [], filters = {}) {
  return cases.filter(item => {
    const meta = item.meta || {};
    if (filters.sources && filters.sources.length && !filters.sources.includes(meta.source)) return false;
    if (filters.caseCategories && filters.caseCategories.length && !(meta.case_categories || []).some(value => filters.caseCategories.includes(value))) return false;
    if (filters.caseReasons && filters.caseReasons.length && !(meta.case_reasons || []).some(value => filters.caseReasons.includes(value))) return false;
    if (filters.trialLevels && filters.trialLevels.length && !(meta.trial_levels || []).some(value => filters.trialLevels.includes(value))) return false;
    if (filters.judgmentYears && filters.judgmentYears.length && !(meta.judgment_years || []).some(value => filters.judgmentYears.includes(value))) return false;
    if (filters.publicationYears && filters.publicationYears.length && !(meta.publication_years || []).some(value => filters.publicationYears.includes(value))) return false;
    return true;
  });
}

function getLatestEntries(entries = []) {
  const latestByRow = new Map();
  entries.forEach(entry => {
    const existing = latestByRow.get(entry.row_id);
    if (!existing || (entry.version || 1) > (existing.version || 1)) {
      latestByRow.set(entry.row_id, entry);
    }
  });
  return Array.from(latestByRow.values());
}

function getTopEntriesByYear(limit, pool = []) {
  const scored = [];
  const seen = new Set();

  pool.forEach(entry => {
    if (seen.has(entry.row_id)) return;
    seen.add(entry.row_id);
    const years = (entry.meta?.years || []).map(value => Number(value)).filter(Boolean);
    scored.push({ entry, year: years.length ? Math.max(...years) : 0 });
  });

  scored.sort((a, b) => b.year - a.year);
  return scored.slice(0, limit).map(item => item.entry);
}

export function getVisibleCases(cases = [], browseMode = 'recent_latest') {
  if (browseMode === 'all_versions') return cases.slice();
  const latestEntries = getLatestEntries(cases);
  if (browseMode === 'latest_only') return latestEntries;
  return getTopEntriesByYear(5, latestEntries);
}

export function getActiveCaseEntry(state) {
  const key = state.selection.activeCaseKey;
  if (!key) return null;
  return state.data.casesIndex.find(item => item.caseKey === key) || null;
}

export function getVersionEntries(state, caseKey) {
  const active = caseKey
    ? state.data.casesIndex.find(item => item.caseKey === caseKey)
    : getActiveCaseEntry(state);
  if (!active) return [];
  const filtered = getFilteredCases(state.data.casesIndex, state.filters);
  return filtered
    .filter(item => item.row_id === active.row_id)
    .sort((a, b) => (a.version || 1) - (b.version || 1));
}

function getOverviewSourceId(sourceLabel) {
  return `source:${sourceLabel}`;
}

export function buildOverviewGraphData(cases = []) {
  const nodes = [];
  const edges = [];
  const sourceMap = new Map();

  cases.forEach(item => {
    const sourceLabel = item.meta?.source || item.source || '未知来源';
    const sourceId = getOverviewSourceId(sourceLabel);

    if (!sourceMap.has(sourceLabel)) {
      sourceMap.set(sourceLabel, sourceId);
      nodes.push({
        id: sourceId,
        label: sourceLabel,
        nodeType: 'SourceRoot',
        shape: 'hexagon',
        size: 34,
        color: { background: '#1d4ed8', border: '#1e3a8a' },
        font: { color: '#ffffff', size: 13 },
        title: `${sourceLabel} 来源案例`
      });
    }

    const typeLabel = (item.meta?.types || [item.case_type]).filter(Boolean).join(' / ');
    nodes.push({
      id: item.caseKey,
      label: shortText(item.case_name || item.row_id, 26),
      fullLabel: item.case_name || item.row_id,
      nodeType: 'CaseEntry',
      row_id: item.row_id,
      caseKey: item.caseKey,
      case_name: item.case_name,
      case_type: item.case_type,
      source: item.source,
      version: item.version,
      meta: item.meta,
      shape: 'box',
      size: 22,
      color: { background: '#f8fafc', border: '#94a3b8' },
      font: { color: '#0f172a', size: 12 },
      title: `${item.case_name || item.row_id}\n${typeLabel}`
    });

    edges.push({
      id: `edge:${sourceId}:${item.caseKey}`,
      from: sourceId,
      to: item.caseKey,
      label: item.case_type || '案例',
      relationType: item.case_type || '案例',
      caseKey: item.caseKey,
      rowId: item.row_id,
      caseName: item.case_name,
      arrows: 'to',
      color: { color: '#94a3b8', opacity: 0.75 },
      font: { size: 10, color: '#64748b', align: 'horizontal', strokeWidth: 2, strokeColor: '#ffffff' },
      smooth: { type: 'continuous' }
    });
  });

  sourceMap.forEach((sourceId, sourceLabel) => {
    const count = cases.filter(item => (item.meta?.source || item.source || '未知来源') === sourceLabel).length;
    const node = nodes.find(item => item.id === sourceId);
    if (node) {
      node.caseCount = count;
      node.label = `${sourceLabel} [${count}]`;
    }
  });

  return { mode: 'overview', nodes, edges };
}

const ROOT_COLORS = {
  LegalNorm: { bg: '#2980b9', border: '#1a5276' },
  JudicialEntity: { bg: '#d35400', border: '#a04000' },
  LegalSubject: { bg: '#27ae60', border: '#1e8449' },
  Person: { bg: '#16a085', border: '#0e6655' }
};

const ADMIN_TYPE_ROOT = {
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
  Attorney: 'Person'
};

const ADMIN_SHAPES = {
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
  DisputeFocus: 'star'
};

const REL_LABEL_MAP = {
  based_on: '依据',
  judgment_cites: '裁判依据',
  element_of_provision: '要件对应法条',
  leads_to: '推导出',
  proves_fact: '证明',
  resolved_by: '裁判',
  has_fact: '事实',
  has_dispute_focus: '焦点',
  submitted_for: '提交',
  cites: '引用'
};

function getAdminColor(typeName) {
  return ROOT_COLORS[ADMIN_TYPE_ROOT[typeName]] || { bg: '#7f8c8d', border: '#5d6d7e' };
}

function lightenColor(hex, percent) {
  if (!hex || typeof hex !== 'string' || !hex.startsWith('#')) return '#dbeafe';
  const num = parseInt(hex.slice(1), 16);
  const amt = Math.round(2.55 * percent);
  const r = Math.min(255, (num >> 16) + amt);
  const g = Math.min(255, ((num >> 8) & 255) + amt);
  const b = Math.min(255, (num & 255) + amt);
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}

function makeGraphPrefix(key) {
  return `g_${String(key).replace(/[^a-zA-Z0-9_]/g, '_')}_`;
}

function createNodeStyle(nodeType) {
  const color = getAdminColor(nodeType);
  return {
    shape: ADMIN_SHAPES[nodeType] || 'ellipse',
    color: {
      background: lightenColor(color.bg, 38),
      border: color.border,
      highlight: { background: color.bg, border: color.border }
    },
    borderWidth: 2,
    font: { color: '#0f172a', size: 12, strokeWidth: 2, strokeColor: '#ffffff' }
  };
}

export function buildStructuredGraphFromOutput(output = {}, ctx = {}) {
  const nodes = [];
  const edges = [];
  const nodeIds = new Set();
  const edgeKeys = new Set();
  const localToGlobal = new Map();
  const caseNumberToNode = new Map();
  const prefix = makeGraphPrefix(ctx.key || ctx.caseKey || ctx.rowId || 'case');
  let firstCourtLocalId = '';

  function globalId(localId) {
    return `${prefix}${String(localId).replace(/[^a-zA-Z0-9_:-]/g, '_')}`;
  }

  function addNode(localId, label, nodeType, level, title, extra) {
    const id = globalId(localId);
    if (nodeIds.has(id)) return id;
    nodeIds.add(id);
    localToGlobal.set(String(localId), id);
    nodes.push({
      id,
      label: shortText(label || nodeType || id, 24),
      fullLabel: label || '',
      title: title || '',
      level: level || 1,
      nodeType: nodeType || 'Unknown',
      caseKey: ctx.caseKey,
      rowId: ctx.rowId,
      caseName: ctx.caseName,
      source: ctx.source,
      ...createNodeStyle(nodeType),
      ...(extra || {})
    });
    return id;
  }

  function resolveRef(ref) {
    if (ref == null || ref === '') return '';
    const key = String(ref);
    if (localToGlobal.has(key)) return localToGlobal.get(key);
    if (caseNumberToNode.has(key)) return caseNumberToNode.get(key);
    const fallback = globalId(key);
    return nodeIds.has(fallback) ? fallback : '';
  }

  function addEdge(fromRef, toRef, label, extra) {
    const fromId = resolveRef(fromRef);
    const toId = resolveRef(toRef);
    if (!fromId || !toId) return;
    const edgeKey = `${fromId}|${toId}|${label || ''}`;
    if (edgeKeys.has(edgeKey)) return;
    edgeKeys.add(edgeKey);
    edges.push({
      id: `${prefix}edge_${edgeKeys.size}`,
      from: fromId,
      to: toId,
      label: label || '',
      relationType: (extra && extra.relationType) || label || '',
      caseKey: ctx.caseKey,
      rowId: ctx.rowId,
      caseName: ctx.caseName,
      source: ctx.source,
      arrows: 'to',
      color: { color: '#94a3b8', opacity: 0.8 },
      width: 1.5,
      font: { size: 10, color: '#64748b', align: 'horizontal', strokeWidth: 2, strokeColor: '#ffffff' },
      smooth: { type: 'continuous' },
      ...(extra || {})
    });
  }

  (output.court_cases || []).forEach((cc, index) => {
    cc = cc || {};
    const localId = `cc_${index}`;
    if (!firstCourtLocalId) firstCourtLocalId = localId;
    const caseNumber = cc.case_number || `case_${index}`;
    const ccId = addNode(localId, caseNumber, 'CourtCase', 0, nodeTitle([
      '<b>法院案件</b>',
      `案号: ${caseNumber}`,
      cc.court && cc.court.name ? `法院: ${cc.court.name}` : '',
      cc.trial_level ? `审级: ${cc.trial_level}` : '',
      cc.trial_procedure ? `程序: ${cc.trial_procedure}` : '',
      cc.judgment_date ? `裁判日期: ${cc.judgment_date}` : ''
    ]), { courtCaseNumber: caseNumber, size: 28 });
    caseNumberToNode.set(caseNumber, ccId);
  });

  const gc = output.guiding_case || {};
  if (gc.guiding_case_name) {
    addNode('gc', gc.guiding_case_name, 'GuidingCase', 0, nodeTitle([
      '<b>指导/典型案例</b>',
      gc.storage_no ? `入库编号: ${gc.storage_no}` : '',
      gc.binding_force ? `效力: ${gc.binding_force}` : '',
      gc.case_level ? `层级: ${gc.case_level}` : '',
      gc.publication_date ? `发布日期: ${gc.publication_date}` : '',
      gc.guiding_points ? `裁判要旨: ${shortText(gc.guiding_points, 180)}` : ''
    ]), { size: 26 });
    if (firstCourtLocalId) addEdge(firstCourtLocalId, 'gc', '关联');
  }

  const ct = output.case_type || {};
  if (ct.category || ct.level1 || ct.level2) {
    addNode('ct', ct.level2 || ct.level1 || toCaseCategoryLabel(ct.category) || '案件类型', 'CaseType', 0, nodeTitle([
      '<b>案件类型</b>',
      ct.category ? `类别: ${toCaseCategoryLabel(ct.category) || ct.category}` : '',
      ct.level1 ? `一级: ${ct.level1}` : '',
      ct.level2 ? `二级: ${ct.level2}` : ''
    ]), { size: 24 });
    if (ct.level1) addNode('ct_level1', ct.level1, 'CaseType', 1, `<b>一级案由</b><br>${ct.level1}`);
    if (ct.level2) addNode('ct_level2', ct.level2, 'CaseType', 1, `<b>二级案由</b><br>${ct.level2}`);
    if (ct.level1) addEdge('ct', 'ct_level1', '一级案由');
    if (ct.level2) addEdge('ct', 'ct_level2', '二级案由');
    (output.court_cases || []).forEach((_, index) => addEdge('ct', `cc_${index}`, '案由'));
  }

  const subjects = output.legal_subjects || output.parties || [];
  subjects.forEach((subj, index) => {
    subj = subj || {};
    addNode(`subj_${index}`, subj.name || `当事人_${index}`, 'LegalSubject', 0, nodeTitle([
      '<b>诉讼主体</b>',
      subj.name ? `名称: ${subj.name}` : '',
      subj.subject_type ? `类型: ${subj.subject_type}` : '',
      subj.org_type ? `组织性质: ${subj.org_type}` : ''
    ]));
  });
  subjects.forEach((subj, index) => {
    subj = subj || {};
    const roles = subj.roles || [];
    if (!roles.length) {
      if (firstCourtLocalId) addEdge(firstCourtLocalId, `subj_${index}`, '当事人');
      return;
    }
    roles.forEach(role => {
      role = role || {};
      addEdge(role.case_number || firstCourtLocalId, `subj_${index}`, role.role_name || '当事人');
    });
  });

  (output.judges || []).forEach((judge, index) => {
    judge = judge || {};
    addNode(`judge_${index}`, judge.name || `法官_${index}`, 'Judge', 1, nodeTitle([
      '<b>法官</b>',
      judge.name ? `姓名: ${judge.name}` : '',
      judge.case_number ? `案号: ${judge.case_number}` : ''
    ]));
    addEdge(judge.case_number || firstCourtLocalId, `judge_${index}`, '审判');
  });

  (output.attorneys || []).forEach((atty, index) => {
    atty = atty || {};
    addNode(`atty_${index}`, atty.name || `律师_${index}`, 'Attorney', 1, nodeTitle([
      '<b>律师</b>',
      atty.name ? `姓名: ${atty.name}` : '',
      atty.case_number ? `案号: ${atty.case_number}` : ''
    ]));
    addEdge(atty.case_number || firstCourtLocalId, `atty_${index}`, '代理');
  });

  (output.legal_provisions || []).forEach((prov, index) => {
    prov = prov || {};
    const provLocal = `prov_${index}`;
    const provLabel = `${prov.statute || '法规'}${prov.article ? `第${prov.article}条` : ''}`;
    addNode(provLocal, provLabel || `法条_${index}`, 'LegalProvision', 1, nodeTitle([
      '<b>法律条文</b>',
      prov.statute ? `法规: ${prov.statute}` : '',
      prov.article ? `条号: ${prov.article}` : '',
      prov.citation_purpose ? `目的: ${prov.citation_purpose}` : '',
      prov.content ? `内容: ${shortText(prov.content, 180)}` : ''
    ]), {
      articleNumber: String(prov.article || ''),
      statuteName: String(prov.statute || ''),
    });
    addEdge(prov.case_number || firstCourtLocalId, provLocal, '引用');
  });

  (output.legal_provision_elements || []).forEach((element, index) => {
    element = element || {};
    const elementLocal = element.id || `prov_elem_${index}`;
    addNode(elementLocal, element.content || element.applicable_fact_pattern || `法条要件_${index}`, 'LegalProvisionElement', 2, nodeTitle([
      '<b>法条构成要件</b>',
      element.element_type ? `类型: ${element.element_type}` : '',
      element.provision_index !== undefined && element.provision_index !== null ? `法条索引: ${element.provision_index}` : '',
      element.statute ? `法规: ${element.statute}` : '',
      element.article ? `条号: ${element.article}` : '',
      element.content ? `内容: ${shortText(element.content, 160)}` : '',
      element.applicable_fact_pattern ? `适用事实: ${shortText(element.applicable_fact_pattern, 160)}` : ''
    ]), { size: 18 });
  });

  (output.evidence || []).forEach((evid, index) => {
    evid = evid || {};
    const evidLocal = evid.id || `evid_${index}`;
    addNode(evidLocal, evid.content || `证据_${index}`, 'Evidence', 1, nodeTitle([
      '<b>证据</b>',
      evid.evidence_type ? `类型: ${evid.evidence_type}` : '',
      evid.submitted_by ? `提交方: ${evid.submitted_by}` : '',
      evid.admission_status ? `采信: ${evid.admission_status}` : '',
      evid.probative_force ? `证明力: ${evid.probative_force}` : '',
      evid.content ? `内容: ${shortText(evid.content, 180)}` : ''
    ]));
    addEdge(evid.case_number || firstCourtLocalId, evidLocal, '证据');
  });

  (output.judgment_results || []).forEach((jr, index) => {
    jr = jr || {};
    const jrLocal = jr.id || `jr_${index}`;
    const resultTypeLabel = normalizeJudgmentResultType(jr.result_type);
    const judgmentLabel = shortText(jr.specific_judgment || jr.reasoning || resultTypeLabel || `裁判结果_${index}`, 48);
    addNode(jrLocal, judgmentLabel, 'JudgmentResult', 0, nodeTitle([
      '<b>裁判结果</b>',
      resultTypeLabel ? `结果类型: ${resultTypeLabel}` : '',
      jr.specific_judgment ? `具体裁判: ${shortText(jr.specific_judgment, 180)}` : '',
      jr.reasoning ? `理由: ${shortText(jr.reasoning, 180)}` : '',
      jr.case_number ? `案号: ${jr.case_number}` : ''
    ]), { size: 24 });
    addEdge(jr.case_number || firstCourtLocalId, jrLocal, '裁判');
  });

  (output.facts || []).forEach((fact, index) => {
    fact = fact || {};
    const factLocal = fact.id || `fact_${index}`;
    addNode(factLocal, fact.content || `事实_${index}`, 'Fact', 1, nodeTitle([
      '<b>案件事实</b>',
      fact.fact_type ? `类型: ${fact.fact_type}` : '',
      fact.case_number ? `案号: ${fact.case_number}` : '',
      fact.content ? `内容: ${shortText(fact.content, 180)}` : ''
    ]));
    addEdge(fact.case_number || firstCourtLocalId, factLocal, '事实');
  });

  (output.dispute_focuses || []).forEach((focus, index) => {
    focus = focus || {};
    const focusLocal = focus.id || `focus_${index}`;
    addNode(focusLocal, focus.content || `争议焦点_${index}`, 'DisputeFocus', 0, nodeTitle([
      '<b>争议焦点</b>',
      focus.focus_type ? `类型: ${focus.focus_type}` : '',
      focus.case_number ? `案号: ${focus.case_number}` : '',
      focus.content ? `内容: ${shortText(focus.content, 180)}` : ''
    ]), { size: 24 });
    addEdge(focus.case_number || firstCourtLocalId, focusLocal, '争议焦点');
  });

  const summary = output.case_summary || {};
  if (summary.disputed_issues) {
    const issuesText = Array.isArray(summary.disputed_issues) ? summary.disputed_issues.join('；') : String(summary.disputed_issues);
    addNode('summary', issuesText, 'CaseSummary', 1, nodeTitle([
      '<b>案件摘要</b>',
      summary.key_facts ? `关键事实: ${shortText(summary.key_facts, 120)}` : '',
      issuesText ? `争议问题: ${shortText(issuesText, 180)}` : '',
      summary.conclusion ? `结论: ${shortText(summary.conclusion, 120)}` : ''
    ]), { size: 22 });
    if (firstCourtLocalId) addEdge(firstCourtLocalId, 'summary', '审理');
  }

  (output.relations || []).forEach(rel => {
    rel = rel || {};
    if (!rel.source_id || !rel.target_id) return;
    const label = rel.label || REL_LABEL_MAP[rel.relation_type] || rel.relation_type || '关联';
    addEdge(rel.source_id, rel.target_id, label, {
      relationType: rel.relation_type || label,
      edgeType: 'explicit',
      isDerived: false
    });
  });

  (output.derived_relations || []).forEach(rel => {
    rel = rel || {};
    if (!rel.source_id || !rel.target_id) return;
    const label = rel.label || REL_LABEL_MAP[rel.relation_type] || rel.relation_type || '补图关联';
    addEdge(rel.source_id, rel.target_id, label, {
      relationType: rel.relation_type || label,
      edgeType: 'derived',
      isDerived: true,
      dashes: [6, 4],
      color: { color: '#6366f1', opacity: 0.86 },
      font: { size: 10, color: '#4338ca', align: 'horizontal', strokeWidth: 2, strokeColor: '#ffffff' }
    });
  });

  return { mode: 'detail', nodes, edges };
}

export function buildDatabaseGraphData(state) {
  const filteredCases = getFilteredCases(state.data.casesIndex, state.filters);
  const visibleCases = getVisibleCases(filteredCases, state.graph.browseMode);
  const activeEntry = getActiveCaseEntry(state);
  const detail = activeEntry ? state.data.caseDetailMap[activeEntry.caseKey] : null;

  if (activeEntry && detail && detail.json_result) {
    return buildStructuredGraphFromOutput(detail.json_result, {
      key: activeEntry.caseKey,
      caseKey: activeEntry.caseKey,
      rowId: activeEntry.row_id,
      caseName: activeEntry.case_name,
      source: activeEntry.meta?.source || activeEntry.source
    });
  }

  return buildOverviewGraphData(visibleCases);
}
