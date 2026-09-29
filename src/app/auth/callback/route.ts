import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get('code');
  const next = sanitizeNext(requestUrl.searchParams.get('next'));

  if (!code) {
    return NextResponse.redirect(new URL(`/login?error=${encodeURIComponent('Authentication callback was missing a code.')}`, requestUrl.origin));
  }

  const cookieStore = await cookies();
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.redirect(new URL('/login?error=Authentication+is+not+configured', requestUrl.origin));
  }

  const supabase = createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value, options }) => {
          cookieStore.set(name, value, options);
        });
      },
    },
  });

  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(new URL(`/login?error=${encodeURIComponent(error.message)}`, requestUrl.origin));
  }

  return NextResponse.redirect(new URL(next, requestUrl.origin));
}

function sanitizeNext(value: string | null) {
  return value && value.startsWith('/') && !value.startsWith('//') ? value : '/';
}
