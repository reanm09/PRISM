import type { Artifact } from './types';

const STORAGE_KEY = 'prism_recent_artifacts';
const MAX_ITEMS = 30;

export function getRecentArtifacts(): Artifact[] {
  if (typeof window === 'undefined') return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '[]');
    return Array.isArray(parsed) ? (parsed as Artifact[]) : [];
  } catch {
    return [];
  }
}

export function rememberArtifact(artifact: Artifact) {
  if (typeof window === 'undefined') return;
  const existing = getRecentArtifacts().filter((item) => item.artifact_id !== artifact.artifact_id);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify([artifact, ...existing].slice(0, MAX_ITEMS)));
}
