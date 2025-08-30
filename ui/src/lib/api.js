// e.g., src/lib/api.js
const API_BASE = import.meta.env.VITE_API_URL ?? '/api';
export async function listIncidents() {
  const r = await fetch(`${API_BASE}/incidents/`, { headers: { Accept: 'application/json' }});
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}

