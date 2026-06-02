const DEFAULT_API_BASE = globalThis.__TAROT_API_BASE__ || '';

export class TarotApiError extends Error {
  constructor(code, message, status) {
    super(message);
    this.name = 'TarotApiError';
    this.code = code;
    this.status = status;
  }
}

async function request(path, options = {}, apiBase = DEFAULT_API_BASE) {
  const response = await fetch(`${apiBase}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  let data = null;
  try {
    data = await response.json();
  } catch (_error) {
    data = null;
  }

  if (!response.ok) {
    const errorCode = data?.error?.code || 'INTERNAL_ERROR';
    const errorMessage = data?.error?.message || '请求失败';
    throw new TarotApiError(errorCode, errorMessage, response.status);
  }

  return data;
}

export function createTarotApiClient(apiBase = DEFAULT_API_BASE) {
  return {
    getHealth() {
      return request('/api/v1/health', {}, apiBase);
    },

    getSpreads() {
      return request('/api/v1/spreads', {}, apiBase);
    },

    getSpreadDetail(spreadId) {
      return request(`/api/v1/spreads/${encodeURIComponent(spreadId)}`, {}, apiBase);
    },

    createDivination(payload) {
      return request('/api/v1/divinations', {
        method: 'POST',
        body: JSON.stringify(payload),
      }, apiBase);
    },

    drawCard(sessionId, payload = {}) {
      return request(`/api/v1/divinations/${encodeURIComponent(sessionId)}/draw`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }, apiBase);
    },

    generateReading(sessionId) {
      return request(`/api/v1/divinations/${encodeURIComponent(sessionId)}/reading`, {
        method: 'POST',
        body: JSON.stringify({}),
      }, apiBase);
    },

    getDivinationSession(sessionId) {
      return request(`/api/v1/divinations/${encodeURIComponent(sessionId)}`, {}, apiBase);
    },
  };
}

const defaultClient = createTarotApiClient();

export const getTarotHealth = () => defaultClient.getHealth();
export const getTarotSpreads = () => defaultClient.getSpreads();
export const getTarotSpreadDetail = (spreadId) => defaultClient.getSpreadDetail(spreadId);
export const createTarotDivination = (payload) => defaultClient.createDivination(payload);
export const drawTarotCard = (sessionId, payload) => defaultClient.drawCard(sessionId, payload);
export const generateTarotReading = (sessionId) => defaultClient.generateReading(sessionId);
export const getTarotDivinationSession = (sessionId) => defaultClient.getDivinationSession(sessionId);
