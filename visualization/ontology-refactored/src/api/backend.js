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

export async function parseQuality(rawText, jsonResult, rowId) {
  const response = await fetch(`${API_BASE}/api/parse-quality`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      raw_text: rawText,
      json_result: jsonResult,
      row_id: rowId,
    }),
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

export async function augmentProvisions(graphData) {
  const res = await fetch(`${API_BASE}/api/augment-provisions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ graph_data: graphData })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function parseEnhancement(rawText, jsonResult, rowId, qualityResult, ontologyEval) {
  const response = await fetch(`${API_BASE}/api/parse-enhancement`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      raw_text: rawText,
      json_result: jsonResult,
      row_id: rowId,
      quality_result: qualityResult,
      ontology_eval: ontologyEval,
    }),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function previewEnhancementMerge(rowId, enhancementRunId, baseVersionId) {
  const response = await fetch(`${API_BASE}/api/parse-enhancement/preview-merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      row_id: rowId,
      enhancement_run_id: enhancementRunId,
      base_version_id: baseVersionId,
    }),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function mergeEnhancementResult(rowId, enhancementRunId, baseVersionId) {
  const response = await fetch(`${API_BASE}/api/parse-enhancement/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      row_id: rowId,
      enhancement_run_id: enhancementRunId,
      base_version_id: baseVersionId,
    }),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function loadCaseVersions(rowId) {
  const response = await fetch(`${API_BASE}/api/saved-case/${encodeURIComponent(rowId)}/versions`);
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function loadSavedCaseVersion(rowId, versionId) {
  const response = await fetch(`${API_BASE}/api/saved-case/${encodeURIComponent(rowId)}?version_id=${encodeURIComponent(versionId)}`);
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

export async function buildRetrievalBundle(payload) {
  const response = await fetch(`${API_BASE}/api/retrieval/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function updateRetrievalEntry(payload) {
  const response = await fetch(`${API_BASE}/api/retrieval/update-entry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function reembedRetrievalBundle(payload) {
  const response = await fetch(`${API_BASE}/api/retrieval/re-embed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function writeRetrievalBundle(payload) {
  const response = await fetch(`${API_BASE}/api/retrieval/write`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function loadRetrievalBundle(bundleId) {
  const response = await fetch(`${API_BASE}/api/retrieval/bundle/${encodeURIComponent(bundleId)}`);
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function writeNeo4jCase(payload) {
  const response = await fetch(`${API_BASE}/api/neo4j/write-case`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function getNeo4jCaseStatus(docId) {
  const response = await fetch(`${API_BASE}/api/neo4j/case-status/${encodeURIComponent(docId)}`);
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 404 && data.exists === false) return data;
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  if (data.error) throw new Error(data.error);
  return data;
}

export async function writeNeo4jRetrievalLayer(payload) {
  const response = await fetch(`${API_BASE}/api/neo4j/write-retrieval-layer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  // #region debug-point D:retrieval-neo4j-response
  fetch("http://127.0.0.1:7777/event",{method:"POST",body:JSON.stringify({sessionId:"retrieval-404-block",runId:"post-fix",hypothesisId:"D",location:"backend.js:writeNeo4jRetrievalLayer:response",msg:"[DEBUG] Retrieval Neo4j HTTP response received",data:{ok:response.ok,status:response.status,url:response.url},ts:Date.now()})}).catch(()=>{});
  // #endregion
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function writeNeo4jDiscoveryLayer(payload) {
  const response = await fetch(`${API_BASE}/api/neo4j/write-discovery-layer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}
