'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { getRecentSentinelEvents, getSentinelStatus, getSentinelWatchRoots, sentinelEventsUrl } from '@/lib/api';
import type { SentinelEvent } from '@/lib/types';

export function SentinelActivity() {
  const status = useQuery({ queryKey: ['sentinel-status'], queryFn: getSentinelStatus, retry: false, refetchInterval: 5000 });
  const roots = useQuery({ queryKey: ['sentinel-roots'], queryFn: getSentinelWatchRoots, retry: false, refetchInterval: 5000 });
  const recent = useQuery({ queryKey: ['sentinel-recent'], queryFn: getRecentSentinelEvents, retry: false });
  const [events, setEvents] = useState<SentinelEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (recent.data) setEvents((current) => mergeEvents(current, recent.data));
  }, [recent.data]);

  useEffect(() => {
    const source = new EventSource(sentinelEventsUrl());
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener('sentinel', (message) => {
      try {
        const event = JSON.parse((message as MessageEvent).data) as SentinelEvent;
        if (event.event_id) setEvents((current) => mergeEvents([event], current));
      } catch { /* Invalid data does not interrupt subsequent events. */ }
    });
    return () => { source.close(); setConnected(false); };
  }, []);

  return <section className="panel-card mt-4 p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="section-heading">Sentinel activity</h2><p className="section-copy">Real changes in folders authorized with the local <span className="mono">prism watch</span> command.</p></div><span className="rounded-full border border-[var(--border)] px-3 py-1 text-xs font-semibold">{status.data?.running ? 'ACTIVE' : 'OFF'} · Live feed {connected ? 'connected' : 'reconnecting'}</span></div>
    <div className="mt-4 text-xs text-[var(--muted)]">{status.data?.watch_root_count ?? 0} watched folders · Supported: PDF, ZIP, PNG</div>
    {roots.data?.length ? <div className="mt-2 flex flex-wrap gap-2">{roots.data.map((root) => <span key={root.root_id} className="rounded-md border border-[var(--border)] px-2 py-1 text-xs">{root.display_name}{root.recursive ? ' · recursive' : ''}</span>)}</div> : <p className="mt-2 text-xs text-[var(--muted)]">No folders configured. Add one with <span className="mono">prism watch add &quot;C:\path\to\folder&quot;</span>.</p>}
    <div className="mt-4 space-y-2">{events.length ? events.map((event) => <div key={event.event_id} className="rounded-md border border-[var(--border)] bg-[var(--panel-muted)] p-3 text-xs"><div className="flex flex-wrap items-center gap-2"><time className="text-[var(--muted)]">{new Date(event.timestamp).toLocaleTimeString()}</time><strong>{event.file_name ?? 'Sentinel'}</strong><span className="font-mono text-[10px]">{event.event_type}</span></div><p className="mt-1">{event.message}</p>{event.event_type === 'QUARANTINE_COMPLETED' ? <div className="mt-2 space-y-1"><p>Containment: QUARANTINED · Trigger: {event.containment_trigger}</p><p>Model prediction: {event.laya_prediction ?? '—'} · Confidence: {event.laya_confidence === null || event.laya_confidence === undefined ? '—' : `${Math.round(event.laya_confidence * 100)}%`}</p><p>Deterministic state: {event.verified_state ?? 'No deterministic verified state'}</p><p>Container: {event.container_name}</p></div> : null}{event.event_type === 'ANALYSIS_COMPLETED' || event.event_type === 'ALERT_RAISED' ? <div className="mt-2 space-y-1"><p>Laya prediction (advisory): {event.laya_prediction ?? '—'} · Route: {event.routing_decision ?? '—'}</p><p>Deterministic state: {event.verified_state ?? 'No deterministic verified state'}</p>{event.reason_codes.length ? <p>Reasons: {event.reason_codes.join(', ')}</p> : null}</div> : null}{event.artifact_id ? <Link className="mt-2 inline-block font-semibold text-[var(--cobalt)]" href={`/artifacts/${event.artifact_id}`}>Open artifact →</Link> : null}</div>) : <p className="text-xs text-[var(--muted)]">No Sentinel events yet.</p>}</div>
  </section>;
}

function mergeEvents(first: SentinelEvent[], second: SentinelEvent[]) {
  const seen = new Set<string>();
  return [...first, ...second].filter((event) => {
    if (seen.has(event.event_id)) return false;
    seen.add(event.event_id);
    return true;
  }).sort((a, b) => b.timestamp.localeCompare(a.timestamp)).slice(0, 100);
}
