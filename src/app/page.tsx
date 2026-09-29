'use client';

import Link from 'next/link';
import { ArrowUpRight, CheckCircle2, RefreshCw, Server, Upload } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { EmptyState, ErrorState, LoadingState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { UploadArtifactButton } from '@/components/upload-artifact-button';
import { getHealth } from '@/lib/api';
import { getRecentArtifacts } from '@/lib/recent-artifacts';
import type { Artifact } from '@/lib/types';

export default function HomePage() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false });
  const [recent, setRecent] = useState<Artifact[]>([]);
  useEffect(() => setRecent(getRecentArtifacts().slice(0, 5)), []);
  return <AppShell><div className="mx-auto max-w-[1640px] px-6 py-7">
    <PageHeader eyebrow="Sentinel" title="Overview" description="Use the connected backend to ingest an artifact, establish byte-observed identity, compare interpreters, and build its Interpretation Graph." actions={<UploadArtifactButton />} />
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
      <section className="panel-card p-5"><div className="flex items-center justify-between gap-3"><div><h2 className="section-heading">Backend connection</h2><p className="section-copy">Live response from <span className="mono">/health</span>.</p></div><button onClick={() => void health.refetch()} className="action-button" disabled={health.isFetching}><RefreshCw size={14} className={health.isFetching ? 'animate-spin' : ''} />Check</button></div><div className="mt-4">{health.isLoading ? <LoadingState label="Checking backend" /> : health.isError ? <ErrorState compact title="Backend unavailable" description={health.error instanceof Error ? health.error.message : 'Health request failed.'} /> : <div className="flex items-center gap-3 rounded-md border border-[#bfd9ca] bg-[#f2faf4] p-4"><CheckCircle2 size={18} className="text-[var(--success)]" /><div><div className="text-sm font-semibold">{health.data?.service ?? 'PRISM backend'}</div><div className="mt-0.5 text-xs text-[var(--muted)]">Status: {health.data?.status ?? '—'}</div></div></div>}</div></section>
      <section className="panel-card p-5"><div className="flex items-center gap-2"><Server size={16} className="text-[var(--cobalt)]" /><h2 className="section-heading">Current API flow</h2></div><div className="mt-4 space-y-2">{['POST /api/artifacts','POST /{id}/fastscan','POST /{id}/interpret','POST /{id}/graph'].map((step, i) => <div key={step} className="flex items-center gap-3 rounded-md border border-[var(--border)] bg-[var(--panel-muted)] px-3 py-2.5"><span className="grid h-6 w-6 place-items-center rounded-full bg-[var(--cobalt-soft)] text-[10px] font-semibold text-[var(--cobalt)]">{i+1}</span><span className="mono text-[11px]">{step}</span></div>)}</div></section>
    </div>
    <section className="panel-card mt-4 p-5"><div className="flex items-start justify-between gap-4"><div><h2 className="section-heading">Recent artifacts on this browser</h2><p className="section-copy">The backend has no global collection endpoint, so the web client keeps a local index of successful uploads.</p></div><Link href="/artifacts" className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--cobalt)]">View artifacts <ArrowUpRight size={14} /></Link></div><div className="mt-4">{recent.length ? <div className="divide-y divide-[var(--border)] rounded-md border border-[var(--border)]">{recent.map((item) => <Link key={item.artifact_id} href={`/artifacts/${item.artifact_id}`} className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-[var(--panel-muted)]"><div className="min-w-0"><div className="truncate text-sm font-semibold">{item.original_name || '(unnamed artifact)'}</div><div className="mt-0.5 truncate font-mono text-[10px] text-[var(--muted)]">{item.sha256}</div></div><span className="shrink-0 text-xs font-semibold text-[var(--cobalt)]">Open →</span></Link>)}</div> : <EmptyState title="No uploaded artifacts" description="Use Analyze Artifact to create the first real backend record." action={<UploadArtifactButton compact />} />}</div></section>
    <div className="mt-4 grid gap-4 md:grid-cols-3"><ConsoleLink icon={<Upload size={16} />} title="Intercept" href="/intercept" description="Manual intake through the backend's upload endpoint." /><ConsoleLink icon={<Server size={16} />} title="Interpretation Graph" href="/graph" description="Inspect graph data generated from real interpreter observations." /><ConsoleLink icon={<CheckCircle2 size={16} />} title="PRISM Lab" href="/lab" description="Reserved for the Lab backend contract, which this repo does not expose yet." /></div>
  </div></AppShell>;
}

function ConsoleLink({ icon, title, description, href }: { icon: React.ReactNode; title: string; description: string; href: string }) { return <Link href={href} className="panel-card block p-4 transition hover:border-[#c8c2b9]"><div className="flex items-center gap-2 text-[var(--cobalt)]">{icon}<span className="text-sm font-semibold text-[var(--ink)]">{title}</span></div><p className="mt-2 text-xs leading-5 text-[var(--muted)]">{description}</p><div className="mt-3 text-xs font-semibold text-[var(--cobalt)]">Open workspace →</div></Link>; }
