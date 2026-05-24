const API_BASE = '';

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const data = await response.json();
  if (!response.ok || data.error) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

export async function parseText(text) {
  return fetchJson('/api/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });
}

export async function parseQuality(rawText, jsonResult, rowId) {
  return fetchJson('/api/parse-quality', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      raw_text: rawText,
      json_result: jsonResult,
      row_id: rowId
    })
  });
}

export async function ontologyEvaluate(text, jsonResult, rowId) {
  return fetchJson('/api/ontology-evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ raw_text: text, json_result: jsonResult, row_id: rowId })
  });
}

export async function loadTestData() {
  return fetchJson('/api/test-data');
}

export async function saveResult(payload) {
  return fetchJson('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

export async function fetchCasesIndex() {
  return fetchJson('/api/cases');
}

export async function fetchSavedCase(rowId) {
  return fetchJson(`/api/saved-case/${encodeURIComponent(rowId)}`);
}

export async function deleteSavedCase(rowId) {
  return fetchJson(`/api/saved-case/${encodeURIComponent(rowId)}`, {
    method: 'DELETE'
  });
}

export async function fetchSemanticLinks(nodes, threshold = 0.5) {
  const response = await fetch(`${API_BASE}/api/graph/semantic_link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nodes, threshold })
  });
  return response.json();
}

export async function fetchAdminStaticCases() {
  return fetchJson('/api/admin-static-cases');
}

export async function fetchAdminStaticCase(rowId, version) {
  const query = version ? `?version=${encodeURIComponent(version)}` : '';
  return fetchJson(`/api/admin-static-case/${encodeURIComponent(rowId)}${query}`);
}
