// ui/src/App.tsx
import { useState } from "react";
import CreateDetect from "./components/CreateDetect";
import Incidents from "./components/Incidents";
import { Incident } from "./lib/api";

export default function App() {
  const [last, setLast] = useState<Incident | null>(null);
  return (
    <div style={{ padding: 16, display: "grid", gap: 24 }}>
      <h2>Agentic Incident Response</h2>
      <CreateDetect onCreated={setLast} />
      {last && <div style={{ color: "green" }}>Created: {last.id}</div>}
      <Incidents />
    </div>
  );
}
