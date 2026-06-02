import {
    TarotApiError,
    createTarotApiClient,
} from './tarot-api.js';

const STORAGE_KEY = 'tarot-demo-session-id';
const DECK_RENDER_COUNT = 24;
const SAMPLE_QUESTIONS = [
    '我的感情发展会如何？',
    '我接下来应该如何处理现在的工作压力？',
    '这段关系值得我继续投入吗？',
];

const api = createTarotApiClient('');

const $ = (id) => document.getElementById(id);
const pages = {
    home: $('homePage'),
    draw: $('drawPage'),
    result: $('resultPage'),
};

const apiStatus = $('apiStatus');
const restartBtn = $('restartBtn');
const homeQuestion = $('questionInput');
const questionHint = $('questionHint');
const questionCount = $('questionCount');
const spreadList = $('spreadList');
const backHomeBtn = $('backHomeBtn');
const drawQuestion = $('drawQuestion');
const drawSpreadName = $('drawSpreadName');
const remainingCount = $('remainingCount');
const drawSubtitle = $('drawSubtitle');
const positionList = $('positionList');
const deckGrid = $('deckGrid');
const generateReadingBtn = $('generateReadingBtn');
const resultRestartBtn = $('resultRestartBtn');
const resultQuestion = $('resultQuestion');
const readingTitle = $('readingTitle');
const openingMessage = $('openingMessage');
const readingCards = $('readingCards');
const overallAnalysis = $('overallAnalysis');
const energyFlow = $('energyFlow');
const conflictHarmony = $('conflictHarmony');
const timingHint = $('timingHint');
const actionAdvice = $('actionAdvice');
const longTermAdvice = $('longTermAdvice');
const toast = $('toast');
const loadingMask = $('loadingMask');
const loadingText = $('loadingText');

const state = {
    spreads: [],
    session: null,
    currentPage: 'home',
    loading: false,
};

function showToast(message) {
    toast.textContent = message;
    toast.classList.remove('hidden');
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => {
        toast.classList.add('hidden');
    }, 2600);
}

function setLoading(isLoading, message = '群星正在为你排列答案...') {
    state.loading = isLoading;
    loadingText.textContent = message;
    loadingMask.classList.toggle('hidden', !isLoading);
    generateReadingBtn.disabled = isLoading || !state.session || state.session.remaining_count > 0;
    renderDeck();
}

function setApiStatus(mode, text) {
    apiStatus.textContent = text;
    apiStatus.classList.remove('status-pending', 'status-connected', 'status-error');
    apiStatus.classList.add(mode);
}

function persistSession() {
    if (state.session?.session_id) {
        sessionStorage.setItem(STORAGE_KEY, state.session.session_id);
    } else {
        sessionStorage.removeItem(STORAGE_KEY);
    }
}

function resetSession(keepQuestion = false) {
    const currentQuestion = homeQuestion.value;
    state.session = null;
    persistSession();
    if (!keepQuestion) {
        homeQuestion.value = '';
    } else {
        homeQuestion.value = currentQuestion;
    }
    updateQuestionMeta();
    showPage('home');
    renderDrawPage();
    renderResultPage();
}

function showPage(pageName) {
    state.currentPage = pageName;
    Object.entries(pages).forEach(([name, element]) => {
        element.classList.toggle('active', name === pageName);
    });
}

function validateQuestion(question) {
    const normalized = question.trim().replace(/\s+/g, ' ');
    if (!normalized) {
        throw new Error('请先输入你想咨询的问题');
    }
    if (normalized.length < 6) {
        throw new Error('问题至少需要 6 个字符');
    }
    if (normalized.length > 120) {
        throw new Error('问题最多 120 个字符');
    }
    return normalized;
}

function updateQuestionMeta() {
    const length = homeQuestion.value.trim().length;
    questionCount.textContent = `${length} / 120`;
    if (length === 0) {
        questionHint.textContent = '建议聚焦一个核心问题，字数 6-120 字。';
        return;
    }
    if (length < 6) {
        questionHint.textContent = '问题有点短，可以再具体一点。';
        return;
    }
    questionHint.textContent = '问题已经足够清晰，可以开始选择牌阵。';
}

function orientationText(value) {
    return value === 'upright' ? '正位' : '逆位';
}

function cardSymbol(card) {
    if (!card) return '✧';
    if (card.arcana_type === 'major') return '✦';
    const symbols = {
        cups: '杯',
        swords: '剑',
        wands: '杖',
        pentacles: '币',
    };
    return symbols[card.suit] || '✦';
}

function createCardMini(card, orientation) {
    if (!card) {
        return `
            <div class="card-mini empty">
                <span class="card-symbol">✧</span>
                <span class="card-name">待抽取</span>
                <span class="card-orientation">命运未揭晓</span>
            </div>
        `;
    }
    return `
        <div class="card-mini">
            <span class="card-symbol">${cardSymbol(card)}</span>
            <span class="card-name">${card.name_cn}</span>
            <span class="card-orientation">${orientationText(orientation)}</span>
        </div>
    `;
}

function renderSpreadList() {
    spreadList.innerHTML = '';
    state.spreads.forEach((spread) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'spread-card';
        button.innerHTML = `
            <div>
                <h3>${spread.name}</h3>
                <p class="spread-subtitle">${spread.subtitle}</p>
            </div>
            <p>${spread.description}</p>
            <div class="spread-footer">
                <span class="pill">${spread.card_count} 张牌</span>
                <span class="pill ${spread.premium_reserved ? 'premium' : ''}">
                    ${spread.premium_reserved ? '预留深度版' : '首版可用'}
                </span>
            </div>
        `;
        button.addEventListener('click', () => startDivination(spread.id));
        spreadList.appendChild(button);
    });
}

function renderDrawPage() {
    if (!state.session) {
        drawQuestion.textContent = '尚未开始新的占卜';
        drawSpreadName.textContent = '--';
        remainingCount.textContent = '0';
        drawSubtitle.textContent = '点击下方任意卡牌，命运将揭示下一张答案。';
        positionList.innerHTML = '';
        renderDeck();
        return;
    }

    const session = state.session;
    drawQuestion.textContent = session.question;
    drawSpreadName.textContent = session.spread.name;
    remainingCount.textContent = String(session.remaining_count);
    drawSubtitle.textContent = session.remaining_count > 0
        ? `当前正在抽取「${session.positions[session.drawn_cards.length]?.name || ''}」位置。`
        : '卡牌已经全部抽满，可以开始解读。';

    positionList.innerHTML = '';
    session.positions.forEach((position, index) => {
        const drawnCard = session.drawn_cards.find((item) => item.position_index === index);
        const article = document.createElement('article');
        const isActive = !drawnCard && index === session.drawn_cards.length && session.remaining_count > 0;
        article.className = `position-card${drawnCard ? ' filled' : ''}${isActive ? ' active' : ''}`;
        article.innerHTML = `
            <div>
                <h3>${position.name}</h3>
                <p class="position-description">${position.description}</p>
            </div>
            ${createCardMini(drawnCard?.card, drawnCard?.orientation)}
            <p class="card-position-note">
                ${drawnCard
                    ? `${drawnCard.card.name_cn}${orientationText(drawnCard.orientation)}已经落入此位。`
                    : isActive
                        ? '当前命运之门正为这个位置开启。'
                        : '等待抽取。'}
            </p>
        `;
        positionList.appendChild(article);
    });

    generateReadingBtn.disabled = state.loading || session.remaining_count > 0;
    renderDeck();
}

function renderDeck() {
    deckGrid.innerHTML = '';
    const disabled = state.loading || !state.session || state.session.remaining_count === 0;
    for (let index = 0; index < DECK_RENDER_COUNT; index += 1) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'deck-card';
        button.disabled = disabled;
        button.setAttribute('aria-label', `抽取第 ${index + 1} 张牌背`);
        button.addEventListener('click', drawNextCard);
        deckGrid.appendChild(button);
    }
}

function renderResultPage() {
    if (!state.session?.reading) {
        resultQuestion.textContent = '';
        readingTitle.textContent = '';
        openingMessage.textContent = '';
        readingCards.innerHTML = '';
        overallAnalysis.textContent = '';
        energyFlow.textContent = '';
        conflictHarmony.textContent = '';
        timingHint.textContent = '';
        actionAdvice.textContent = '';
        longTermAdvice.textContent = '';
        return;
    }

    const { question, reading } = state.session;
    resultQuestion.textContent = question;
    readingTitle.textContent = reading.title;
    openingMessage.textContent = reading.opening_message;
    overallAnalysis.textContent = reading.overall_analysis;
    energyFlow.textContent = reading.energy_flow;
    conflictHarmony.textContent = reading.conflict_and_harmony;
    timingHint.textContent = reading.timing_hint;
    actionAdvice.textContent = reading.action_advice;
    longTermAdvice.textContent = reading.long_term_advice;

    readingCards.innerHTML = '';
    reading.cards.forEach((cardReading) => {
        const drawnCard = state.session.drawn_cards.find((item) => item.position_name === cardReading.position_name);
        const article = document.createElement('article');
        article.className = 'reading-card';
        article.innerHTML = `
            <div class="reading-card-header">
                ${createCardMini(drawnCard?.card, cardReading.orientation)}
                <div>
                    <p class="reading-meta">${cardReading.position_name}</p>
                    <h3>${cardReading.card_name}（${orientationText(cardReading.orientation)}）</h3>
                    <span class="meaning">核心含义：${cardReading.core_meaning}</span>
                </div>
            </div>
            <p class="card-analysis">${cardReading.analysis}</p>
        `;
        readingCards.appendChild(article);
    });
}

function hydrateSession(payload) {
    state.session = {
        session_id: payload.session_id,
        status: payload.status,
        question: payload.question,
        spread_id: payload.spread_id || payload.spread.id,
        spread: payload.spread,
        positions: payload.positions,
        drawn_cards: payload.drawn_cards || [],
        remaining_count: payload.remaining_count,
        reading: payload.reading || null,
        expires_at: payload.expires_at,
    };
    persistSession();
    renderDrawPage();
    renderResultPage();
}

async function startDivination(spreadId) {
    let question;
    try {
        question = validateQuestion(homeQuestion.value);
    } catch (error) {
        showToast(error.message);
        homeQuestion.focus();
        return;
    }

    try {
        setLoading(true, '星辰正在校准你的问题...');
        const response = await api.createDivination({
            question,
            spread_id: spreadId,
        });
        hydrateSession({
            ...response,
            spread_id: response.spread.id,
            drawn_cards: [],
            reading: null,
        });
        showPage('draw');
        showToast('牌阵已展开，开始抽牌吧。');
    } catch (error) {
        handleApiError(error);
    } finally {
        setLoading(false);
    }
}

async function drawNextCard() {
    if (!state.session || state.loading || state.session.remaining_count === 0) {
        return;
    }
    try {
        setLoading(true, '命运正在翻开下一张牌...');
        const response = await api.drawCard(state.session.session_id, {
            client_draw_index: state.session.drawn_cards.length,
        });
        state.session.drawn_cards = [...state.session.drawn_cards, response.drawn_card];
        state.session.status = response.status;
        state.session.remaining_count = response.remaining_count;
        renderDrawPage();
        persistSession();
        if (response.all_cards_drawn) {
            showToast('所有牌位都已揭晓，可以开始解读。');
        }
    } catch (error) {
        handleApiError(error);
    } finally {
        setLoading(false);
    }
}

async function generateReading() {
    if (!state.session || state.loading || state.session.remaining_count > 0) {
        return;
    }
    try {
        setLoading(true, '群星正在为你排列答案...');
        const response = await api.generateReading(state.session.session_id);
        state.session.status = response.status;
        state.session.reading = response.reading;
        persistSession();
        renderResultPage();
        showPage('result');
    } catch (error) {
        handleApiError(error);
    } finally {
        setLoading(false);
    }
}

async function restoreSession() {
    const savedSessionId = sessionStorage.getItem(STORAGE_KEY);
    if (!savedSessionId) {
        return;
    }
    try {
        const response = await api.getDivinationSession(savedSessionId);
        hydrateSession(response);
        if (response.status === 'reading_ready' && response.reading) {
            showPage('result');
        } else {
            showPage('draw');
        }
        showToast('已恢复你刚才的占卜会话。');
    } catch (error) {
        sessionStorage.removeItem(STORAGE_KEY);
        if (!(error instanceof TarotApiError && error.code === 'SESSION_NOT_FOUND')) {
            handleApiError(error);
        }
    }
}

async function init() {
    updateQuestionMeta();
    if (!homeQuestion.value) {
        homeQuestion.value = SAMPLE_QUESTIONS[0];
        updateQuestionMeta();
    }

    setApiStatus('status-pending', '正在连接占卜之门...');
    try {
        const [health, spreadsResponse] = await Promise.all([
            api.getHealth(),
            api.getSpreads(),
        ]);
        state.spreads = spreadsResponse.items || [];
        renderSpreadList();
        setApiStatus('status-connected', `${health.service} 已连接，命运流转正常`);
        await restoreSession();
    } catch (error) {
        setApiStatus('status-error', '占卜服务暂时失联');
        handleApiError(error, true);
    }
    renderDeck();
}

function handleApiError(error, silentToast = false) {
    console.error(error);
    const message = error instanceof TarotApiError ? error.message : (error?.message || '请求失败');
    if (!silentToast) {
        showToast(message);
    }
}

homeQuestion.addEventListener('input', updateQuestionMeta);
restartBtn.addEventListener('click', () => resetSession(true));
backHomeBtn.addEventListener('click', () => resetSession(true));
resultRestartBtn.addEventListener('click', () => resetSession(false));
generateReadingBtn.addEventListener('click', generateReading);

init();
