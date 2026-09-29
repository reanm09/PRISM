import { DatabaseZap } from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';

export default function ImmuneMemoryPage() {
  return <AppShell><div className="mx-auto max-w-[1640px] px-6 py-7"><PageHeader eyebrow="Intelligence" title="Immune Memory" description="Verified findings, regression fixtures, minimized reproducers, and reusable investigation knowledge." /><div className="panel-card p-6"><EmptyState title="Memory backend not exposed" description="The supplied backend currently exposes artifact ingestion, FastScan, interpreter comparison, and Interpretation Graph endpoints only. There is no /api/immune-memory endpoint in this repository." action={<div className="inline-flex items-center gap-2 text-xs text-[var(--muted)]"><DatabaseZap size={15} />Waiting for the memory service contract</div>} /></div></div></AppShell>;
}
