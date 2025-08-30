import { useState } from "react";
import DetectForm from "./DetectForm";
import IncidentList from "./IncidentList";
import DemoPanel from "./DemoPanel";

export default function App() {
  const [lastId, setLastId] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const bump = () => setReloadKey(k => k + 1);

  return (
    <div style={{ maxWidth: 1100, margin: "24px auto", padding: "0 16px", fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Arial" }}>
      <h1>Agentic Incident Response — UI</h1>
      <p style={{ color:"#555" }}>Detect incidents, run the pipeline, and open the HTML report.</p>

      <DemoPanel onChanged={bump} />

      <div style={{ border:"1px solid #ddd", borderRadius:8, padding:12, marginBottom:16 }}>
        <h2>Create / Detect</h2>
        <DetectForm onCreated={(inc)=> { setLastId(inc?.id || null); bump(); }} />
        {lastId && <p>Created <code>{lastId}</code>. You can run it from the table below.</p>}
      </div>

      <IncidentList reloadKey={reloadKey} />

      <footer style={{ marginTop: 24, color:"#777", fontSize: 12 }}>
        API: <code>{import.meta.env.VITE_API_URL || "http://localhost:8000"}</code>
      </footer>
    </div>
  );
}
