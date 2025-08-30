import React from 'react';

type Evidence = { title: string; content: string; score?: number; uri?: string };

export default function IncidentEvidence({ evidence }: { evidence: Evidence[] }) {
  if (!evidence || evidence.length === 0) return <div>No evidence yet.</div>;

  return (
    <div className="space-y-3">
      {evidence.map((e, i) => (
        <div key={i} style={{border:'1px solid #e5e7eb', borderRadius:12, padding:12}}>
          <div style={{display:'flex', justifyContent:'space-between', gap:8}}>
            <div>
              <div style={{fontWeight:600}}>{e.title}</div>
              {typeof e.score === 'number' && (
                <div style={{fontSize:12, color:'#6b7280'}}>score: {e.score.toFixed(3)}</div>
              )}
            </div>
            {e.uri && (
              <a href={e.uri} target="_blank" rel="noreferrer" style={{fontSize:14, textDecoration:'underline'}}>
                Open
              </a>
            )}
          </div>
          <pre style={{marginTop:8, whiteSpace:'pre-wrap', fontSize:14}}>{e.content}</pre>
        </div>
      ))}
    </div>
  );
}
