import { AppShell } from '@/components/app-shell';
import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';

export default function PassportsPage() {
  return <AppShell><div className="mx-auto max-w-[1640px] px-6 py-7"><PageHeader eyebrow="Intelligence" title="Artifact Passports" description="Human-readable and machine-readable records of identity, structure, capabilities, behavior, and evidence." /><EmptyState title="No passports" description="A passport is generated after a completed investigation has enough validated evidence to produce one." /></div></AppShell>;
}
