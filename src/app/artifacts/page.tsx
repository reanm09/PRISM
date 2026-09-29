'use client';

import Link from 'next/link';

import { RefreshCw, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { UploadArtifactButton } from '@/components/upload-artifact-button';
import { getRecentArtifacts } from '@/lib/recent-artifacts';
import type { Artifact } from '@/lib/types';

export default function ArtifactsPage() {
  const [items, setItems] = useState<Artifact[]>([]);
  const [query, setQuery] = useState('');
  useEffect(() => {
    setItems(getRecentArtifacts());
    const initialQuery = new URLSearchParams(window.location.search).get('q');
    if (initialQuery) setQuery(initialQuery);
  }, []);
  const filtered = items.filter((item) => {
    const q = query.trim().toLowerCase();
    return !q || [item.original_name, item.sha256, item.artifact_id, item.claimed_extension].some((value) => value.toLowerCase().includes(q));
  });
  return <AppShell><div className="mx-auto max-w-[1640px] px-6 py-7">
    <PageHeader eyebrow="Sentinel" title="Artifacts" description="Uploaded artifact records known to this browser. Each row links to the backend-backed artifact workspace." actions={<UploadArtifactButton />} />
    <div className="panel-card mb-4 flex items-center gap-2 p-3"><div className="flex min-w-[260px] flex-1 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--panel-muted)] px-3 py-2"><Search size={15} className="text-[var(--muted)]" /><input value={query} onChange={(e) => setQuery(e.target.value)} className="w-full bg-transparent text-sm outline-none placeholder:text-[#96938d]" placeholder="Search name, hash, or artifact ID" /></div><button onClick={() => setItems(getRecentArtifacts())} className="action-button"><RefreshCw size={13} />Refresh</button></div>
    {filtered.length ? <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--panel)]"><div className="grid grid-cols-[minmax(0,1fr)_140px_120px_110px] gap-4 border-b border-[var(--border)] bg-[var(--panel-muted)] px-5 py-3 text-[10px] font-semibold uppercase tracking-[0.13em] text-[var(--muted)]"><span>Artifact</span><span>Claimed</span><span>Status</span><span>Open</span></div>{filtered.map((item) => <div key={item.artifact_id} className="grid grid-cols-[minmax(0,1fr)_140px_120px_110px] items-center gap-4 border-b border-[var(--border)] px-5 py-4 last:border-b-0"><div className="min-w-0"><div className="truncate text-sm font-semibold">{item.original_name || '(unnamed artifact)'}</div><div className="mt-1 truncate font-mono text-[10px] text-[var(--muted)]">{item.sha256}</div></div><div className="text-xs text-[var(--muted)]">{item.claimed_extension || '—'}</div><div className="text-xs">{item.status}</div><Link href={`/artifacts/${item.artifact_id}`} className="text-xs font-semibold text-[var(--cobalt)] hover:underline">Inspect →</Link></div>)}</div> : items.length ? <EmptyState title="No matching artifacts" description="Try a different filename, hash, or artifact ID." /> : <EmptyState title="No artifacts in this browser" description="Upload an artifact to create a real record. The current backend does not provide a global artifact-list endpoint." action={<UploadArtifactButton compact />} />}
  </div></AppShell>;
}
