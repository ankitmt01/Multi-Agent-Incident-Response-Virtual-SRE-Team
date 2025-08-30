import { useState } from "react";
import { api } from "./api";

export default function DemoPanel({ onChanged }) {
  const [service, setService] = useState("payments");
  const [minutes, setMinutes] = useState(120);
  const [count, setCount] = useState(3);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function seed() {
    setBusy(true); setMsg("");
    try {
      await api.seedMetrics(service, Number(minutes));
      setMsg(`Seeded metrics for ${service} (${minutes}m).`);
      onChanged?.();
    } catch (e) { setMsg(String(e)); }
    finally { setBusy(false); }
  }

  async function gen() {
    setBusy(true); setMsg("");
    try {
      const r = await api.generateIncidents(service, Number(count), true);
      setMsg(`Generated ${r.created_ids.length} incidents (pipeline run).`);
      onChanged?.();
    } catch (e) { setMsg(String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div style={{ border:"1px solid #ddd", borderRadius:8, padding:12, marginBottom:16 }}>
      <h2>Demo data</h2>
      <div style={{ display:"grid", gap:8, gridTemplateColumns:"1fr 1fr 1fr auto auto" }}>
        <label>Service
          <input value={service} onChange={e=>setService(e.target.value)} />
        </label>
        <label>Minutes (metrics)
          <input type="number" min={10} max={720} value={minutes} onChange={e=>setMinutes(e.target.value)} />
        </label>
        <label>Count (incidents)
          <input type="number" min={1} max={20} value={count} onChange={e=>setCount(e.target.value)} />
        </label>
        <button disabled={busy} onClick={seed}>{busy ? "Working..." : "Seed metrics"}</button>
        <button disabled={busy} onClick={gen}>{busy ? "Working..." : "Generate incidents"}</button>
      </div>
      {msg && <div style={{ marginTop:8, color: msg.startsWith("HTTP") ? "crimson" : "green" }}>{msg}</div>}
    </div>
  );
}