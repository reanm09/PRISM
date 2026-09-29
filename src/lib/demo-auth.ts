const SESSION_KEY = 'prism_demo_session';
const EMAIL_KEY = 'prism_demo_email';

export function setDemoSession(email = 'demo@prism.local') {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(SESSION_KEY, '1');
  window.localStorage.setItem(EMAIL_KEY, email);
}

export function clearDemoSession() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(SESSION_KEY);
  window.localStorage.removeItem(EMAIL_KEY);
}

export function getDemoSession() {
  if (typeof window === 'undefined') return { authenticated: false, email: null as string | null };
  return {
    authenticated: window.localStorage.getItem(SESSION_KEY) === '1',
    email: window.localStorage.getItem(EMAIL_KEY),
  };
}
