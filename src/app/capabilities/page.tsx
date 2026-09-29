import { AppShell } from '@/components/app-shell';
import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';

export default function CapabilitiesPage() {
  return <AppShell><div className="mx-auto max-w-[1640px] px-6 py-7"><PageHeader eyebrow="Intelligence" title="Capability Graph" description="Model what an artifact can expose or cause different consumers to interpret or execute." /><div className="panel-card p-4"><div className="grid-paper min-h-[560px] rounded-md border border-[var(--border)]"><EmptyState title="No capability graph" description="Capability nodes are derived from observed artifact interpretations and validated findings." /></div></div></div></AppShell>;
}
