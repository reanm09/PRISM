const API_BASE = (process.env.NEXT_PUBLIC_PRISM_API_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');

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

export function getLocalStatus() {
  return prismFetch<Record<'backend' | 'ollama' | 'laya' | 'rag' | 'lab', string>>('/api/local/status');
}

export function analyzeArtifact(artifactId: string) {
  return prismFetch<import('./types').PrismAnalysis>(`/api/artifacts/${artifactId}/analyze`, { method: 'POST' });
}

export function reasonArtifact(artifactId: string) {
  return prismFetch<import('./types').SemanticReasoningResult>(`/api/artifacts/${artifactId}/reason`, { method: 'POST' });
}

export function investigateArtifact(artifactId: string) {
  return prismFetch<import('./types').AutonomousInvestigationResult>(`/api/artifacts/${artifactId}/investigate`, { method: 'POST' });
}

export function getSentinelStatus() {
  return prismFetch<import('./types').SentinelStatus>('/api/sentinel/status');
}

export function getSentinelWatchRoots() {
  return prismFetch<import('./types').SentinelWatchRoot[]>('/api/sentinel/watch-roots');
}

export function getRecentSentinelEvents() {
  return prismFetch<import('./types').SentinelEvent[]>('/api/sentinel/events/recent');
}

export function sentinelEventsUrl() {
  return `${API_BASE}/api/sentinel/events`;
}

export function getArtifactQuarantine(artifactId: string) {
  return prismFetch<import('./types').QuarantineRecord>(`/api/quarantine/artifact/${artifactId}`);
}

export function restoreQuarantine(quarantineId: string) {
  return prismFetch<import('./types').QuarantineRecord>(`/api/quarantine/${quarantineId}/restore`, { method: 'POST' });
}
