import { useEffect, useState } from "react";
import { api } from "./api";

export default function Candidates({ incidentId, onClose, onChanged }) {
  const [inc, setInc] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try { setInc(await api.getIncident(incidentId)); }
    catch (e) { setErr(String(e)); }
  }

  useEffect(()=>{ load(); }, [incidentId]);

  async function approve(name) {
    setBusy(true);
    try {
      await api.approveCandidate(incidentId, name);
      // optional: re-run pipeline to refresh validation/report data
      await api.runPipeline(incidentId);
      await load();
      onChanged?.();
    } catch (e) {
      alert(e);
    } finally {
      setBusy(false);
    }
  }

  if (!inc) return (
    <div style={panel}>
      <h3>Candidates</h3>
      {err ? <div style={{color:"crimson"}}>{err}</div> : <div>Loading…</div>}
      <button onClick={onClose} style={{marginTop:8}}>Close</button>
    </div>
  );

  return (
    <div style={panel}>
      <h3>Candidates — <code>{inc.id}</code></h3>
      <div style={{ maxHeight: 360, overflowY: "auto" }}>
        <table style={{ width:"100%", borderCollapse:"collapse" }}>
          <thead>
            <tr><th>Name</th><th>Policy</th><th>Reasons</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {(inc.remediation_candidates || []).map(c => {
              const st = c.policy_status || "unknown";
              const reasons = (c.policy_reasons || []).join("; ");
              const canApprove = st === "needs_approval";
              return (
                <tr key={c.name}>
                  <td>{c.name}</td>
                  <td>{st}</td>
                  <td style={{maxWidth: 420}}>{reasons}</td>
                  <td>
                    <button
                      disabled={!canApprove || busy}
                      onClick={()=>approve(c.name)}
                      title={canApprove ? "Approve this plan" : "Only 'needs_approval' plans can be approved"}
                    >
                      Approve
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ display:"flex", justifyContent:"flex-end", gap:8, marginTop:8 }}>
        <a href={api.reportHtmlUrl(incidentId)} target="_blank" rel="noreferrer">Open report</a>
        <button onClick={onClose}>Close</button>
      </div>
    </div>
  );
}

const panel = {
  position:"fixed", right:16, bottom:16, left:16,
  background:"#fff", border:"1px solid #ddd", borderRadius:8, padding:12,
  boxShadow:"0 12px 28px rgba(0,0,0,0.18)", zIndex: 9999
};
