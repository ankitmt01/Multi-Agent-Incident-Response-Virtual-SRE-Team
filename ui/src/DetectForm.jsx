import { useState } from "react";
import { api } from "./api";

export default function DetectForm({ onCreated }) {
  const [service, setService] = useState("payments");
  const [cause, setCause] = useState("bad deploy");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [fivexx, setFivexx] = useState(12);
  const [p95, setP95] = useState(1200);

  async function submit(e) {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      const payload = {
        service,
        signals: [
          { source: "metrics", label: "http_5xx_rate", value: Number(fivexx) },
          { source: "metrics", label: "latency_p95", value: Number(p95), unit: "ms" },
        ],
        suspected_cause: cause,
      };
      const inc = await api.detectIncident(payload);
      onCreated?.(inc);
      setBusy(false);
    } catch (ex) {
      setErr(String(ex)); setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ display: "grid", gap: 8, alignItems: "end", gridTemplateColumns: "1fr 1fr 1fr 1fr auto" }}>
      <label>Service
        <input value={service} onChange={e=>setService(e.target.value)} placeholder="service name" />
      </label>
      <label>Suspected cause
        <input value={cause} onChange={e=>setCause(e.target.value)} placeholder="e.g. bad deploy" />
      </label>
      <label>5xx rate
        <input type="number" value={fivexx} onChange={e=>setFivexx(e.target.value)} />
      </label>
      <label>p95 (ms)
        <input type="number" value={p95} onChange={e=>setP95(e.target.value)} />
      </label>
      <button disabled={busy} type="submit">{busy ? "Detecting..." : "Detect"}</button>
      {err && <div style={{ gridColumn: "1 / -1", color: "crimson" }}>{err}</div>}
    </form>
  );
}
