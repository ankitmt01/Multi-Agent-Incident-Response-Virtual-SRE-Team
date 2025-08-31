import { useEffect, useRef, useState } from 'react';

export type SSEEvent = { event: string; data: any };

export function useSSE(url: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!url) return;
    const es = new EventSource(url, { withCredentials: false });
    ref.current = es;
    setOpen(true);

    const onMessage = (e: MessageEvent) => {
      try {
        setEvents(prev => [...prev, { event: e.type || 'message', data: JSON.parse(e.data) }]);
      } catch {
        setEvents(prev => [...prev, { event: e.type || 'message', data: e.data }]);
      }
    };

    const forward = (type: string) => (e: MessageEvent) => {
      try {
        setEvents(prev => [...prev, { event: type, data: JSON.parse(e.data) }]);
      } catch {
        setEvents(prev => [...prev, { event: type, data: e.data }]);
      }
    };

    es.addEventListener('run_start', forward('run_start'));
    es.addEventListener('stage_start', forward('stage_start'));
    es.addEventListener('stage_done', forward('stage_done'));
    es.addEventListener('run_done', forward('run_done'));
    es.addEventListener('error', forward('error'));
    es.onmessage = onMessage;

    es.onerror = () => {
      es.close();
      setOpen(false);
    };

    return () => {
      es.close();
      setOpen(false);
    };
  }, [url]);

  return { open, events };
}
