const API_BASE = (process.env.NEXT_PUBLIC_PRISM_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export class PrismApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'PrismApiError';
    this.status = status;
  }
}

export async function prismFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    let message = `PRISM API returned ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') message = body.detail;
      else message = JSON.stringify(body);
    } catch {
      const text = await response.text().catch(() => '');
      if (text) message = text;
    }
    throw new PrismApiError(response.status, message);
  }

  return response.json() as Promise<T>;
}

export async function uploadArtifact(file: File) {
  const form = new FormData();
  form.append('file', file);
  return prismFetch<import('./types').Artifact>('/api/artifacts', {
    method: 'POST',
    body: form,
    headers: {},
  });
}

export function getArtifact(artifactId: string) {
  return prismFetch<import('./types').Artifact>(`/api/artifacts/${artifactId}`);
}

export function getFastScan(artifactId: string) {
  return prismFetch<import('./types').FastScanResult>(`/api/artifacts/${artifactId}/fastscan`);
}

export function runFastScan(artifactId: string) {
  return prismFetch<import('./types').FastScanResult>(`/api/artifacts/${artifactId}/fastscan`, { method: 'POST' });
}

export function getInterpretation(artifactId: string) {
  return prismFetch<import('./types').InterpretationResult>(`/api/artifacts/${artifactId}/interpretation`);
}

export function runInterpretation(artifactId: string) {
  return prismFetch<import('./types').InterpretationResult>(`/api/artifacts/${artifactId}/interpret`, { method: 'POST' });
}

export function getGraph(artifactId: string) {
  return prismFetch<import('./types').InterpretationGraph>(`/api/artifacts/${artifactId}/graph`);
}

export function buildGraph(artifactId: string) {
  return prismFetch<import('./types').InterpretationGraph>(`/api/artifacts/${artifactId}/graph`, { method: 'POST' });
}

export function getHealth() {
  return prismFetch<{ status: string; service: string }>('/health');
}
