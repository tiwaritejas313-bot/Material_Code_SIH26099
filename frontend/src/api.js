const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";
const TOKEN_KEY = "sih26099_token";
const USER_KEY = "sih26099_user";

let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function storeSession(token, username, role) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify({ username, role }));
  } catch {
    // ignore -- private browsing / blocked storage; session just won't persist across reloads
  }
}

export function logout() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    // ignore
  }
}

function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function handleResponse(res, fallbackMessage) {
  const body = await res.json().catch(() => ({}));
  if (res.status === 401 && onUnauthorized) {
    onUnauthorized();
  }
  if (!res.ok) {
    throw new Error(body.detail || fallbackMessage || `Request failed: ${res.status}`);
  }
  return body;
}

async function request(path) {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() });
  return handleResponse(res, `${path} failed`);
}

export async function login(username, password) {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const body = await handleResponse(res, "Login failed");
  storeSession(body.access_token, body.username, body.role);
  return body;
}

export function getHealth() {
  return request("/health");
}

export function getRecordStats() {
  return request("/records/stats");
}

export function listRecords({ source, category, cpse, limit = 25, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (source) params.set("source", source);
  if (category) params.set("category", category);
  if (cpse) params.set("cpse", cpse);
  params.set("limit", limit);
  params.set("offset", offset);
  return request(`/records?${params.toString()}`);
}

export function getCandidates(recordId, { topK = 8, sameCategoryOnly = true } = {}) {
  const params = new URLSearchParams();
  params.set("top_k", topK);
  params.set("same_category_only", sameCategoryOnly);
  return request(`/records/${recordId}/candidates?${params.toString()}`);
}

export async function evaluatePair(recordAId, recordBId) {
  const res = await fetch(`${API_BASE_URL}/pairs/evaluate`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ record_a_id: recordAId, record_b_id: recordBId }),
  });
  return handleResponse(res, "Evaluation failed");
}

export function getReviewQueue({ limit = 15, category, source, scanLimit = 300 } = {}) {
  const params = new URLSearchParams();
  params.set("limit", limit);
  params.set("scan_limit", scanLimit);
  if (category) params.set("category", category);
  if (source) params.set("source", source);
  return request(`/pairs/queue?${params.toString()}`);
}

export function getDecisions(limit = 50) {
  return request(`/pairs/decisions?limit=${limit}`);
}

export async function submitDecision(recordAId, recordBId, action, reason) {
  // No "reviewer" argument -- identity comes from the JWT server-side now,
  // not a free-text field the caller could set to anything.
  const res = await fetch(`${API_BASE_URL}/pairs/decision`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ record_a_id: recordAId, record_b_id: recordBId, action, reason }),
  });
  return handleResponse(res, "Decision failed");
}

export function listGroups({ status = "active", category, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  params.set("status", status);
  params.set("limit", limit);
  params.set("offset", offset);
  if (category) params.set("category", category);
  return request(`/groups?${params.toString()}`);
}

export function getGroup(commonCode) {
  return request(`/groups/${commonCode}`);
}

export function getRecordGroup(recordId) {
  return request(`/records/${recordId}/group`);
}

export function getDashboardSummary() {
  return request("/dashboard/summary");
}

export function getDashboardBreakdown() {
  return request("/dashboard/breakdown");
}

export async function legacyMappingSearch(code) {
  const res = await fetch(`${API_BASE_URL}/groups/search/lookup?code=${encodeURIComponent(code)}`, {
    headers: authHeaders(),
  });
  return handleResponse(res, "Search failed");
}

export async function downloadErpExport(format = "csv", status = "active") {
  // Can't be a plain <a href> anymore -- the endpoint now requires a Bearer
  // token, which browser navigation can't attach. Fetch with auth, then hand
  // the browser a Blob to save/open instead.
  const res = await fetch(`${API_BASE_URL}/erp/export?format=${format}&status=${status}`, {
    headers: authHeaders(),
  });
  if (res.status === 401 && onUnauthorized) onUnauthorized();
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Export failed: ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  if (format === "json") {
    window.open(url, "_blank");
  } else {
    const a = document.createElement("a");
    a.href = url;
    a.download = "cnmc_mapping_export.csv";
    a.click();
  }
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export function getAuditTrail({ entityType, entityId, limit = 50 } = {}) {
  const params = new URLSearchParams();
  if (entityType) params.set("entity_type", entityType);
  if (entityId) params.set("entity_id", entityId);
  params.set("limit", limit);
  return request(`/audit?${params.toString()}`);
}

export async function uploadRecords(file, sourceLabel) {
  const formData = new FormData();
  formData.append("file", file);
  if (sourceLabel) formData.append("source", sourceLabel);

  const res = await fetch(`${API_BASE_URL}/records/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  return handleResponse(res, "Upload failed");
}
