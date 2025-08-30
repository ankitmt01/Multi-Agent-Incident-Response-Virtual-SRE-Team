export type IncEvent = {
  ts: number
  event: string
  data: Record<string, any>
}

export function connectIncidentStream(incidentId: string, onEvent: (e: IncEvent) => void) {
  const url = (import.meta.env.VITE_API_URL ?? "/api") + `/incidents/${incidentId}/stream`
  const es = new EventSource(url, { withCredentials: false })

  es.onmessage = (m) => {
    try {
      const parsed = JSON.parse(m.data) as IncEvent
      onEvent(parsed)
    } catch {
      // ignore
    }
  }

  // named events (optional)
  const evs = ["connected","run_start","stage","stage_start","stage_done","run_done"]
  for (const ev of evs) {
    es.addEventListener(ev, (m: MessageEvent) => {
      try {
        const parsed = JSON.parse((m as MessageEvent).data) as IncEvent
        onEvent(parsed)
      } catch {}
    })
  }

  es.onerror = () => {
    // auto-reconnect by closing; browser will re-open if server supports it, or you can recreate manually
    // es.close()
  }

  return () => es.close()
}
