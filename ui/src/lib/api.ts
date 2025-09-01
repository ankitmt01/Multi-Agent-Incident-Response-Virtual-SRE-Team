// ui/src/lib/api.ts
export type Severity = "low" | "medium" | "high" | "critical" | null;

export interface IncidentSignal {
  source: string; label: string; value: number;
  unit?: string | null; window_s?: number | null; at?: string | null;
}

export interface EvidenceItem { title: string; content: string; score?: number; uri?: string | null; }

export interface RemediationCandidate {
  name: string;
  description?: string;
  steps?: string[];
  risks?: string[];
  rollback?: string[];
  rationale?: string;
  predicted_impact?: Record<string, any>;
  actions?: any[];
  policy_status?: string;
  policy_reasons?: string[];
}

export interface ValidationResult {
  candidate?: string;
  passed: boolean;
  notes?: string;
  kpi_before?: Record<string, any>;
  kpi_after?: Record<string, any>;
}

export interface Incident {
  id: string;
  service: string;
  severity: Severity;
  created_at: string;
  suspected_cause?: string | null;
  status: string;
  signals?: IncidentSignal[];
  evidence?: EvidenceItem[];
  remediation_candidates?: RemediationCandidate[];
  validation_results?: ValidationResult[];
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${text || "Internal Server Error"}`);
  }
  return res.json();
}

export const api = {
  listIncidents: () => fetch(`/incidents`).then(json<Incident[]>),
  detect: (inc: Incident) =>
    fetch(`/incidents/detect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(inc),
    }).then(json<Incident>),
  run: (id: string) =>
    fetch(`/incidents/${encodeURIComponent(id)}/run`, { method: "POST" }).then(json<{ ok: boolean }>()),
  approve: (id: string, candidateName: string) =>
    fetch(`/incidents/${encodeURIComponent(id)}/approve?candidate_name=${encodeURIComponent(candidateName)}`, {
      method: "POST",
    }).then(json<Incident>),
  seedMetrics: (service = "payments", minutes = 120) =>
    fetch(`/demo/seed-metrics`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service, minutes }),
    }).then(json<{ ok: boolean; path: string }>()),
  streamRun: (id: string, onEvent: (type: string, data: any) => void) => {
    const es = new EventSource(`/incidents/${encodeURIComponent(id)}/run.stream`);
    const wrap = (type: string) => (evt: MessageEvent) => {
      try { onEvent(type, JSON.parse(evt.data)); } catch { onEvent(type, evt.data); }
    };
    es.onmessage = wrap("message");
    es.addEventListener("run_start", wrap("run_start"));
    es.addEventListener("run_done", evt => { wrap("run_done")(evt); es.close(); });
    es.addEventListener("error", evt => { onEvent("error", (evt as any).data ?? "stream error"); es.close(); });
    return es; // caller can es.close()
  },
};
