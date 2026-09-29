import { AppShell } from '@/components/app-shell';
import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';

export default function ExperimentsPage() {
  return <AppShell><div className="mx-auto max-w-[1640px] px-6 py-7"><PageHeader eyebrow="Investigation" title="Experiments" description="Controlled semantic mutations, parser reruns, sandbox results, and validation history." /><EmptyState title="No experiments" description="Experiments are created inside a Lab investigation and recorded by the PRISM backend." /></div></AppShell>;
}
