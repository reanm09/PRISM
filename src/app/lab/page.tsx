import { FlaskConical, Layers3, MessageSquareText } from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';

export default function LabPage() {
  return (
    <AppShell>
      <div className="mx-auto max-w-[1640px] px-6 py-7">
        <PageHeader eyebrow="Investigation" title="PRISM Lab" description="Evidence-grounded investigation: observe, hypothesize, experiment, validate, and minimize." />
        <div className="grid gap-4 xl:grid-cols-[270px_minmax(0,1fr)_330px]">
          <Panel icon={<Layers3 size={16} />} title="Evidence"><EmptyState compact title="No evidence" description="Select an artifact investigation to load FastScan, parser, sandbox, and retrieved knowledge evidence." /></Panel>
          <Panel icon={<FlaskConical size={16} />} title="Investigation"><EmptyState compact title="No investigation selected" description="A Lab workspace opens when an artifact is escalated for deeper investigation." /></Panel>
          <Panel icon={<MessageSquareText size={16} />} title="Reasoning"><EmptyState compact title="No hypotheses" description="Hypotheses appear after a Lab investigation has collected enough evidence to reason from." /></Panel>
        </div>
        <section className="panel-card mt-4 p-4">
          <div className="flex items-center justify-between"><div><div className="section-heading">Investigation lifecycle</div><div className="section-copy">The Lab follows the evidence loop rather than a generic chat workflow.</div></div></div>
          <div className="mt-4 grid gap-2 md:grid-cols-6">
            {['Observe', 'Hypothesize', 'Experiment', 'Execute', 'Validate', 'Minimize'].map((step, index) => <div key={step} className="rounded-md border border-[var(--border)] bg-[var(--panel-muted)] px-3 py-3"><div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">0{index + 1}</div><div className="mt-1 text-sm font-medium">{step}</div></div>)}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function Panel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <section className="panel-card p-4"><div className="mb-3 flex items-center gap-2 text-sm font-semibold"><span className="text-[var(--cobalt)]">{icon}</span>{title}</div>{children}</section>;
}
