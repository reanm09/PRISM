'use client';

import Link from 'next/link';
import { ArrowRight, Inbox, UploadCloud } from 'lucide-react';
import { useEffect, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { UploadArtifactButton } from '@/components/upload-artifact-button';
import { getRecentArtifacts } from '@/lib/recent-artifacts';
import type { Artifact } from '@/lib/types';

export default function InterceptPage() {
  const [recent, setRecent] = useState<Artifact[]>([]);
  useEffect(() => setRecent(getRecentArtifacts().slice(0, 8)), []);
  return <AppShell><div className="mx-auto max-w-[1640px] px-6 py-7"><PageHeader eyebrow="Sentinel" title="Intercept" description="The supplied backend currently exposes manual artifact ingestion rather than a native endpoint watcher." actions={<UploadArtifactButton />} /><section className="panel-card p-5"><div className="grid gap-3 md:grid-cols-3"><InfoCard icon={<Inbox size={17} />} title="Manual intake" text="POST /api/artifacts accepts the uploaded file bytes." /><InfoCard icon={<UploadCloud size={17} />} title="Ingestion evidence" text="The backend calculates SHA-256 and records the claimed extension." /><InfoCard icon={<ArrowRight size={17} />} title="Analysis handoff" text="Open the artifact workspace to trigger FastScan and interpretation." /></div></section><section className="mt-4">{recent.length ? <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--panel)]">{recent.map((item) => <Link key={item.artifact_id} href={`/artifacts/${item.artifact_id}`} className="flex items-center justify-between gap-4 border-b border-[var(--border)] px-5 py-4 last:border-b-0 hover:bg-[var(--panel-muted)]"><div className="min-w-0"><div className="truncate text-sm font-semibold">{item.original_name}</div><div className="mt-1 truncate font-mono text-[10px] text-[var(--muted)]">{item.artifact_id}</div></div><span className="text-xs font-semibold text-[var(--cobalt)]">Inspect →</span></Link>)}</div> : <EmptyState title="No intercepted artifacts" description="Use Analyze Artifact to create the first intake record." action={<UploadArtifactButton compact />} />}</section></div></AppShell>;
}
function InfoCard({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) { return <div className="rounded-md border border-[var(--border)] bg-[var(--panel-muted)] p-4"><div className="text-[var(--cobalt)]">{icon}</div><div className="mt-3 text-sm font-semibold">{title}</div><div className="mt-1 text-xs leading-5 text-[var(--muted)]">{text}</div></div>; }
