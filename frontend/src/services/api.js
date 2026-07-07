// Central API client for the TdR Explorer backend.
//
// Base URL resolution order:
//   1. VITE_API_BASE env var (e.g. "http://localhost:8000") — set for prod builds
//   2. "/api" — proxied to the backend by Vite in dev (see vite.config.js)
const BASE = import.meta.env.VITE_API_BASE || "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

export function getHealth() {
  return request("/health");
}

// ── Search (retrieval only) ──────────────────────────────────────
export function search(query, limit = 10, document = null) {
  return request("/search", {
    method: "POST",
    body: JSON.stringify({ query, limit, document }),
  });
}

// ── Corpus metadata (for filters) ────────────────────────────────
export function listDocuments() {
  return request("/filters/documents");
}

// URL to open/view an original TdR PDF in the browser.
export function documentUrl(filename) {
  return `${BASE}/documents/${encodeURIComponent(filename)}`;
}

// ── Conversations (persisted chat history) ───────────────────────
export function listConversations() {
  return request("/conversations");
}

export function createConversation(title) {
  return request("/conversations", {
    method: "POST",
    body: JSON.stringify({ title: title ?? null }),
  });
}

export function getConversation(id) {
  return request(`/conversations/${id}`);
}

export function deleteConversation(id) {
  return request(`/conversations/${id}`, { method: "DELETE" });
}

export function sendMessage(conversationId, query, opts = {}) {
  return request(`/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({
      query,
      context_limit: opts.contextLimit ?? 5,
      temperature: opts.temperature ?? 0.2,
      document: opts.document ?? null,
    }),
  });
}
