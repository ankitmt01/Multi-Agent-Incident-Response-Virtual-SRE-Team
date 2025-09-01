// ui/src/components/CreateDetect.tsx
import { useState } from "react";
import { api, Incident } from "../lib/api";

export default function CreateDetect({ onCreated }: { onCreated: (inc: Incident) => void }) {
  const [service, setService] = useState("payments");
  const [cause, setCause] = useState("bad deploy");
  const [rate, setRate] = useState("12.0");
  const [p95, setP95] = useState("1200");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const inc: Incident = {
        id: "", // backend will assign if empty
        service,
        severity: null, // detector will fill
        created_at: new Date().toISOString(),
        suspected_cause: cause,
        status: "OPEN",
        signals: [
          { source: "metrics", label: "http_5xx_rate", value: parseFloat(rate) },
          { source: "metrics", label: "latency_p95", value: parseFloat(p95), unit: "ms" },
        ],
      } as any;
      const out = await api.detect(inc);
      onCreated(out);
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} style={{ display: "grid", gap: 8, maxWidth: 520 }}>
      <h3>Create / Detect</h3>
      <label>Service <input value={service} onChange={e => setService(e.target.value)} required /></label>
      <label>Suspected cause <input value={cause} onChange={e => setCause(e.target.value)} /></label>
      <label>5xx rate <input value={rate} onChange={e => setRate(e.target.value)} type="number" step="0.1" /></label>
      <label>p95 (ms) <input value={p95} onChange={e => setP95(e.target.value)} type="number" step="1" /></label>
      <div>
        <button disabled={busy} type="submit">{busy ? "Creating..." : "Create / Detect"}</button>
      </div>
      {err && <div style={{ color: "crimson" }}>{err}</div>}
    </form>
  );
}
