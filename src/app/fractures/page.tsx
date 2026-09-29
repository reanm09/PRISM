'use client';

import Link from 'next/link';
import { TriangleAlert } from 'lucide-react';
import { useEffect, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { getRecentArtifacts } from '@/lib/recent-artifacts';
import type { Artifact } from '@/lib/types';

export default function FracturesPage() {
  const [recent, setRecent] = useState<Artifact[]>([]);
  useEffect(() => setRecent(getRecentArtifacts()), []);
  return <AppShell><div className="mx-auto max-w-[1640px] px-6 py-7"><PageHeader eyebrow="Sentinel" title="Semantic Fractures" description="The supplied backend does not have a separate fracture entity. It currently exposes disagreement signals from the interpreter comparison, which are shown inside each artifact workspace." />{recent.length ? <div className="grid gap-3">{recent.map((item) => <Link key={item.artifact_id} href={`/artifacts/${item.artifact_id}#interpretations`} className="panel-card flex items-center justify-between gap-4 px-5 py-4 hover:border-[#c8c2b9]"><div className="flex min-w-0 items-center gap-3"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-[#ead8cf] bg-[#fff8f5] text-[#8d4b3d]"><TriangleAlert size={16} /></div><div className="min-w-0"><div className="truncate text-sm font-semibold">{item.original_name}</div><div className="mt-1 truncate font-mono text-[10px] text-[var(--muted)]">{item.artifact_id}</div></div></div><span className="shrink-0 text-xs font-semibold text-[var(--cobalt)]">Inspect signals →</span></Link>)}</div> : <EmptyState title="No artifacts available" description="Upload an artifact and run the interpreter comparison to produce disagreement signals." />}</div></AppShell>;
}
