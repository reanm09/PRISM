export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-5 border-b border-[var(--border)] pb-5">
      <div className="min-w-0">
        {eyebrow ? <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">{eyebrow}</div> : null}
        <h1 className="text-[31px] font-semibold tracking-[-0.045em] text-[var(--ink)]">{title}</h1>
        {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
