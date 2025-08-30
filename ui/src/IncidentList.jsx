import { useEffect, useState } from "react";
import { api } from "./api";
import Candidates from "./Candidates";

export default function IncidentList({ reloadKey }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [panelId, setPanelId] = useState(null);

  async function load() {
    setErr(""); setLoading(true);
    try {
      const data = await api.listIncidents();
      data.sort((a,b)=> new Date(b.created_at)-new Date(a.created_at));
      setRows(data);
    } catch (ex) {
      setErr(String(ex));
    } finally { setLoading(false); }
  }

  useEffect(()=>{ load(); }, [reloadKey]);

  async function run(id) {
    try { await api.runPipeline(id); await load(); }
    catch (ex) { alert(ex); }
  }

  return (
    <div>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", margin:"12px 0" }}>
        <h2>Incidents</h2>
        <button onClick={load} disabled={loading}>{loading ? "Refreshing..." : "Refresh"}</button>
      </div>
      {err && <div style={{ color:"crimson", marginBottom:8 }}>{err}</div>}
      <div style={{ overflowX:"auto" }}>
        <table style={{ width:"100%", borderCollapse:"collapse" }}>
          <thead>
            <tr>
              <th>ID</th><th>Service</th><th>Severity</th><th>Status</th><th>Created</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length===0 && !loading && <tr><td colSpan={6} style={{ textAlign:"center", padding:12 }}>No incidents yet.</td></tr>}
            {rows.map(x => (
              <tr key={x.id}>
                <td><code>{x.id}</code></td>
                <td>{x.service}</td>
                <td>{String(x.severity).split(".").pop()}</td>
                <td>{x.status}</td>
                <td>{new Date(x.created_at).toLocaleString()}</td>
                <td style={{ whiteSpace:"nowrap" }}>
                  <button onClick={()=>run(x.id)} style={{ marginRight:8 }}>Run</button>
                  <button onClick={()=>setPanelId(x.id)} style={{ marginRight:8 }}>Candidates</button>
                  <a href={api.reportHtmlUrl(x.id)} target="_blank" rel="noreferrer">Report</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {panelId && (
        <Candidates
          incidentId={panelId}
          onClose={()=>setPanelId(null)}
          onChanged={load}
        />
      )}
    </div>
  );
}
