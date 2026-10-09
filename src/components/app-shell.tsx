'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ChevronRight, LogOut, Menu, PanelLeftClose, Search, UserRound, X } from 'lucide-react';
import { navigation } from '@/lib/navigation';
import { NavIcon } from './icons';
import { useEffect, useMemo, useState } from 'react';
import { UploadArtifactDialog } from './upload-artifact-dialog';
import { PrismNavigationTransition } from './prism-navigation-transition';
import { getSupabaseBrowserClient } from '@/lib/supabase/client';
import { clearDemoSession, getDemoSession } from '@/lib/demo-auth';

const sections = [
  { key: 'sentinel', label: 'Sentinel' },
  { key: 'investigation', label: 'Investigation' },
  { key: 'intelligence', label: 'Intelligence' },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [navigatingTo, setNavigatingTo] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [accountEmail, setAccountEmail] = useState<string | null>(null);

  const workspaceLabel = useMemo(() => getWorkspaceLabel(pathname), [pathname]);

  useEffect(() => {
    setMobileOpen(false);
    if (!navigatingTo) return;
    const timer = window.setTimeout(() => setNavigatingTo(null), 300);
    return () => window.clearTimeout(timer);
  }, [pathname, navigatingTo]);

  useEffect(() => {
    const demo = getDemoSession();
    if (demo.authenticated) setAccountEmail(demo.email);

    const client = getSupabaseBrowserClient();
    if (!client) return;

    let active = true;
    void client.auth.getUser().then(({ data }: { data: { user: { email?: string } | null } }) => {
      if (active) setAccountEmail(data.user?.email ?? null);
    });

    const { data: subscription } = client.auth.onAuthStateChange((_event: string, session: { user: { email?: string } } | null) => {
      setAccountEmail(session?.user?.email ?? null);
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = search.trim();
    if (!query) return;
    router.push(`/artifacts?q=${encodeURIComponent(query)}`);
  }

  async function signOut() {
    const client = getSupabaseBrowserClient();
    if (client) await client.auth.signOut();
    clearDemoSession();
    setAccountEmail(null);
    setMenuOpen(false);
    router.push('/login');
  }

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--ink)]">
      <aside className={`fixed inset-y-0 left-0 z-40 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 border-r border-[var(--border)] bg-[var(--sidebar)] transition-[width,transform] duration-200 ${collapsed ? 'w-[76px]' : 'w-[246px]'}`}>
        <div className="flex h-full flex-col">
          <div className={`flex h-[72px] items-center justify-between border-b border-[var(--border)] ${collapsed ? 'justify-center px-3' : 'px-5'}`}>
            <Link href="/" className="flex items-center gap-3" aria-label="PRISM overview">
              <PrismMark collapsed={collapsed} />
              {!collapsed ? (
                <div>
                  <div className="text-[18px] font-semibold tracking-[-0.035em]">PRISM</div>
                  <div className="mt-0.5 text-[9px] uppercase tracking-[0.18em] text-[#8b8881]">Artifact Truth Engine</div>
                </div>
              ) : null}
            </Link>
            <button onClick={() => setMobileOpen(false)} className="grid h-8 w-8 place-items-center rounded-md text-[var(--muted)] hover:bg-[#e8e4dd] lg:hidden" aria-label="Close navigation"><X size={16} /></button>
          </div>

          <nav className="prism-scroll flex-1 overflow-y-auto px-3 py-5" aria-label="Primary navigation">
            {sections.map((section) => {
              const items = navigation.filter((item) => item.section === section.key);
              return (
                <div key={section.key} className="mb-7">
                  {!collapsed ? <div className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#87837b]">{section.label}</div> : null}
                  <div className="space-y-1">
                    {items.map((item) => {
                      const active = item.href === '/' ? pathname === '/' : pathname === item.href || pathname.startsWith(`${item.href}/`);
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={`group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-[13px] transition ${active ? 'bg-[var(--cobalt-soft)] text-[var(--cobalt)]' : 'text-[#575b63] hover:bg-[#e8e4dd] hover:text-[var(--ink)]'}`}
                          title={collapsed ? item.label : undefined}
                          onClick={(event) => {
                            if (active || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                            event.preventDefault();
                            setNavigatingTo(item.href);
                            window.requestAnimationFrame(() => router.push(item.href));
                          }}
                        >
                          {active ? <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-[var(--cobalt)]" aria-hidden="true" /> : null}
                          <NavIcon name={item.icon as never} />
                          {!collapsed ? <span>{item.label}</span> : null}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </nav>

          <div className="border-t border-[var(--border)] p-3">
            {accountEmail ? (
              <div className="mb-2 rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2.5">
                {!collapsed ? <div className="truncate text-[11px] text-[var(--muted)]">Workspace</div> : null}
                <div className={`truncate text-xs font-medium ${collapsed ? 'text-center' : 'mt-0.5'}`}>{collapsed ? accountEmail.slice(0, 1).toUpperCase() : accountEmail}</div>
              </div>
            ) : null}
            <button onClick={() => setCollapsed((value) => !value)} className="flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-xs text-[#77736d] transition hover:bg-[#e8e4dd] hover:text-[var(--ink)]" title={collapsed ? 'Expand navigation' : 'Collapse navigation'}>
              <PanelLeftClose size={16} className={`transition ${collapsed ? 'rotate-180' : ''}`} />
              {!collapsed ? 'Collapse' : null}
            </button>
          </div>
        </div>
      </aside>

      <div className={collapsed ? 'pl-0 lg:pl-[76px] transition-[padding] duration-200' : 'pl-0 lg:pl-[246px] transition-[padding] duration-200'}>
        <header className="sticky top-0 z-20 flex min-h-[72px] items-center gap-5 border-b border-[var(--border)] bg-[rgba(247,245,241,0.94)] px-6 backdrop-blur">
          <button onClick={() => setMobileOpen(true)} className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-[var(--border)] bg-[var(--panel)] text-[var(--muted)] lg:hidden" aria-label="Open navigation"><Menu size={18} /></button>
          <div className="hidden min-w-0 items-center gap-2 text-xs text-[var(--muted)] md:flex">
            <span>PRISM</span>
            <ChevronRight size={13} />
            <span className="truncate font-medium text-[var(--ink)]">{workspaceLabel}</span>
          </div>

          <div className="ml-auto flex min-w-0 items-center gap-2.5">
            <form onSubmit={submitSearch} className="hidden w-[380px] items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2.5 text-sm text-[var(--muted)] lg:flex">
              <Search size={16} strokeWidth={1.7} />
              <input value={search} onChange={(event) => setSearch(event.target.value)} className="w-full bg-transparent outline-none placeholder:text-[#9b9891]" placeholder="Search artifacts, hashes, or analysis IDs" aria-label="Search PRISM" />
              <kbd className="hidden rounded border border-[var(--border)] bg-[var(--panel-muted)] px-1.5 py-0.5 text-[9px] text-[var(--muted)] xl:inline">Enter</kbd>
            </form>

            <div className="relative">
              <button onClick={() => setMenuOpen((value) => !value)} className="grid h-10 w-10 place-items-center rounded-md border border-[var(--border)] bg-[var(--panel)] text-[var(--muted)] transition hover:border-[#c6c0b8] hover:text-[var(--ink)]" aria-label="Account menu" aria-expanded={menuOpen}>
                <UserRound size={16} strokeWidth={1.7} />
              </button>
              {menuOpen ? (
                <div className="absolute right-0 top-12 z-40 w-60 rounded-lg border border-[var(--border)] bg-[var(--panel)] p-2 shadow-[0_20px_50px_rgba(31,36,43,0.12)]">
                  {accountEmail ? <div className="px-2.5 py-2 text-xs text-[var(--muted)]">{accountEmail}</div> : <Link href="/login" onClick={() => setMenuOpen(false)} className="block rounded-md px-2.5 py-2 text-sm hover:bg-[var(--panel-muted)]">Sign in</Link>}
                  {accountEmail ? <button onClick={signOut} className="mt-1 flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm text-[#6d5653] hover:bg-[#fff5f3]"><LogOut size={15} />Sign out</button> : null}
                </div>
              ) : null}
            </div>

            <button onClick={() => setUploadOpen(true)} className="rounded-md bg-[var(--cobalt)] px-3.5 py-2.5 text-sm font-semibold text-white shadow-[0_6px_18px_rgba(49,95,218,0.14)] transition hover:bg-[var(--cobalt-hover)]">Analyze Artifact</button>
          </div>
        </header>

        <main>{children}</main>
      </div>

      {mobileOpen ? <button className="fixed inset-0 z-30 bg-black/10 lg:hidden" aria-label="Close navigation" onClick={() => setMobileOpen(false)} /> : null}
      <UploadArtifactDialog open={uploadOpen} onClose={() => setUploadOpen(false)} />
      <PrismNavigationTransition active={Boolean(navigatingTo)} />
    </div>
  );
}

function PrismMark({ collapsed }: { collapsed: boolean }) {
  return (
    <div className={`relative grid place-items-center overflow-hidden ${collapsed ? 'h-8 w-8' : 'h-10 w-10'}`} aria-hidden="true">
      <Image src="/prism-mark.svg" alt="" width={44} height={44} priority className={`${collapsed ? 'h-7 w-7' : 'h-9 w-9'} object-contain`} />
    </div>
  );
}

function getWorkspaceLabel(pathname: string) {
  if (pathname === '/') return 'Overview';
  if (pathname.startsWith('/artifacts/')) return 'Artifact Analysis';
  const exact: Record<string, string> = {
    '/intercept': 'Intercept',
    '/artifacts': 'Artifacts',
    '/fractures': 'Semantic Fractures',
    '/graph': 'Interpretation Graph',
    '/lab': 'PRISM Lab',
    '/experiments': 'Experiments',
    '/passports': 'Artifact Passports',
    '/capabilities': 'Capability Graph',
    '/immune-memory': 'Immune Memory',
  };
  return exact[pathname] ?? 'Workspace';
}
