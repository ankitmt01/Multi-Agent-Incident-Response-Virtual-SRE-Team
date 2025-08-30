const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function jfetch(url, opts = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${t}`);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

export const api = {
  listIncidents: () => jfetch(`${API_BASE}/incidents`),
  getIncident: (id) => jfetch(`${API_BASE}/incidents/${id}`),            // ← NEW
  detectIncident: (payload) =>
    jfetch(`${API_BASE}/incidents/detect`, { method: "POST", body: JSON.stringify(payload) }),
  runPipeline: (id) => jfetch(`${API_BASE}/incidents/${id}/run`, { method: "POST" }),
  approveCandidate: (id, name) =>                                       // ← NEW
    jfetch(`${API_BASE}/incidents/${id}/approve?candidate_name=${encodeURIComponent(name)}`, { method: "POST" }),
  reportHtmlUrl: (id) => `${API_BASE}/incidents/${id}/report.html`,
  seedMetrics: (service = "payments", minutes = 120) =>
    jfetch(`${API_BASE}/demo/seed-metrics`, { method: "POST", body: JSON.stringify({ service, minutes }) }),
  generateIncidents: (service = "payments", count = 3, run_pipeline = true) =>
    jfetch(`${API_BASE}/demo/generate-incidents`, {
      method: "POST",
      body: JSON.stringify({ service, count, run_pipeline }),
    }),
};
