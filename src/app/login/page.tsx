'use client';

import Image from 'next/image';
import Link from 'next/link';
import { Suspense, useState } from 'react';
import { Eye, EyeOff, LockKeyhole, Mail, ShieldCheck } from 'lucide-react';
import { getSupabaseBrowserClient } from '@/lib/supabase/client';
import { setDemoSession } from '@/lib/demo-auth';

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  // The sign-in screen renders before credentials are supplied, but it never invents a client session.
  const searchParams = new URLSearchParams(typeof window !== 'undefined' ? window.location.search : '');
  const next = searchParams.get('next')?.startsWith('/') ? searchParams.get('next')! : '/';
  const queryError = searchParams.get('error');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(queryError);

  async function continueWithGoogle() {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      setBusy(true);
      setMessage(null);
      window.setTimeout(() => {
        setDemoSession('google-demo@prism.local');
        window.location.assign(next);
      }, 220);
      return;
    }

    setBusy(true);
    setMessage(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`,
      },
    });

    if (error) {
      setBusy(false);
      setMessage(error.message);
    }
  }

  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const supabase = getSupabaseBrowserClient();

    if (!supabase) {
      setBusy(true);
      setMessage(null);
      window.setTimeout(() => {
        setDemoSession(email.trim() || 'demo@prism.local');
        window.location.assign(next);
      }, 220);
      return;
    }

    setBusy(true);
    setMessage(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setBusy(false);
      setMessage(error.message);
      return;
    }

    window.location.assign(next);
  }

  return (
    <main className="min-h-screen bg-[var(--background)] text-[var(--ink)]">
      <div className="grid min-h-screen lg:grid-cols-[1.08fr_0.92fr]">
        <section className="relative hidden overflow-hidden border-r border-[var(--border)] bg-[#ece7df] lg:flex">
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute left-[14%] top-[18%] h-56 w-56 rounded-full border border-[var(--cobalt)]/10" />
            <div className="absolute left-[22%] top-[27%] h-40 w-40 rounded-full border border-[var(--cobalt)]/10" />
            <div className="absolute bottom-[15%] right-[10%] h-px w-2/3 bg-[var(--cobalt)]/15" />
            <div className="absolute bottom-[22%] right-[18%] h-24 w-24 rotate-45 border border-[var(--ink)]/8" />
          </div>
          <div className="relative flex w-full flex-col justify-between p-12 xl:p-16">
            <div className="flex items-center gap-3">
              <Image src="/prism-mark.svg" alt="PRISM" width={42} height={42} className="h-10 w-10 object-contain" priority />
              <div>
                <div className="text-[19px] font-semibold tracking-[-0.04em]">PRISM</div>
                <div className="mt-0.5 text-[9px] uppercase tracking-[0.18em] text-[#7e7971]">Artifact Truth Engine</div>
              </div>
            </div>

            <div className="max-w-[610px]">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">Evidence-first security analysis</div>
              <h1 className="mt-5 max-w-xl text-[48px] font-semibold leading-[1.02] tracking-[-0.055em] xl:text-[56px]">Understand what the artifact actually is.</h1>
              <p className="mt-6 max-w-xl text-[15px] leading-7 text-[var(--muted)]">Compare independent interpretations of the same bytes, investigate meaningful differences, and preserve a traceable evidence chain.</p>
              <div className="mt-9 max-w-xl border-l-2 border-[var(--cobalt)] pl-4 text-sm leading-6 text-[#54575b]">The system treats filenames, MIME types, and individual parser output as claims — not ground truth.</div>
            </div>

            <div className="flex items-center gap-6 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#858078]">
              <span>Interpret</span>
              <span className="h-px w-8 bg-[#c8c2b8]" />
              <span>Compare</span>
              <span className="h-px w-8 bg-[#c8c2b8]" />
              <span>Validate</span>
            </div>
          </div>
        </section>

        <section className="flex min-h-screen items-center justify-center bg-[var(--panel)] px-6 py-10 sm:px-10 lg:px-16">
          <div className="w-full max-w-[420px]">
            <Link href="/" className="inline-flex items-center gap-3 lg:hidden">
              <Image src="/prism-mark.svg" alt="PRISM" width={38} height={38} className="h-9 w-9 object-contain" priority />
              <span className="text-lg font-semibold tracking-[-0.04em]">PRISM</span>
            </Link>

            <div className="mt-8 lg:mt-0">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">Workspace access</div>
              <h2 className="mt-2 text-[31px] font-semibold tracking-[-0.05em]">Welcome back</h2>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Sign in to continue to artifact analysis and investigation.</p>
            </div>

            <button type="button" onClick={continueWithGoogle} disabled={busy} className="mt-8 flex w-full items-center justify-center gap-3 rounded-md border border-[var(--border)] bg-white px-4 py-3 text-sm font-semibold shadow-[0_4px_14px_rgba(31,36,43,0.03)] transition hover:border-[#c3beb5] hover:bg-[#fdfcf9] disabled:cursor-not-allowed disabled:opacity-60">
              <GoogleMark />
              Continue with Google
            </button>

            <div className="my-7 flex items-center gap-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">
              <span className="h-px flex-1 bg-[var(--border)]" />
              <span>or</span>
              <span className="h-px flex-1 bg-[var(--border)]" />
            </div>

            <form onSubmit={signIn} className="space-y-4">
              <Field label="Email" icon={<Mail size={16} strokeWidth={1.75} />}>
                <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="email" placeholder="you@company.com" className="w-full bg-transparent text-sm outline-none placeholder:text-[#aaa69f]" />
              </Field>

              <Field label="Password" icon={<LockKeyhole size={16} strokeWidth={1.75} />} trailing={<button type="button" onClick={() => setShowPassword((value) => !value)} className="text-[var(--muted)] hover:text-[var(--ink)]" aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button>}>
                <input value={password} onChange={(event) => setPassword(event.target.value)} type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" className="w-full bg-transparent text-sm outline-none placeholder:text-[#aaa69f]" />
              </Field>

              {message ? <div className="rounded-md border border-[#e3c6c1] bg-[#fff7f5] px-3 py-2.5 text-xs leading-5 text-[#7f4e49]" role="alert">{message}</div> : null}

              <button disabled={busy} type="submit" className="w-full rounded-md bg-[var(--cobalt)] px-4 py-3 text-sm font-semibold text-white shadow-[0_7px_18px_rgba(47,99,216,0.15)] transition hover:bg-[var(--cobalt-hover)] disabled:cursor-not-allowed disabled:opacity-60">{busy ? 'Signing in…' : 'Sign in'}</button>
            </form>

            <div className="mt-8 flex items-start gap-2 text-xs leading-5 text-[var(--muted)]">
              <ShieldCheck size={15} className="mt-0.5 shrink-0 text-[var(--cobalt)]" />
              <span>Temporary workspace access is enabled for frontend development until the authentication provider is connected.</span>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function LoginFallback() {
  return <main className="grid min-h-screen place-items-center bg-[var(--background)] text-sm text-[var(--muted)]">Preparing sign-in</main>;
}

function Field({ label, icon, trailing, children }: { label: string; icon: React.ReactNode; trailing?: React.ReactNode; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-[var(--ink)]">{label}</span>
      <span className="flex min-h-11 items-center gap-2.5 rounded-md border border-[var(--border)] bg-white px-3.5 transition focus-within:border-[var(--cobalt)] focus-within:ring-2 focus-within:ring-[var(--cobalt)]/10">
        <span className="text-[var(--muted)]">{icon}</span>
        <span className="min-w-0 flex-1">{children}</span>
        {trailing}
      </span>
    </label>
  );
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M21.35 12.23c0-.7-.06-1.42-.2-2.1H12v3.97h5.21a4.45 4.45 0 0 1-1.93 2.91v2.42h3.12c1.83-1.69 2.95-4.18 2.95-7.2Z" />
      <path fill="#34A853" d="M12 21.5c2.62 0 4.82-.86 6.43-2.34l-3.12-2.42c-.87.58-1.98.92-3.31.92-2.54 0-4.69-1.72-5.46-4.02H3.33v2.5A9.71 9.71 0 0 0 12 21.5Z" />
      <path fill="#FBBC05" d="M6.54 13.64a5.83 5.83 0 0 1 0-3.28v-2.5H3.33a9.69 9.69 0 0 0 0 8.28l3.21-2.5Z" />
      <path fill="#EA4335" d="M12 6.34c1.43 0 2.72.49 3.73 1.45l2.8-2.8C16.82 3.45 14.62 2.5 12 2.5a9.7 9.7 0 0 0-8.67 5.36l3.21 2.5C7.31 8.06 9.46 6.34 12 6.34Z" />
    </svg>
  );
}
