'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getArtifactQuarantine, PrismApiError, restoreQuarantine } from '@/lib/api';
import { useState } from 'react';

export function QuarantineStatus({ artifactId }: { artifactId: string }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['quarantine', artifactId], queryFn: () => getArtifactQuarantine(artifactId), retry: false, refetchInterval: 3000 });
  const [error, setError] = useState<string | null>(null);
  if (query.error instanceof PrismApiError && query.error.status === 404) return null;
  const record = query.data;
  if (!record) return null;
  async function restore() {
    if (!record) return;
    setError(null);
    try { await restoreQuarantine(record.quarantine_id); await client.invalidateQueries({ queryKey: ['quarantine', artifactId] }); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Restore failed'); }
  }
  return <section className="panel-card mt-4 border-amber-300 p-5"><h2 className="text-lg font-semibold">{record.status === 'QUARANTINED' ? 'QUARANTINED' : 'RESTORED'}</h2><div className="mt-3 grid gap-2 text-sm sm:grid-cols-2"><p>Trigger: {record.trigger === 'LAYA_SUSPICIOUS' ? 'Laya SUSPICIOUS (precautionary)' : 'Deterministic SUSPICIOUS'}</p><p>Model confidence: {record.laya_confidence === null ? '—' : `${Math.round(record.laya_confidence * 100)}%`}</p><p>Deterministic state: {record.verified_state ?? 'No deterministic verified state'}</p><p>Container: {record.container_name}</p></div><p className="mt-2 text-xs text-[var(--muted)]">{record.trigger === 'LAYA_SUSPICIOUS' ? 'This artifact was contained as a precaution based on model triage.' : 'Containment followed deterministic security evidence.'}</p>{record.reason_codes.length ? <p className="mt-2 text-xs">Verified reasons: {record.reason_codes.join(', ')}</p> : null}{record.status === 'QUARANTINED' ? <button className="action-button mt-3" onClick={() => void restore()}>Restore original file</button> : null}{error ? <p className="mt-2 text-xs text-[var(--danger)]">{error}</p> : null}</section>;
}
