const API_BASE = ``;

export async function parseText(text) {
  const response = await fetch(`${API_BASE}/api/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function parseQuality(jsonResult) {
  const response = await fetch(`${API_BASE}/api/parse-quality`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ json_result: jsonResult }),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function ontologyEvaluate(text, jsonResult, rowId) {
  const response = await fetch(`${API_BASE}/api/ontology-evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      raw_text: text,
      json_result: jsonResult,
      row_id: rowId,
    }),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function loadTestData() {
  const response = await fetch(`${API_BASE}/api/test-data`);
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function saveResult(payload) {
  const response = await fetch(`${API_BASE}/api/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}
