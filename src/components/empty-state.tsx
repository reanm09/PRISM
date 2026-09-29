import { FileSearch, Info, LoaderCircle, TriangleAlert } from 'lucide-react';

export function EmptyState({ title, description, action, compact = false }: { title: string; description: string; action?: React.ReactNode; compact?: boolean }) {
  return (
    <div className={`flex ${compact ? 'min-h-[190px]' : 'min-h-[280px]'} flex-col items-center justify-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--panel-muted)] px-6 text-center`}>
      <div className="mb-4 grid h-11 w-11 place-items-center rounded-lg border border-[var(--border)] bg-[var(--panel)] text-[var(--muted)] shadow-[0_3px_12px_rgba(31,36,43,0.03)]">
        <FileSearch size={19} strokeWidth={1.65} />
      </div>
      <h3 className="text-sm font-semibold text-[var(--ink)]">{title}</h3>
      <p className="mt-1 max-w-lg text-sm leading-6 text-[var(--muted)]">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex min-h-[220px] items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--panel)] text-sm text-[var(--muted)] shadow-[0_4px_16px_rgba(31,36,43,0.025)]">
      <div className="flex items-center gap-2"><LoaderCircle size={16} className="animate-spin" />{label}</div>
    </div>
  );
}

export function ErrorState({ title = 'Unable to load', description, action }: { title?: string; description: string; action?: React.ReactNode }) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-[#e6c7c4] bg-[#fff8f7] px-6 text-center">
      <TriangleAlert size={20} className="text-[var(--danger)]" />
      <h3 className="mt-3 text-sm font-semibold">{title}</h3>
      <p className="mt-1 max-w-lg text-sm leading-6 text-[#7f4b47]">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function NoDataNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-[var(--border)] bg-[var(--panel-muted)] px-3 py-2.5 text-xs leading-5 text-[var(--muted)]">
      <Info size={14} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
