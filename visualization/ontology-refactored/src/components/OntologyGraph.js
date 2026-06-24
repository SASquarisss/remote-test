import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { store } from '../store/index.js';
import { ENTITY_DATA, ENTITY_STYLES, EN_DESCRIPTIONS, RELATION_LABELS, TYPE_NAMES, ZH_LABELS } from '../data/schema.js';
import { getOntologyRelationEdges } from '../data/relationModel.js';
import { bindCustomPan } from '../utils/pan.js';

const DOMAIN_META = {
  legal_norm: { zh: '法源规范', en: 'Norms', x: -780, color: '#dbeafe', border: '#60a5fa' },
  legal_subject: { zh: '主体组织', en: 'Subjects', x: -260, color: '#ede9fe', border: '#8b5cf6' },
  case_core: { zh: '案件骨架', en: 'Case Core', x: 220, color: '#fee2e2', border: '#f87171' },
  reasoning: { zh: '事实论证', en: 'Reasoning', x: 760, color: '#fef3c7', border: '#f59e0b' },
  judgment: { zh: '裁判执行', en: 'Judgment', x: 1260, color: '#dcfce7', border: '#22c55e' },
};

const DOMAIN_ORDER = ['legal_norm', 'legal_subject', 'case_core', 'reasoning', 'judgment'];

const TYPE_DOMAIN_MAP = {
  Law: 'legal_norm',
  LegalProvision: 'legal_norm',
  LegalProvisionVersion: 'legal_norm',
  CaseType: 'legal_norm',
  GuidingCase: 'legal_norm',
  SentencingStandard: 'legal_norm',
  LegalProvisionElement: 'legal_norm',
  Judge: 'legal_subject',
  Attorney: 'legal_subject',
  Clerk: 'legal_subject',
  Prosecutor: 'legal_subject',
  Organization: 'legal_subject',
  Court: 'legal_subject',
  Procuratorate: 'legal_subject',
  LawFirm: 'legal_subject',
  ExpertInstitution: 'legal_subject',
  LegalRole: 'legal_subject',
  CourtCase: 'case_core',
  CaseSummary: 'case_core',
  TrialOrganization: 'case_core',
  ExecutionInfo: 'case_core',
  LegalDocument: 'case_core',
  District: 'case_core',
  CaseParticipant: 'case_core',
  Evidence: 'reasoning',
  Fact: 'reasoning',
  LitigationClaim: 'reasoning',
  ProceduralOpinion: 'reasoning',
  ArgumentPoint: 'reasoning',
  JudicialAssessment: 'reasoning',
  DisputeFocus: 'reasoning',
  JudgmentResult: 'judgment',
};

const BUSINESS_GROUPS = [
  {
    key: 'legal_norm',
    label: '法源规范',
    types: ['Law', 'LegalProvision', 'LegalProvisionVersion', 'CaseType', 'GuidingCase', 'SentencingStandard', 'LegalProvisionElement'],
  },
  {
    key: 'legal_subject',
    label: '主体组织',
    types: ['Judge', 'Attorney', 'Clerk', 'Prosecutor', 'Organization', 'Court', 'Procuratorate', 'LawFirm', 'ExpertInstitution', 'LegalRole'],
  },
  {
    key: 'case_core',
    label: '案件骨架',
    types: ['CourtCase', 'CaseSummary', 'TrialOrganization', 'ExecutionInfo', 'LegalDocument', 'District', 'CaseParticipant'],
  },
  {
    key: 'reasoning',
    label: '事实论证',
    types: ['Evidence', 'Fact', 'LitigationClaim', 'ProceduralOpinion', 'ArgumentPoint', 'JudicialAssessment', 'DisputeFocus'],
  },
  {
    key: 'judgment',
    label: '裁判执行',
    types: ['JudgmentResult'],
  },
];

const CORE_RELATION_TYPES = new Set([
  'typically_applies',
  'belongs_to',
  'has_version',
  'guides_case_type',
  'cites_guiding_case',
  'applies_standard',
  'has_summary',
  'tried_by',
  'undertakes',
  'plays_role',
  'has_jurisdiction_over',
  'prosecutes',
  'signed_by',
  'has_case_type',
  'cites',
  'judgment_cites',
  'submitted_for',
  'proves_fact',
  'has_dispute_focus',
  'has_fact',
  'raises_claim',
  'expresses_opinion',
  'supports_claim',
  'supports_opinion',
  'responds_to_claim',
  'responds_to_opinion',
  'evaluates_argument',
  'based_on_fact',
  'based_on_provision',
  'supports_result',
  'matches_element',
  'resolved_by',
  'leads_to',
  'element_of_provision',
]);

const STEP_TYPE_MAP = {
  证据采信分析: ['Evidence', 'Fact', 'JudicialAssessment'],
  诉求抗辩分析: ['LitigationClaim', 'ProceduralOpinion', 'ArgumentPoint'],
  构成要件分析: ['Fact', 'LegalProvisionElement'],
  法条适用分析: ['DisputeFocus', 'LegalProvision', 'LegalProvisionElement'],
  裁判尺度分析: ['JudgmentResult', 'JudicialAssessment', 'SentencingStandard'],
};

const DISPLAY_TYPES = Array.from(new Set([...TYPE_NAMES, 'LegalProvisionElement', 'Person']));

function shortZhLabel(label = '') {
  return String(label).replace(/（[^）]*）/g, '').trim();
}

function domainOf(type) {
  return TYPE_DOMAIN_MAP[type] || 'case_core';
}

function matchText(type, searchTerm = '') {
  if (!searchTerm) return true;
  const keyword = searchTerm.trim().toLowerCase();
  if (!keyword) return true;
  const zh = shortZhLabel(ZH_LABELS[type] || '');
  const en = EN_DESCRIPTIONS[type] || '';
  return [type, zh, en].some((text) => String(text || '').toLowerCase().includes(keyword));
}

export class OntologyGraph {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.host = document.getElementById('ontologyNetworkHost') || this.container;
    this.detailHost = document.getElementById('ontologyDetailHost');
    this.treeDetailHost = document.getElementById('ontologyTreeDetailHost');
    this.runtimeSourceBadge = document.getElementById('ontologyRuntimeSourceBadge');
    this.runtimeSourceText = document.getElementById('ontologyRuntimeSourceText');
    this.runtimeFooter = document.getElementById('ontologyRuntimeFooterText');
    this.runtimeOpenWorkspaceBtn = document.getElementById('ontologyRuntimeOpenWorkspace');
    this.runtimeOpenWorkspaceButtons = Array.from(document.querySelectorAll('[data-runtime-open-workspace="true"]'));
    this.runtimeHeaderEl = document.querySelector('#ontologySubGraphHost .ontology-runtime-header');
    this.runtimeHintEl = document.querySelector('#ontologySubGraphHost .ontology-runtime-hint');
    this.runtimeFooterEl = document.getElementById('ontologyRuntimeFooter');
    this.runtimeSwitcherPrimaryBtn = document.querySelector('#ontologySubGraphHost .ontology-runtime-switcher [data-runtime-open-workspace="true"]');
    this.runtimeSourceTabs = document.getElementById('ontologyRuntimeSourceTabs');
    this.runtimeSummaryHost = document.getElementById('ontologyRuntimeSummary');
    this.statusText = document.getElementById('ontologyStatusText');
    this.runtimeCanvas = document.getElementById('ontologyRuntimeCanvas');
    this.runtimeView = document.getElementById('ontologyRuntimeView');
    this.caseOverviewView = document.getElementById('ontologyCaseOverviewView');
    this.caseOverviewGrid = document.getElementById('ontologyCaseOverviewGrid');
    this.caseOverviewDetail = document.getElementById('ontologyCaseOverviewDetail');
    this.overviewMappingModeToggle = document.getElementById('ontologyOverviewMappingModeToggle');
    this.caseDeltaView = document.getElementById('ontologyCaseDeltaView');
    this.caseDeltaGrid = document.getElementById('ontologyCaseDeltaGrid');
    this.caseDeltaDetail = document.getElementById('ontologyCaseDeltaDetail');
    this.network = null;
    this.nodesDs = new DataSet();
    this.edgesDs = new DataSet();
    this.languageMode = 'zh';
    this.searchTerm = '';
    this.highlightCase = true;
    this.highlightReasoning = true;
    this.hideUnused = false;
    this.inheritanceMode = 'technical';
    this.lockedType = null;
    this.activeTab = 'ontologyOverviewTab';
    this.runtimeSource = { kind: 'idle', label: '当前来源：暂无运行时子图', footer: '说明：此视图展示的是运行时业务链路，不属于静态本体结构。' };
    this.runtimeEntries = {};
    this.activeRuntimeSourceKind = 'idle';
    this.runtimeViewMode = 'runtime';
    this.overviewMappingMode = 'type';
    this.deltaMappingMode = 'reasoning';
    this.isMinimized = false;
    this.lastWindowMode = 'mini';
    this.lastActiveDiscoverySignature = null;

    this.bindTabEvents();
    this.bindControlEvents();
    this.initOverviewGraph();
    this.bindFloatingEvents();
    this.bindRuntimeMetaEvents();
    this.render(store.getState());
    store.subscribe((state) => this.render(state));
  }

  bindTabEvents() {
    const header = document.getElementById('ontologyHeader');
    if (!header) return;
    header.addEventListener('click', (event) => {
      const tab = event.target.closest('.onto-tab');
      if (!tab) return;
      const targetId = tab.getAttribute('data-target');
      if (!targetId) return;
      this.activeTab = targetId;
      header.querySelectorAll('.onto-tab').forEach((item) => item.classList.toggle('active', item === tab));
      document.querySelectorAll('#ontologyContainer .onto-tab-content').forEach((pane) => {
        pane.classList.toggle('active', pane.id === targetId);
      });
      if (targetId === 'ontologyOverviewTab' && this.network) {
        setTimeout(() => this.network.fit({ animation: true }), 50);
      }
    });
  }

  bindControlEvents() {
    const languageToggle = document.getElementById('ontologyLanguageToggle');
    if (languageToggle) {
      languageToggle.addEventListener('click', (event) => {
        const button = event.target.closest('[data-lang]');
        if (!button) return;
        this.languageMode = button.getAttribute('data-lang') || 'zh';
        languageToggle.querySelectorAll('[data-lang]').forEach((item) => item.classList.toggle('active', item === button));
        this.render(store.getState());
      });
    }

    const searchInput = document.getElementById('ontologySearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (event) => {
        this.searchTerm = event.target.value || '';
        this.render(store.getState());
      });
    }

    const highlightCase = document.getElementById('ontologyHighlightCase');
    if (highlightCase) {
      highlightCase.addEventListener('change', (event) => {
        this.highlightCase = Boolean(event.target.checked);
        this.render(store.getState());
      });
    }

    const highlightReasoning = document.getElementById('ontologyHighlightReasoning');
    if (highlightReasoning) {
      highlightReasoning.addEventListener('change', (event) => {
        this.highlightReasoning = Boolean(event.target.checked);
        this.render(store.getState());
      });
    }

    const hideUnused = document.getElementById('ontologyHideUnused');
    if (hideUnused) {
      hideUnused.addEventListener('change', (event) => {
        this.hideUnused = Boolean(event.target.checked);
        this.render(store.getState());
      });
    }

    const treeModeToggle = document.getElementById('ontologyTreeModeToggle');
    if (treeModeToggle) {
      treeModeToggle.addEventListener('click', (event) => {
        const button = event.target.closest('[data-mode]');
        if (!button) return;
        this.inheritanceMode = button.getAttribute('data-mode') || 'technical';
        treeModeToggle.querySelectorAll('[data-mode]').forEach((item) => item.classList.toggle('active', item === button));
        this.renderInheritance(store.getState());
      });
    }

    const runtimeViewButtons = document.querySelectorAll('[data-runtime-view]');
    runtimeViewButtons.forEach((button) => {
      button.addEventListener('click', () => {
        this.runtimeViewMode = button.getAttribute('data-runtime-view') || 'runtime';
        runtimeViewButtons.forEach((item) => item.classList.toggle('active', item === button));
        this.updateRuntimePanels();
      });
    });

    if (this.overviewMappingModeToggle) {
      this.overviewMappingModeToggle.addEventListener('click', (event) => {
        const button = event.target.closest('[data-overview-mode]');
        if (!button) return;
        this.overviewMappingMode = button.getAttribute('data-overview-mode') || 'type';
        this.overviewMappingModeToggle.querySelectorAll('[data-overview-mode]').forEach((item) => item.classList.toggle('active', item === button));
        this.renderOverviewMapping(store.getState());
      });
    }

    const deltaMappingModeToggle = document.getElementById('ontologyDeltaMappingModeToggle');
    if (deltaMappingModeToggle) {
      deltaMappingModeToggle.addEventListener('click', (event) => {
        const button = event.target.closest('[data-delta-mode]');
        if (!button) return;
        this.deltaMappingMode = button.getAttribute('data-delta-mode') || 'reasoning';
        deltaMappingModeToggle.querySelectorAll('[data-delta-mode]').forEach((item) => item.classList.toggle('active', item === button));
        this.renderDeltaMapping(store.getState());
      });
    }

    this.runtimeOpenWorkspaceButtons.forEach((button) => {
      button.addEventListener('click', () => {
        const suggestedTab = this.runtimeSource.kind === 'retrieval'
          ? 'termSubGraphTabContent'
          : this.runtimeSource.kind === 'discovery'
            ? 'termDiscoveryTabContent'
            : 'termRetrievalTabContent';
        window.dispatchEvent(new CustomEvent('ontology-open-runtime-workspace', {
          detail: {
            kind: this.runtimeSource.kind,
            suggestedTab,
          }
        }));
      });
    });

    const expandAll = document.getElementById('ontologyExpandAll');
    if (expandAll) {
      expandAll.addEventListener('click', () => {
        document.querySelectorAll('#legendBody details').forEach((detail) => {
          detail.open = true;
        });
      });
    }

    const collapseAll = document.getElementById('ontologyCollapseAll');
    if (collapseAll) {
      collapseAll.addEventListener('click', () => {
        document.querySelectorAll('#legendBody details').forEach((detail) => {
          detail.open = false;
        });
      });
    }

    const legendBody = document.getElementById('legendBody');
    if (legendBody) {
      legendBody.addEventListener('click', (event) => {
        const typeTarget = event.target.closest('[data-type]');
        if (!typeTarget) return;
        const type = typeTarget.getAttribute('data-type');
        if (!type) return;
        this.lockedType = this.lockedType === type ? null : type;
        if (this.lockedType) {
          store.setState({
            selectedNodeId: this.lockedType,
            selectedEdgeId: null,
            selectedGraph: 'ontology',
            ontologySelectionKind: 'type',
            ontologySelectionScope: 'all',
            hoverOntologyDomain: null,
            isPanelOpen: true,
          });
        }
        this.render(store.getState());
      });
    }
  }

  bindRuntimeMetaEvents() {
    window.addEventListener('ontology-runtime-meta', (event) => {
      const detail = event.detail || {};
      const sourceType = detail.type || 'idle';
      const label = detail.label || '当前来源：暂无运行时子图';
      const footer = detail.footer || '说明：此视图展示的是运行时业务链路，不属于静态本体结构。';
      const entry = {
        kind: sourceType,
        label,
        footer,
        nodeCount: detail.nodeCount || 0,
        edgeCount: detail.edgeCount || 0,
        workspaceTarget: detail.workspaceTarget || (sourceType === 'retrieval' ? 'termSubGraphTabContent' : sourceType === 'discovery' ? 'termDiscoveryTabContent' : 'termRetrievalTabContent'),
        summary: detail.summary || '',
        updatedAt: Date.now(),
      };
      if (sourceType === 'idle') {
        this.runtimeSource = entry;
        if (!Object.keys(this.runtimeEntries).length) {
          this.activeRuntimeSourceKind = 'idle';
        }
      } else {
        this.runtimeEntries[sourceType] = entry;
        this.runtimeSource = entry;
        this.activeRuntimeSourceKind = sourceType;
      }
      this.renderRuntimeSourceTabs();
      this.renderRuntimeSummary();
      this.syncRuntimeMetaUi(this.getActiveRuntimeEntry());
    });

    window.addEventListener('ontology-runtime-select', (event) => {
      const kind = event.detail?.kind || 'idle';
      if (kind !== 'idle' && this.runtimeEntries[kind]) {
        this.activeRuntimeSourceKind = kind;
      }
      this.renderRuntimeSourceTabs();
      this.renderRuntimeSummary();
      this.syncRuntimeMetaUi(this.getActiveRuntimeEntry());
    });
  }

  getRuntimeKindLabel(kind) {
    if (kind === 'retrieval') return '检索链路';
    if (kind === 'discovery') return '知识发现';
    return '过渡中';
  }

  getActiveRuntimeEntry() {
    if (this.activeRuntimeSourceKind !== 'idle' && this.runtimeEntries[this.activeRuntimeSourceKind]) {
      return this.runtimeEntries[this.activeRuntimeSourceKind];
    }
    return this.runtimeSource;
  }

  syncRuntimeMetaUi(entry = this.getActiveRuntimeEntry()) {
    const sourceType = entry?.kind || 'idle';
    if (this.runtimeSourceBadge) {
      this.runtimeSourceBadge.className = `ontology-runtime-badge is-${sourceType}`;
      this.runtimeSourceBadge.textContent = this.getRuntimeKindLabel(sourceType);
    }
    if (this.runtimeSourceText) this.runtimeSourceText.textContent = entry?.label || '当前来源：暂无运行时子图';
    if (this.runtimeFooter) this.runtimeFooter.textContent = entry?.footer || '说明：此视图展示的是运行时业务链路，不属于静态本体结构。';
    this.runtimeOpenWorkspaceButtons.forEach((button) => {
      button.textContent = sourceType === 'retrieval'
        ? '在主工作区查看检索子图'
        : sourceType === 'discovery'
          ? '在主工作区查看知识发现'
          : '前往主工作区';
    });
  }

  renderRuntimeSourceTabs() {
    if (!this.runtimeSourceTabs) return;
    const entries = ['retrieval', 'discovery']
      .filter((kind) => this.runtimeEntries[kind])
      .map((kind) => this.runtimeEntries[kind]);
    if (!entries.length) {
      this.runtimeSourceTabs.innerHTML = '<span class="ontology-runtime-empty-desc">当前没有可切换的动态图来源</span>';
      return;
    }
    this.runtimeSourceTabs.innerHTML = entries.map((entry) => `
      <button class="ontology-runtime-source-chip ${this.activeRuntimeSourceKind === entry.kind ? 'active' : ''}" data-runtime-source-kind="${entry.kind}">
        ${this.getRuntimeKindLabel(entry.kind)}
      </button>
    `).join('');
    this.runtimeSourceTabs.querySelectorAll('[data-runtime-source-kind]').forEach((button) => {
      button.addEventListener('click', () => {
        const kind = button.getAttribute('data-runtime-source-kind');
        if (!kind) return;
        this.activeRuntimeSourceKind = kind;
        this.renderRuntimeSourceTabs();
        this.renderRuntimeSummary();
        this.syncRuntimeMetaUi(this.getActiveRuntimeEntry());
        window.dispatchEvent(new CustomEvent('ontology-runtime-select', { detail: { kind } }));
      });
    });
  }

  renderRuntimeSummary() {
    if (!this.runtimeSummaryHost) return;
    const entry = this.getActiveRuntimeEntry();
    if (!entry || entry.kind === 'idle') {
      this.runtimeSummaryHost.innerHTML = `
        <div class="ontology-runtime-summary-card">
          <div class="ontology-runtime-summary-title">统一动态图容器</div>
          <div class="ontology-runtime-summary-subtitle">这里会统一承接检索链路、知识发现等运行时图谱。当前暂无可展示来源。</div>
          <div class="ontology-runtime-summary-item">当检索资产或知识发现生成子图后，可在这里切换来源、查看摘要，并快速跳回主工作区。</div>
        </div>
      `;
      return;
    }
    this.runtimeSummaryHost.innerHTML = `
      <div class="ontology-runtime-summary-card">
        <div>
          <div class="ontology-runtime-summary-title">${this.getRuntimeKindLabel(entry.kind)}</div>
          <div class="ontology-runtime-summary-subtitle">${entry.label || '当前运行时来源'}</div>
        </div>
        <div class="ontology-runtime-summary-list">
          <div class="ontology-runtime-summary-item">节点数：${entry.nodeCount || 0}</div>
          <div class="ontology-runtime-summary-item">边数：${entry.edgeCount || 0}</div>
          <div class="ontology-runtime-summary-item">工作区目标：${entry.kind === 'retrieval' ? '检索链路' : entry.kind === 'discovery' ? '知识发现' : '主工作区'}</div>
          <div class="ontology-runtime-summary-item">${entry.summary || entry.footer || '当前来源暂无额外摘要。'}</div>
        </div>
        <div class="ontology-runtime-summary-actions">
          <button class="ontology-primary-btn" data-runtime-open-workspace="true">在主工作区查看</button>
          <button class="ontology-runtime-view-btn" data-runtime-switch-to-mapping="true">切换到全案映射</button>
        </div>
      </div>
    `;
    this.runtimeSummaryHost.querySelectorAll('[data-runtime-open-workspace="true"]').forEach((button) => {
      button.addEventListener('click', () => {
        const activeEntry = this.getActiveRuntimeEntry();
        window.dispatchEvent(new CustomEvent('ontology-open-runtime-workspace', {
          detail: {
            kind: activeEntry?.kind || 'idle',
            suggestedTab: activeEntry?.workspaceTarget || 'termRetrievalTabContent',
          }
        }));
      });
    });
    this.runtimeSummaryHost.querySelectorAll('[data-runtime-switch-to-mapping="true"]').forEach((button) => {
      button.addEventListener('click', () => {
        this.runtimeViewMode = 'overview';
        document.querySelectorAll('[data-runtime-view]').forEach((item) => {
          item.classList.toggle('active', item.getAttribute('data-runtime-view') === 'overview');
        });
        this.updateRuntimePanels();
      });
    });
  }

  getPreferredAnalysisModeByType(type) {
    if (['Evidence', 'Fact', 'JudicialAssessment'].includes(type)) {
      return { mode: 'evidence_chain', label: '证据链路' };
    }
    if (['DisputeFocus', 'LegalProvision', 'LegalProvisionElement', 'JudgmentResult', 'SentencingStandard'].includes(type)) {
      return { mode: 'judgment_basis', label: '裁判依据' };
    }
    return { mode: 'overview', label: '全貌总览' };
  }

  applyCaseMappingSelection(type, scope = 'all') {
    if (!type) return;
    const preferredMode = this.getPreferredAnalysisModeByType(type);
    this.lockedType = type;
    store.setState({
      selectedNodeId: type,
      selectedEdgeId: null,
      selectedGraph: 'ontology',
      ontologySelectionKind: 'type',
      ontologySelectionScope: scope,
      hoverOntologyDomain: null,
      locateTarget: {
        typeKey: type,
        nodeType: type,
        sourceGraph: 'parse',
        timestamp: Date.now()
      },
      workspaceLayoutMode: store.getState().isParseResultAvailable ? 'parse_primary' : store.getState().workspaceLayoutMode,
      isPanelOpen: true,
    });
    window.dispatchEvent(new CustomEvent('parse-analysis-mode-request', {
      detail: {
        mode: preferredMode.mode,
        typeKey: type,
        scope,
      }
    }));
  }

  applyDomainMappingSelection(domainKey) {
    if (!domainKey) return;
    this.lockedType = null;
    store.setState({
      selectedNodeId: domainKey,
      selectedEdgeId: null,
      selectedGraph: 'ontology',
      ontologySelectionKind: 'domain',
      ontologySelectionScope: 'all',
      hoverOntologyType: null,
      isPanelOpen: true,
    });
  }

  initOverviewGraph() {
    if (!this.host) return;
    this.network = new Network(this.host, { nodes: this.nodesDs, edges: this.edgesDs }, {
      physics: false,
      interaction: {
        hover: true,
        dragView: true,
        zoomView: true,
        navigationButtons: true,
        keyboard: true,
      },
      edges: {
        arrows: { to: { enabled: true, scaleFactor: 0.5 } },
        smooth: { type: 'cubicBezier', roundness: 0.12 },
      },
      nodes: {
        font: {
          multi: 'md',
          size: 12,
          face: 'Microsoft YaHei, PingFang SC, Helvetica Neue, Arial, sans-serif',
        },
      },
    });

    bindCustomPan(this.network, this.host);

    this.network.on('click', (params) => {
      if (!params.nodes.length) {
        this.lockedType = null;
        this.network.unselectAll();
        this.render(store.getState());
        return;
      }
      const nodeId = params.nodes[0];
      if (String(nodeId).startsWith('domain:')) {
        return;
      }
      this.lockedType = this.lockedType === nodeId ? null : nodeId;
      store.setState({
        selectedNodeId: this.lockedType,
        selectedEdgeId: null,
        selectedGraph: this.lockedType ? 'ontology' : null,
        ontologySelectionKind: 'type',
        ontologySelectionScope: this.lockedType ? 'all' : null,
        hoverOntologyDomain: null,
        isPanelOpen: Boolean(this.lockedType),
      });
      this.render(store.getState());
    });

    this.network.on('hoverNode', (params) => {
      if (!params?.node || String(params.node).startsWith('domain:')) return;
      store.setState({ hoverOntologyType: params.node, hoverOntologyDomain: null });
    });

    this.network.on('blurNode', () => {
      store.setState({ hoverOntologyType: null });
    });
  }

  getTypeCounts(state) {
    const counts = {};
    (state.parseGraphData?.nodes || []).forEach((node) => {
      const type = node.nodeType || node.group;
      if (!type || String(type).startsWith('Aggregate')) return;
      counts[type] = (counts[type] || 0) + 1;
    });
    return counts;
  }

  subtreeMatches(type) {
    if (matchText(type, this.searchTerm)) return true;
    return Object.keys(ENTITY_DATA).some((child) => ENTITY_DATA[child]?.is_a === type && this.subtreeMatches(child));
  }

  getReasoningTypeSet(state) {
    const history = state.discoveryHistory || [];
    const activeIdx = typeof state.activeDiscoveryIdx === 'number' && state.activeDiscoveryIdx >= 0
      ? state.activeDiscoveryIdx
      : history.length - 1;
    const record = history[activeIdx];
    const result = new Set();
    (record?.result?.knowledge_discovery?.new_nodes || []).forEach((node) => {
      const type = node.type || node.nodeType || node.group;
      if (type) result.add(type);
    });
    (STEP_TYPE_MAP[record?.type] || []).forEach((type) => result.add(type));
    return result;
  }

  getActiveOntologyType(state) {
    if (this.lockedType) return this.lockedType;
    if (state.selectedGraph === 'parse' && state.parseNodeData) {
      return state.parseNodeData.nodeType || state.parseNodeData.group || null;
    }
    if (
      state.selectedGraph === 'ontology'
      && state.ontologySelectionKind !== 'domain'
      && state.selectedNodeId
      && ENTITY_DATA[state.selectedNodeId]
      && !String(state.selectedNodeId).startsWith('domain:')
    ) {
      return state.selectedNodeId;
    }
    return state.hoverOntologyType || null;
  }

  getDisplayText(type) {
    const zh = shortZhLabel(ZH_LABELS[type] || type);
    const en = type;
    if (this.languageMode === 'en') return en;
    if (this.languageMode === 'bilingual') return `${zh}\n${en}`;
    return zh;
  }

  getTypeTone(type) {
    return ENTITY_STYLES[type] || { shape: 'box', color: '#f8fafc', border: '#cbd5e1', fontColor: '#0f172a', size: 18 };
  }

  buildOverviewData(state) {
    const typeCounts = this.getTypeCounts(state);
    const reasoningTypes = this.getReasoningTypeSet(state);
    const activeType = this.getActiveOntologyType(state);
    const visibleTypes = DISPLAY_TYPES.filter((type) => {
      if (this.hideUnused && !typeCounts[type] && !reasoningTypes.has(type) && type !== activeType && !matchText(type, this.searchTerm)) {
        return false;
      }
      return true;
    });

    const domainNodes = DOMAIN_ORDER.map((key) => {
      const meta = DOMAIN_META[key];
      const domainTypes = visibleTypes.filter((type) => domainOf(type) === key);
      return {
        id: `domain:${key}`,
        label: this.languageMode === 'en' ? meta.en : this.languageMode === 'bilingual' ? `${meta.zh}\n${meta.en}` : meta.zh,
        shape: 'box',
        color: { background: meta.color, border: meta.border },
        borderWidth: 2.2,
        font: { color: '#0f172a', size: 17, bold: true, multi: 'md' },
        x: meta.x,
        y: 56,
        fixed: true,
        shadow: { enabled: true, color: 'rgba(15,23,42,0.08)', size: 10, x: 0, y: 3 },
        margin: { top: 12, right: 16, bottom: 12, left: 16 },
        title: `${meta.zh} (${domainTypes.length})`,
      };
    });

    const typeNodes = visibleTypes.map((type) => {
      const domainKey = domainOf(type);
      const indexInDomain = visibleTypes.filter((item) => domainOf(item) === domainKey).indexOf(type);
      const style = this.getTypeTone(type);
      const count = typeCounts[type] || 0;
      const isCaseActive = count > 0;
      const isReasoningActive = reasoningTypes.has(type);
      const isMatch = matchText(type, this.searchTerm);
      const shouldDim = (
        (this.highlightCase && Object.keys(typeCounts).length > 0 && !isCaseActive)
        && (this.highlightReasoning && reasoningTypes.size > 0 && !isReasoningActive)
        && !isMatch
        && type !== activeType
      );
      const rowSize = 6;
      const row = indexInDomain % rowSize;
      const col = Math.floor(indexInDomain / rowSize);
      const x = DOMAIN_META[domainKey].x + (col - 0.5) * 160;
      const y = 180 + row * 66;
      const labelBase = this.getDisplayText(type);
      const label = count > 0 && this.languageMode !== 'en' ? `${labelBase}\n[${count}]` : (count > 0 ? `${labelBase}\n[${count}]` : labelBase);
      const background = shouldDim ? 'rgba(241,245,249,0.45)' : style.color;
      const border = type === activeType ? '#2563eb' : (shouldDim ? 'rgba(203,213,225,0.6)' : style.border);
      const fontColor = shouldDim ? '#94a3b8' : (style.fontColor || '#0f172a');
      return {
        id: type,
        label,
        title: `${shortZhLabel(ZH_LABELS[type] || type)} (${type})`,
        x,
        y,
        fixed: true,
        nodeType: type,
        shape: type === 'LegalProvision' ? 'hexagon' : (style.shape || 'box'),
        size: style.size || 18,
        color: { background, border },
        font: { color: fontColor, size: this.languageMode === 'bilingual' ? 11 : 12, multi: 'md', strokeWidth: 2, strokeColor: '#ffffff' },
        borderWidth: type === activeType ? 3.5 : (isReasoningActive ? 2.8 : 2),
        opacity: shouldDim ? 0.36 : 1,
        shadow: type === activeType
          ? { enabled: true, color: 'rgba(37,99,235,0.28)', size: 18, x: 0, y: 4 }
          : isReasoningActive
            ? { enabled: true, color: 'rgba(245,158,11,0.18)', size: 12, x: 0, y: 3 }
            : { enabled: false },
      };
    });

    const domainEdges = visibleTypes.map((type, index) => ({
      id: `domain_link_${type}_${index}`,
      from: `domain:${domainOf(type)}`,
      to: type,
      dashes: [6, 4],
      color: { color: 'rgba(148,163,184,0.35)', highlight: 'rgba(148,163,184,0.5)' },
      width: 1,
      arrows: '',
      label: '',
      smooth: { type: 'straightCross', roundness: 0.1 },
    }));

    const relationEdges = getOntologyRelationEdges()
      .filter((edge) => CORE_RELATION_TYPES.has(edge.relationType))
      .filter((edge) => visibleTypes.includes(edge.fromType) && visibleTypes.includes(edge.toType))
      .map((edge) => {
        const touchesFocus = activeType && (edge.fromType === activeType || edge.toType === activeType);
        const touchesReasoning = reasoningTypes.has(edge.fromType) || reasoningTypes.has(edge.toType);
        const isMatch = matchText(edge.fromType, this.searchTerm) || matchText(edge.toType, this.searchTerm);
        const dim = !touchesFocus && !touchesReasoning && !isMatch && activeType;
        return {
          id: edge.id,
          from: edge.fromType,
          to: edge.toType,
          label: touchesFocus ? (RELATION_LABELS[edge.relationType] || edge.label || edge.relationType) : '',
          arrows: 'to',
          dashes: edge.source === 'derived' ? [6, 4] : false,
          color: edge.source === 'derived'
            ? { color: dim ? 'rgba(99,102,241,0.18)' : '#6366f1', highlight: '#4338ca' }
            : { color: dim ? 'rgba(148,163,184,0.18)' : 'rgba(148,163,184,0.75)', highlight: '#475569' },
          width: touchesFocus ? 2.4 : (touchesReasoning ? 2 : 1.2),
          font: {
            size: 10,
            color: touchesFocus ? '#334155' : 'rgba(100,116,139,0.0)',
            align: 'horizontal',
            strokeWidth: touchesFocus ? 2 : 0,
            strokeColor: '#ffffff',
          },
          smooth: { type: 'curvedCW', roundness: domainOf(edge.fromType) === domainOf(edge.toType) ? 0.08 : 0.16 },
          title: `${RELATION_LABELS[edge.relationType] || edge.relationType}: ${edge.fromType} -> ${edge.toType}`,
        };
      });

    return { nodes: [...domainNodes, ...typeNodes], edges: [...domainEdges, ...relationEdges], typeCounts, reasoningTypes, activeType };
  }

  renderOverview(state) {
    const graph = this.buildOverviewData(state);
    this.nodesDs.clear();
    this.edgesDs.clear();
    this.nodesDs.add(graph.nodes);
    this.edgesDs.add(graph.edges);
    if (graph.activeType && this.nodesDs.get(graph.activeType)) {
      this.network.selectNodes([graph.activeType], false);
    } else {
      this.network.unselectAll();
    }
    this.renderTypeDetail(this.detailHost, graph.activeType, graph.typeCounts, graph.reasoningTypes);
  }

  renderTypeDetail(host, type, typeCounts, reasoningTypes) {
    if (!host) return;
    if (!type || !ENTITY_DATA[type]) {
      host.innerHTML = `
        <div class="ontology-empty-state">
          点击本体类型后，这里会展示该类型的中文说明、所属业务域、关键字段、当前案件实例数，以及与链式思考的联动状态。
        </div>
      `;
      return;
    }
    const entity = ENTITY_DATA[type] || {};
    const parent = entity.is_a || '无';
    const children = Object.keys(ENTITY_DATA).filter((key) => ENTITY_DATA[key]?.is_a === type);
    const relations = getOntologyRelationEdges()
      .filter((edge) => edge.fromType === type || edge.toType === type)
      .slice(0, 8)
      .map((edge) => `${RELATION_LABELS[edge.relationType] || edge.relationType} · ${edge.fromType} -> ${edge.toType}`);
    const count = typeCounts[type] || 0;
    const reasoningActive = reasoningTypes.has(type);
    host.innerHTML = `
      <div class="ontology-side-card">
        <div>
          <div class="ontology-side-title">${shortZhLabel(ZH_LABELS[type] || type)}</div>
          <div class="ontology-side-subtitle">${type} · ${EN_DESCRIPTIONS[type] || ''}</div>
        </div>
        <div class="ontology-stat-grid">
          <div class="ontology-stat-card">
            <div class="ontology-stat-label">当前案件实例数</div>
            <div class="ontology-stat-value">${count}</div>
          </div>
          <div class="ontology-stat-card">
            <div class="ontology-stat-label">推理状态</div>
            <div class="ontology-stat-value">${reasoningActive ? '命中' : '未命中'}</div>
          </div>
        </div>
        <div>
          <div class="ontology-section-title">结构信息</div>
          <div class="ontology-chip-row">
            <span class="ontology-chip">业务域：${DOMAIN_META[domainOf(type)]?.zh || '未分类'}</span>
            <span class="ontology-chip">父类：${parent}</span>
            <span class="ontology-chip">子类：${children.length}</span>
          </div>
        </div>
        <div>
          <div class="ontology-section-title">类型说明</div>
          <div class="ontology-meta-list">
            <div>${entity.description || '暂无说明'}</div>
          </div>
        </div>
        <div>
          <div class="ontology-section-title">核心字段</div>
          <div class="ontology-meta-list">
            <div>必填：${(entity.required || []).slice(0, 6).join('、') || '无'}</div>
            <div>可选：${(entity.optional || []).slice(0, 6).join('、') || '无'}</div>
          </div>
        </div>
        <div>
          <div class="ontology-section-title">关键关系</div>
          <div class="ontology-meta-list">${relations.length ? relations.map((item) => `<div>${item}</div>`).join('') : '<div>暂无关系</div>'}</div>
        </div>
      </div>
    `;
  }

  buildTechnicalTreeNode(type, state, typeCounts, reasoningTypes) {
    const children = Object.keys(ENTITY_DATA).filter((key) => ENTITY_DATA[key]?.is_a === type);
    const hasChildren = children.length > 0;
    const activeType = this.getActiveOntologyType(state);
    const count = typeCounts[type] || 0;
    const badges = [
      count > 0 ? `<span class="ontology-tree-badge">案件 ${count}</span>` : '',
      reasoningTypes.has(type) ? `<span class="ontology-tree-badge">推理中</span>` : '',
    ].filter(Boolean).join('');
    const marker = this.getTypeTone(type);
    const titleHtml = `
      <span class="ontology-tree-marker" style="background:${marker.color || '#f8fafc'};border-color:${marker.border || '#cbd5e1'};"></span>
      <span class="ontology-tree-content" data-type="${type}">
        <div class="ontology-tree-title">${shortZhLabel(ZH_LABELS[type] || type)}</div>
        <div class="ontology-tree-subtitle">${type}</div>
        ${badges ? `<div class="ontology-tree-badges">${badges}</div>` : ''}
      </span>
    `;
    if (!hasChildren) {
      return `<div class="ontology-tree-leaf ${activeType === type ? 'is-active' : ''}" data-type="${type}">${titleHtml}</div>`;
    }
    const childMarkup = children.map((child) => this.buildTechnicalTreeNode(child, state, typeCounts, reasoningTypes)).join('');
    return `
      <details class="ontology-tree-node ${activeType === type ? 'is-active' : ''}" open>
        <summary data-type="${type}">${titleHtml}</summary>
        <div class="ontology-tree-children">${childMarkup}</div>
      </details>
    `;
  }

  buildBusinessTree(state, typeCounts, reasoningTypes) {
    const activeType = this.getActiveOntologyType(state);
    return BUSINESS_GROUPS.map((group) => {
      const items = group.types
        .filter((type) => ENTITY_DATA[type])
        .filter((type) => !this.searchTerm || matchText(type, this.searchTerm))
        .map((type) => this.buildTechnicalTreeNode(type, state, typeCounts, reasoningTypes))
        .join('');
      if (!items) return '';
      const badge = group.types.reduce((sum, type) => sum + (typeCounts[type] || 0), 0);
      return `
        <details class="ontology-tree-group ${group.types.includes(activeType) ? 'is-active' : ''}" open>
          <summary>
            <span class="ontology-tree-marker" style="background:${DOMAIN_META[group.key]?.color || '#f8fafc'};border-color:${DOMAIN_META[group.key]?.border || '#cbd5e1'};"></span>
            <span class="ontology-tree-content">
              <div class="ontology-tree-title">${group.label}</div>
              <div class="ontology-tree-subtitle">${group.types.length} 类 · 当前案件 ${badge}</div>
            </span>
          </summary>
          <div class="ontology-tree-children">${items}</div>
        </details>
      `;
    }).join('');
  }

  renderInheritance(state) {
    const legendBody = document.getElementById('legendBody');
    if (!legendBody) return;
    const typeCounts = this.getTypeCounts(state);
    const reasoningTypes = this.getReasoningTypeSet(state);
    let html = '';
    if (this.inheritanceMode === 'business') {
      html = this.buildBusinessTree(state, typeCounts, reasoningTypes);
    } else {
      const roots = Object.keys(ENTITY_DATA).filter((key) => !ENTITY_DATA[key]?.is_a);
      html = roots
        .filter((type) => !this.searchTerm || this.subtreeMatches(type))
        .map((type) => this.buildTechnicalTreeNode(type, state, typeCounts, reasoningTypes))
        .join('');
    }
    legendBody.innerHTML = `<div class="ontology-tree-list">${html || '<div class="ontology-empty-state">没有匹配到本体类型，请尝试其他关键字。</div>'}</div>`;
    this.renderTypeDetail(this.treeDetailHost, this.getActiveOntologyType(state), typeCounts, reasoningTypes);
  }

  renderStatus(state) {
    if (!this.statusText) return;
    const typeCounts = this.getTypeCounts(state);
    const covered = Object.keys(typeCounts).filter((key) => typeCounts[key] > 0).length;
    const history = state.discoveryHistory || [];
    const activeIdx = typeof state.activeDiscoveryIdx === 'number' && state.activeDiscoveryIdx >= 0 ? state.activeDiscoveryIdx : history.length - 1;
    const activeStep = history[activeIdx]?.type || '无';
    this.statusText.textContent = `当前案件覆盖 ${covered} 类本体类型 · 当前推理步骤：${activeStep}`;
  }

  getDiscoveryContext(state) {
    const history = state.discoveryHistory || [];
    const activeIdx = typeof state.activeDiscoveryIdx === 'number' && state.activeDiscoveryIdx >= 0 ? state.activeDiscoveryIdx : history.length - 1;
    const activeRecord = history[activeIdx] || null;
    const activeStep = activeRecord?.type || '无';
    return { history, activeIdx, activeRecord, activeStep };
  }

  getVersionDeltaStats(state) {
    const stats = {};
    const { history } = this.getDiscoveryContext(state);
    history.forEach((record) => {
      (record?.result?.knowledge_discovery?.new_nodes || []).forEach((node) => {
        const type = node.type || node.nodeType || node.group;
        if (!type) return;
        if (!stats[type]) stats[type] = { added: 0, updated: 0, total: 0, discoveryAdded: 0, mergeAdded: 0, mergeUpdated: 0 };
        stats[type].added += 1;
        stats[type].discoveryAdded += 1;
        stats[type].total += 1;
      });
    });
    const nodeTypeById = new Map((state.parseGraphData?.nodes || []).map((node) => [String(node.id), node.nodeType || node.group]));
    const highlight = state.parseEnhancementPreviewActive && state.parseEnhancementPreviewPatch
      ? state.parseEnhancementPreviewPatch
      : state.parseMergeHighlight;
    (highlight?.addedNodeIds || []).forEach((id) => {
      const type = nodeTypeById.get(String(id));
      if (!type) return;
      if (!stats[type]) stats[type] = { added: 0, updated: 0, total: 0, discoveryAdded: 0, mergeAdded: 0, mergeUpdated: 0 };
      stats[type].added += 1;
      stats[type].mergeAdded += 1;
      stats[type].total += 1;
    });
    (highlight?.updatedNodeIds || []).forEach((id) => {
      const type = nodeTypeById.get(String(id));
      if (!type) return;
      if (!stats[type]) stats[type] = { added: 0, updated: 0, total: 0, discoveryAdded: 0, mergeAdded: 0, mergeUpdated: 0 };
      stats[type].updated += 1;
      stats[type].mergeUpdated += 1;
      stats[type].total += 1;
    });
    return stats;
  }

  buildMappingBaseItems(state) {
    const typeCounts = this.getTypeCounts(state);
    const reasoningTypes = this.getReasoningTypeSet(state);
    const versionDeltaStats = this.getVersionDeltaStats(state);
    const { activeRecord, activeStep } = this.getDiscoveryContext(state);
    const stepDeltaCounts = {};
    (activeRecord?.result?.knowledge_discovery?.new_nodes || []).forEach((node) => {
      const type = node.type || node.nodeType || node.group;
      if (!type) return;
      stepDeltaCounts[type] = (stepDeltaCounts[type] || 0) + 1;
    });

    return DISPLAY_TYPES
      .filter((type) => ENTITY_DATA[type])
      .filter((type) => !this.searchTerm || matchText(type, this.searchTerm))
      .map((type) => ({
        type,
        zh: shortZhLabel(ZH_LABELS[type] || type),
        en: type,
        domain: DOMAIN_META[domainOf(type)]?.zh || '未分类',
        domainKey: domainOf(type),
        count: typeCounts[type] || 0,
        reasoning: reasoningTypes.has(type),
        stepDelta: stepDeltaCounts[type] || 0,
        versionAdded: versionDeltaStats[type]?.added || 0,
        versionUpdated: versionDeltaStats[type]?.updated || 0,
        versionDelta: versionDeltaStats[type]?.total || 0,
        discoveryAdded: versionDeltaStats[type]?.discoveryAdded || 0,
        mergeAdded: versionDeltaStats[type]?.mergeAdded || 0,
        mergeUpdated: versionDeltaStats[type]?.mergeUpdated || 0,
        activeStep,
      }));
  }

  buildOverviewItems(state) {
    return this.buildMappingBaseItems(state)
      .filter((item) => !this.hideUnused || item.count > 0)
      .sort((a, b) => b.count - a.count || Number(b.reasoning) - Number(a.reasoning) || b.versionDelta - a.versionDelta);
  }

  buildOverviewDomainItems(state) {
    const items = this.buildMappingBaseItems(state);
    const domainMap = new Map();
    DOMAIN_ORDER.forEach((key) => {
      domainMap.set(key, {
        domainKey: key,
        domain: DOMAIN_META[key]?.zh || key,
        en: DOMAIN_META[key]?.en || key,
        count: 0,
        coveredTypes: 0,
        reasoningTypes: 0,
        versionDelta: 0,
      });
    });
    items.forEach((item) => {
      const bucket = domainMap.get(item.domainKey);
      if (!bucket) return;
      bucket.count += item.count;
      bucket.versionDelta += item.versionDelta;
      if (item.count > 0) bucket.coveredTypes += 1;
      if (item.reasoning || item.stepDelta > 0) bucket.reasoningTypes += 1;
    });
    return Array.from(domainMap.values())
      .filter((item) => !this.hideUnused || item.count > 0 || item.reasoningTypes > 0)
      .sort((a, b) => b.count - a.count || b.reasoningTypes - a.reasoningTypes || b.versionDelta - a.versionDelta);
  }

  getDomainTypeItems(domainKey, state = store.getState()) {
    return this.buildMappingBaseItems(state)
      .filter((item) => item.domainKey === domainKey)
      .filter((item) => !this.hideUnused || item.count > 0 || item.reasoning || item.versionDelta > 0)
      .sort((a, b) => b.count - a.count || b.versionDelta - a.versionDelta || Number(b.reasoning) - Number(a.reasoning));
  }

  buildDeltaItems(state) {
    const items = this.buildMappingBaseItems(state);
    if (this.deltaMappingMode === 'version') {
      return items
        .filter((item) => item.versionDelta > 0)
        .sort((a, b) => b.versionDelta - a.versionDelta || b.count - a.count);
    }
    return items
      .filter((item) => item.reasoning || item.stepDelta > 0)
      .sort((a, b) => b.stepDelta - a.stepDelta || Number(b.reasoning) - Number(a.reasoning) || b.versionDelta - a.versionDelta || b.count - a.count);
  }

  bindMappingCardInteractions(host, { scope = 'all', activeType = null } = {}) {
    if (!host) return;
    host.querySelectorAll('[data-map-type]').forEach((card) => {
      const mapType = card.getAttribute('data-map-type');
      if (!mapType) return;
      card.addEventListener('mouseenter', () => {
        card.classList.add('is-preview');
        store.setState({ hoverOntologyType: mapType });
      });
      card.addEventListener('mouseleave', () => {
        card.classList.remove('is-preview');
        if (store.getState().hoverOntologyType === mapType) {
          store.setState({ hoverOntologyType: null });
        }
      });
      card.addEventListener('click', () => {
        this.applyCaseMappingSelection(mapType, scope);
        this.render(store.getState());
      });
      card.classList.toggle('is-active', activeType === mapType);
    });
  }

  bindDomainCardInteractions(host, { activeDomain = null } = {}) {
    if (!host) return;
    host.querySelectorAll('[data-map-domain]').forEach((card) => {
      const domainKey = card.getAttribute('data-map-domain');
      if (!domainKey) return;
      card.addEventListener('mouseenter', () => {
        card.classList.add('is-preview');
        store.setState({ hoverOntologyType: null, hoverOntologyDomain: domainKey });
      });
      card.addEventListener('mouseleave', () => {
        card.classList.remove('is-preview');
        if (store.getState().hoverOntologyDomain === domainKey) {
          store.setState({ hoverOntologyDomain: null });
        }
      });
      card.addEventListener('click', () => {
        this.applyDomainMappingSelection(domainKey);
        this.render(store.getState());
      });
      card.classList.toggle('is-active', activeDomain === domainKey);
    });
  }

  renderOverviewMapping(state) {
    if (!this.caseOverviewGrid) return;
    if (this.overviewMappingMode === 'domain') {
      const items = this.buildOverviewDomainItems(state);
      const activeDomain = state.selectedGraph === 'ontology' && state.ontologySelectionKind === 'domain'
        ? state.selectedNodeId
        : state.hoverOntologyDomain || null;
      if (!items.length) {
        this.caseOverviewGrid.innerHTML = '<div class="ontology-empty-state">当前还没有可展示的业务域分布，请先完成解析。</div>';
        this.renderMappingDetail(this.caseOverviewDetail, null, { title: '全案映射', emptyText: '业务域热力会按法源规范、主体组织、案件骨架、事实论证、裁判执行五个域汇总当前全案实例。' });
        return;
      }
      this.caseOverviewGrid.innerHTML = items.map((item) => `
        <div class="ontology-map-card ${activeDomain === item.domainKey ? 'is-active' : ''}" data-map-domain="${item.domainKey}">
          <div class="ontology-map-card-title">${item.domain}</div>
          <div class="ontology-map-card-subtitle">${item.en}</div>
          <div class="ontology-map-card-stats">
            <span class="ontology-map-card-pill is-hot">实例 ${item.count}</span>
            <span class="ontology-map-card-pill">${item.coveredTypes} 类命中</span>
          </div>
          <div class="ontology-map-card-subtitle">推理激活类型 ${item.reasoningTypes} · 变更 ${item.versionDelta}</div>
        </div>
      `).join('');
      this.bindDomainCardInteractions(this.caseOverviewGrid, { activeDomain });
      const preferredItem = items.find((item) => item.domainKey === activeDomain) || items[0];
      this.renderMappingDetail(this.caseOverviewDetail, preferredItem, { title: '全案映射', modeLabel: '业务域热力' });
      return;
    }

    const items = this.buildOverviewItems(state);
    const activeType = this.getActiveOntologyType(state);
    const { activeStep } = this.getDiscoveryContext(state);
    if (!items.length) {
      this.caseOverviewGrid.innerHTML = '<div class="ontology-empty-state">当前还没有可展示的全案实例分布，请先完成解析。</div>';
      this.renderMappingDetail(this.caseOverviewDetail, null, { title: '全案映射', emptyText: '全案映射只展示当前案件已经存在的本体实例分布，不受检索链路或知识发现来源切换影响。' });
      return;
    }
    this.caseOverviewGrid.innerHTML = items.map((item) => `
      <div class="ontology-map-card ${activeType === item.type ? 'is-active' : ''}" data-map-type="${item.type}">
        <div class="ontology-map-card-title">${this.languageMode === 'en' ? item.en : item.zh}</div>
        <div class="ontology-map-card-subtitle">${this.languageMode === 'zh' ? item.en : `${item.zh} · ${item.en}`}</div>
        <div class="ontology-map-card-subtitle">业务域：${item.domain}</div>
        <div class="ontology-map-card-stats">
          <span class="ontology-map-card-pill ${item.count > 0 ? 'is-hot' : ''}">实例 ${item.count}</span>
          ${item.reasoning ? `<span class="ontology-map-card-pill is-reasoning">当前步骤：${activeStep}</span>` : '<span class="ontology-map-card-pill">全案静态分布</span>'}
        </div>
      </div>
    `).join('');
    this.bindMappingCardInteractions(this.caseOverviewGrid, { scope: 'all', activeType });
    const preferredItem = items.find((item) => item.type === activeType) || items[0];
    this.renderMappingDetail(this.caseOverviewDetail, preferredItem, { title: '全案映射', modeLabel: '类型热力' });
  }

  renderDeltaMapping(state) {
    if (!this.caseDeltaGrid) return;
    const items = this.buildDeltaItems(state);
    const activeType = this.getActiveOntologyType(state);
    const { activeStep } = this.getDiscoveryContext(state);
    if (!items.length) {
      this.caseDeltaGrid.innerHTML = `<div class="ontology-empty-state">${this.deltaMappingMode === 'version' ? '当前没有可展示的版本变化类型。' : '当前步骤没有可展示的推理增量类型。'}</div>`;
      this.renderMappingDetail(this.caseDeltaDetail, null, {
        title: '增量映射',
        emptyText: this.deltaMappingMode === 'version'
          ? '版本变化只展示近期新增或更新过的本体类型。'
          : '推理映射只展示当前链式思考步骤激活或新增的本体类型。'
      });
      return;
    }
    this.caseDeltaGrid.innerHTML = items.map((item) => `
      <div class="ontology-map-card ${activeType === item.type ? 'is-active' : ''}" data-map-type="${item.type}">
        <div class="ontology-map-card-title">${this.languageMode === 'en' ? item.en : item.zh}</div>
        <div class="ontology-map-card-subtitle">${this.languageMode === 'zh' ? item.en : `${item.zh} · ${item.en}`}</div>
        <div class="ontology-map-card-subtitle">业务域：${item.domain}</div>
        <div class="ontology-map-card-stats">
          ${this.deltaMappingMode === 'version'
            ? `<span class="ontology-map-card-pill is-hot">新增 ${item.versionAdded}</span><span class="ontology-map-card-pill is-update">更新 ${item.versionUpdated}</span>`
            : `<span class="ontology-map-card-pill is-reasoning">步骤新增 ${item.stepDelta}</span><span class="ontology-map-card-pill">当前步骤</span>`}
        </div>
        <div class="ontology-map-card-subtitle">${this.deltaMappingMode === 'version' ? `发现新增 ${item.discoveryAdded} · 版本新增 ${item.mergeAdded} · 版本更新 ${item.mergeUpdated}` : `步骤：${activeStep} · 点击后优先聚焦推理新增实例`}</div>
      </div>
    `).join('');
    this.bindMappingCardInteractions(this.caseDeltaGrid, { scope: this.deltaMappingMode, activeType });
    const preferredItem = items.find((item) => item.type === activeType)
      || (this.deltaMappingMode === 'reasoning' ? items.find((item) => item.reasoning || item.stepDelta > 0) : items.find((item) => item.versionDelta > 0))
      || items[0];
    this.renderMappingDetail(this.caseDeltaDetail, preferredItem, { title: '增量映射', modeLabel: this.deltaMappingMode === 'version' ? '版本变化' : '推理映射' });
  }

  renderMappingDetail(host, item, { title = '映射视图', modeLabel = '', emptyText = '' } = {}) {
    if (!host) return;
    if (!item) {
      host.innerHTML = `<div class="ontology-empty-state">${emptyText || '这里会展示当前映射视图的类型说明和主图联动语义。'}</div>`;
      return;
    }
    if (item.domainKey) {
      const domainTypes = this.getDomainTypeItems(item.domainKey);
      host.innerHTML = `
        <div class="ontology-side-card">
          <div>
            <div class="ontology-side-title">${item.domain}</div>
            <div class="ontology-side-subtitle">${item.en} · 业务域热力</div>
          </div>
          <div class="ontology-stat-grid">
            <div class="ontology-stat-card">
              <div class="ontology-stat-label">全域实例数</div>
              <div class="ontology-stat-value">${item.count}</div>
            </div>
            <div class="ontology-stat-card">
              <div class="ontology-stat-label">命中类型数</div>
              <div class="ontology-stat-value">${item.coveredTypes}</div>
            </div>
          </div>
          <div>
            <div class="ontology-section-title">联动说明</div>
            <div class="ontology-meta-list">
              <div>视图：${title}${modeLabel ? ` · ${modeLabel}` : ''}</div>
              <div>推理激活类型：${item.reasoningTypes}</div>
              <div>近期变更：${item.versionDelta}</div>
              <div>点击后主图会聚焦该业务域下的全部实例。</div>
            </div>
          </div>
          <div>
            <div class="ontology-section-title">域内类型展开</div>
            <div class="ontology-chip-list">
              ${domainTypes.map((typeItem) => `
                <button class="ontology-type-chip" data-domain-type="${typeItem.type}">
                  <span>${this.languageMode === 'en' ? typeItem.en : typeItem.zh}</span>
                  <span class="ontology-type-chip-meta">实例 ${typeItem.count}</span>
                </button>
              `).join('') || '<div class="ontology-empty-state">当前业务域暂无可展开类型。</div>'}
            </div>
          </div>
        </div>
      `;
      host.querySelectorAll('[data-domain-type]').forEach((button) => {
        button.addEventListener('click', () => {
          const type = button.getAttribute('data-domain-type');
          if (!type) return;
          this.overviewMappingMode = 'type';
          if (this.overviewMappingModeToggle) {
            this.overviewMappingModeToggle.querySelectorAll('[data-overview-mode]').forEach((itemEl) => {
              itemEl.classList.toggle('active', itemEl.getAttribute('data-overview-mode') === 'type');
            });
          }
          this.applyCaseMappingSelection(type, 'all');
          this.render(store.getState());
        });
      });
      return;
    }
    const entity = ENTITY_DATA[item.type] || {};
    const preferredMode = this.getPreferredAnalysisModeByType(item.type);
    host.innerHTML = `
      <div class="ontology-side-card">
        <div>
          <div class="ontology-side-title">${item.zh}</div>
          <div class="ontology-side-subtitle">${item.en} · ${item.domain}</div>
        </div>
        <div class="ontology-stat-grid">
          <div class="ontology-stat-card">
            <div class="ontology-stat-label">全案实例数</div>
            <div class="ontology-stat-value">${item.count}</div>
          </div>
          <div class="ontology-stat-card">
            <div class="ontology-stat-label">${modeLabel || title}</div>
            <div class="ontology-stat-value">${this.deltaMappingMode === 'version' && title === '增量映射' ? item.versionDelta : (title === '增量映射' ? item.stepDelta : item.count)}</div>
          </div>
        </div>
        <div>
          <div class="ontology-section-title">联动说明</div>
          <div class="ontology-meta-list">
            <div>视图：${title}${modeLabel ? ` · ${modeLabel}` : ''}</div>
            <div>推理命中：${item.reasoning ? '是' : '否'}</div>
            <div>步骤新增：${item.stepDelta}</div>
            <div>版本新增：${item.versionAdded}</div>
            <div>版本更新：${item.versionUpdated}</div>
            <div>版本增量总计：${item.versionDelta}</div>
            <div>其中：知识发现新增 ${item.discoveryAdded} / 版本新增 ${item.mergeAdded} / 版本更新 ${item.mergeUpdated}</div>
            <div>推荐主图模式：${preferredMode.label}</div>
          </div>
        </div>
        <div>
          <div class="ontology-section-title">类型说明</div>
          <div class="ontology-meta-list">
            <div>${entity.description || '暂无说明'}</div>
          </div>
        </div>
      </div>
    `;
  }

  updateRuntimePanels() {
    if (this.runtimeView) this.runtimeView.classList.toggle('is-hidden', this.runtimeViewMode !== 'runtime');
    if (this.caseOverviewView) this.caseOverviewView.classList.toggle('is-hidden', this.runtimeViewMode !== 'overview');
    if (this.caseDeltaView) this.caseDeltaView.classList.toggle('is-hidden', this.runtimeViewMode !== 'delta');
    if (this.runtimeViewMode === 'runtime') {
      this.renderRuntimeSummary();
      this.syncRuntimeMetaUi(this.getActiveRuntimeEntry());
      if (this.runtimeHeaderEl) this.runtimeHeaderEl.classList.remove('is-mapping-mode');
      if (this.runtimeFooterEl) this.runtimeFooterEl.classList.remove('is-hidden');
      if (this.runtimeSwitcherPrimaryBtn) this.runtimeSwitcherPrimaryBtn.classList.remove('is-hidden');
    } else {
      if (this.runtimeSourceBadge) {
        this.runtimeSourceBadge.className = `ontology-runtime-badge ${this.runtimeViewMode === 'overview' ? 'is-discovery' : 'is-retrieval'}`;
        this.runtimeSourceBadge.textContent = this.runtimeViewMode === 'overview' ? '全案映射' : '增量映射';
      }
      if (this.runtimeSourceText) {
        this.runtimeSourceText.textContent = this.runtimeViewMode === 'overview'
          ? '当前视图：全案静态本体映射，不显示检索链路或知识发现来源切换。'
          : '当前视图：增量本体映射，只展示推理与版本变化带来的类型变化。';
      }
      if (this.runtimeHintEl) {
        this.runtimeHintEl.textContent = this.runtimeViewMode === 'overview'
          ? '当前主内容是热力卡片与详情面板，不显示运行时子图。'
          : '当前主内容是增量类型卡片与详情面板，不显示运行时子图。';
      }
      if (this.runtimeHeaderEl) this.runtimeHeaderEl.classList.add('is-mapping-mode');
      if (this.runtimeFooterEl) this.runtimeFooterEl.classList.add('is-hidden');
      if (this.runtimeSwitcherPrimaryBtn) this.runtimeSwitcherPrimaryBtn.classList.add('is-hidden');
    }
  }

  syncDeltaMappingModeButtons() {
    const host = document.getElementById('ontologyDeltaMappingModeToggle');
    if (!host) return;
    host.querySelectorAll('[data-delta-mode]').forEach((item) => {
      item.classList.toggle('active', item.getAttribute('data-delta-mode') === this.deltaMappingMode);
    });
  }

  render(state) {
    const discoveryHistory = state.discoveryHistory || [];
    const activeIdx = typeof state.activeDiscoveryIdx === 'number' && state.activeDiscoveryIdx >= 0 ? state.activeDiscoveryIdx : discoveryHistory.length - 1;
    const currentStep = discoveryHistory[activeIdx]?.type || '无';
    const discoverySignature = `${activeIdx}:${currentStep}:${discoveryHistory.length}`;
    if (discoverySignature !== this.lastActiveDiscoverySignature) {
      this.lastActiveDiscoverySignature = discoverySignature;
      if (this.runtimeViewMode === 'delta' && currentStep !== '无' && this.deltaMappingMode !== 'version') {
        this.deltaMappingMode = 'reasoning';
        this.syncDeltaMappingModeButtons();
      }
    }
    this.renderOverview(state);
    this.renderInheritance(state);
    this.renderOverviewMapping(state);
    this.renderDeltaMapping(state);
    this.renderStatus(state);
    this.updateRuntimePanels();
  }

  bindFloatingEvents() {
    const ohClose = document.getElementById('ohClose');
    if (ohClose) {
      ohClose.addEventListener('click', () => {
        this.minimizeToDock();
      });
    }

    const ohToggleFull = document.getElementById('ohToggleFull');
    if (ohToggleFull) {
      ohToggleFull.addEventListener('click', () => {
        const isMini = this.container.classList.contains('mini-mode');
        if (isMini) this.setMainMode();
        else this.setMiniMode();
      });
    }

    const minimizedDock = document.getElementById('ontologyMinimizedDock');
    if (minimizedDock) {
      minimizedDock.addEventListener('click', () => {
        this.restoreFromDock();
      });
    }

    const restoreFloat = document.getElementById('ontologyRestoreFloat');
    if (restoreFloat) {
      restoreFloat.addEventListener('click', () => {
        this.setMiniMode();
      });
    }

    const header = document.getElementById('ontologyHeader');
    if (header) {
      let isDragging = false;
      let startX = 0;
      let startY = 0;
      let initialLeft = 0;
      let initialTop = 0;
      header.addEventListener('mousedown', (event) => {
        if (event.target.closest('button, input, label')) return;
        isDragging = true;
        startX = event.clientX;
        startY = event.clientY;
        const rect = this.container.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;

        const onMouseMove = (moveEvent) => {
          if (!isDragging) return;
          this.container.style.left = `${initialLeft + moveEvent.clientX - startX}px`;
          this.container.style.top = `${initialTop + moveEvent.clientY - startY}px`;
        };

        const onMouseUp = () => {
          isDragging = false;
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });
    }
  }

  setMiniMode() {
    this.lastWindowMode = 'mini';
    if (this.isMinimized) {
      this.container.classList.remove('main-mode');
      this.container.classList.add('mini-mode', 'is-minimized');
      return;
    }
    this.isMinimized = false;
    this.container.classList.remove('is-minimized', 'main-mode');
    this.container.classList.add('mini-mode');
    this.container.style.width = '780px';
    this.container.style.height = '640px';
    this.container.style.top = '54px';
    this.container.style.left = '20px';
    this.container.style.zIndex = '998';
    this.container.style.boxShadow = '0 10px 30px rgba(0,0,0,0.3)';
    this.container.style.borderRadius = '8px';
    this.container.style.border = '1px solid #334155';
    this.container.style.overflow = 'hidden';
    this.container.style.backgroundColor = '#ffffff';
    const header = document.getElementById('ontologyHeader');
    if (header) header.style.display = 'flex';
    setTimeout(() => this.network?.fit({ animation: true }), 350);
  }

  setMainMode() {
    this.lastWindowMode = 'main';
    if (this.isMinimized) {
      this.container.classList.remove('mini-mode');
      this.container.classList.add('main-mode', 'is-minimized');
      return;
    }
    this.isMinimized = false;
    this.container.classList.remove('is-minimized', 'mini-mode');
    this.container.classList.add('main-mode');
    this.container.style.width = '100%';
    this.container.style.height = '100vh';
    this.container.style.top = '0';
    this.container.style.left = '0';
    this.container.style.zIndex = '2';
    this.container.style.boxShadow = 'none';
    this.container.style.borderRadius = '0';
    this.container.style.border = 'none';
    this.container.style.backgroundColor = 'transparent';
    const header = document.getElementById('ontologyHeader');
    if (header) header.style.display = 'none';
    setTimeout(() => this.network?.fit({ animation: true }), 350);
  }

  minimizeToDock() {
    this.isMinimized = true;
    this.container.classList.add('is-minimized');
    store.setState({ isOntologyVisible: true });
  }

  restoreFromDock() {
    this.container.classList.remove('is-minimized');
    this.isMinimized = false;
    if (this.lastWindowMode === 'main') this.setMainMode();
    else this.setMiniMode();
  }
}
