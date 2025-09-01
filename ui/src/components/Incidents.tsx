// ui/src/components/Incidents.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { api, Incident } from "../lib/api";

export default function Incidents() {
  const [rows, setRows] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const streamRef = useRef<EventSource | null>(null);

  const load = async () => {
    setLoading(true); setErr(null);
    try {
      const data = await api.listIncidents();
      // newest first
      data.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
      setRows(data);
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const run = async (id: string) => {
    setErr(null);
    try {
      await api.run(id);
      await load();
    } catch (e: any) { setErr(e.message || String(e)); }
  };

  const streamRun = (id: string) => {
    if (streamRef.current) { streamRef.current.close(); streamRef.current = null; }
    setLog([]);
    streamRef.current = api.streamRun(id, (type, data) => {
      setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${type}: ${typeof data === "string" ? data : JSON.stringify(data)}`]);
      if (type === "run_done" || type === "error") load();
    });
  };

  const approve = async (id: string) => {
    const name = prompt("Approve which candidate? (e.g., rollback_latest, scale_up)");
    if (!name) return;
    try { await api.approve(id, name); await load(); }
    catch (e: any) { alert(e.message || String(e)); }
  };

  const ReportLinks = ({ id }: { id: string }) => (
    <span>
      <a href={`/incidents/${encodeURIComponent(id)}/report.md`} target="_blank">MD</a>{" · "}
      <a href={`/incidents/${encodeURIComponent(id)}/report.html`} target="_blank">HTML</a>
    </span>
  );

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>Incidents</h3>
        <button onClick={load} disabled={loading}>{loading ? "Loading..." : "Refresh"}</button>
        <button onClick={() => api.seedMetrics().then(() => alert("Seeded metrics")).catch(e => alert(e.message))}>
          Seed demo metrics
        </button>
      </div>
      {err && <div style={{ color: "crimson" }}>{err}</div>}
      <table border={1} cellPadding={6} cellSpacing={0}>
        <thead>
          <tr>
            <th>ID</th><th>Service</th><th>Severity</th><th>Status</th><th>Created</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr><td colSpan={6} style={{ color: "#666" }}>No incidents yet.</td></tr>
          )}
          {rows.map(r => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{r.service}</td>
              <td>{r.severity ?? "-"}</td>
              <td>{r.status}</td>
              <td>{new Date(r.created_at).toLocaleString()}</td>
              <td style={{ display: "flex", gap: 6 }}>
                <button onClick={() => run(r.id)}>Run</button>
                <button onClick={() => streamRun(r.id)}>Run (stream)</button>
                <button onClick={() => approve(r.id)}>Approve…</button>
                <ReportLinks id={r.id} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {log.length > 0 && (
        <pre style={{ background: "#111", color: "#0f0", padding: 12, maxHeight: 240, overflow: "auto" }}>
          {log.join("\n")}
        </pre>
      )}
    </div>
  );
}
