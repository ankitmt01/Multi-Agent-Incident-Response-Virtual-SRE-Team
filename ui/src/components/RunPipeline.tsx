import React from 'react';
import { useSSE } from '@/hooks/useSSE';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api';

export default function RunPipeline({ incidentId }: { incidentId: string }) {
  const { open, events } = useSSE(`${API_BASE}/incidents/${incidentId}/run.stream`);

  return (
    <div style={{padding:12, border:'1px solid #e5e7eb', borderRadius:12}}>
      <div style={{display:'flex', alignItems:'center', justifyContent:'space-between'}}>
        <strong>Pipeline run</strong>
        <span style={{fontSize:12, color: open ? '#059669' : '#6b7280'}}>
          {open ? 'Streaming...' : 'Idle'}
        </span>
      </div>
      <div style={{marginTop:8, fontFamily:'monospace', fontSize:13, whiteSpace:'pre-wrap'}}>
        {events.map((e, i) => (
          <div key={i}>
            [{e.event}] {typeof e.data === 'string' ? e.data : JSON.stringify(e.data)}
          </div>
        ))}
      </div>
    </div>
  );
}
