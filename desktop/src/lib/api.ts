import { invoke } from '@tauri-apps/api/core';

export type ScanResult = {
  path: string;
  name: string;
  extension: string;
  size_bytes: number;
  sha256: string;
  declared_type: string;
  detected_type: string;
  entropy: number;
  markers: string[];
  status: 'CLEAR' | 'REVIEW' | 'QUARANTINED' | 'ERROR';
  reason?: string;
  risk_score: number;
  risk_factors: string[];
  scanned_at: string;
};

export type HistoryItem = ScanResult & { id: string };

export type QuarantineItem = {
  id: string;
  name: string;
  original_path: string;
  quarantined_path: string;
  sha256: string;
  risk_score: number;
  risk_factors: string[];
  declared_type: string;
  detected_type: string;
  size_bytes: number;
  quarantined_at: string;
  scan_status: string;
};

export type BatchScanResult = {
  directory: string;
  scanned: number;
  review: number;
  clear: number;
  failed: number;
};

export const scanFile = (path: string) => invoke<ScanResult>('scan_file', { path });
export const scanDirectory = (path: string) => invoke<BatchScanResult>('scan_directory', { path });
export const scanWatchedFolder = (path: string) => invoke<BatchScanResult>('scan_watched_folder', { path });
export const pickFile = () => invoke<string | null>('pick_file');
export const pickFolder = () => invoke<string | null>('pick_folder');
export const quarantineFile = (path: string) => invoke<QuarantineItem>('quarantine_file', { path });
export const restoreQuarantine = (id: string) => invoke<string>('restore_quarantine', { id });
export const revealFile = (path: string) => invoke<void>('reveal_file', { path });
export const openQuarantineFolder = () => invoke<string>('open_quarantine_folder');
export const getHistory = () => invoke<HistoryItem[]>('get_history');
export const clearHistory = () => invoke<void>('clear_history');
export const addWatch = (path: string) => invoke<void>('add_watch', { path });
export const removeWatch = (path: string) => invoke<void>('remove_watch', { path });
export const getWatches = () => invoke<string[]>('get_watches');
export const getQuarantine = () => invoke<QuarantineItem[]>('get_quarantine');
export const getSettings = () => invoke<{ api_url: string; quarantine_dir: string; max_file_mb: number }>('get_settings');
export const setApiUrl = (apiUrl: string) => invoke<void>('set_api_url', { apiUrl });
export const handoffArtifact = (path: string, apiUrl: string) => invoke<{ artifact_id: string; message: string }>('handoff_artifact', { path, apiUrl });

export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

export const backendRequest = (apiUrl: string, path: string, method = 'GET', body?: unknown) =>
  invoke<JsonValue>('backend_request', { apiUrl, path, method, body: body === undefined ? null : JSON.stringify(body) });

export const getHealth = (apiUrl: string) => backendRequest(apiUrl, '/health');
export const getRemoteArtifact = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}`);
export const runRemoteFastScan = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}/fastscan`, 'POST');
export const getRemoteFastScan = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}/fastscan`);
export const runRemoteInterpret = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}/interpret`, 'POST');
export const getRemoteInterpretation = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}/interpretation`);
export const runRemoteGraph = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}/graph`, 'POST');
export const getRemoteGraph = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}/graph`);
export const getRemoteFractures = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}/fractures`);
export const startRemoteLab = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}/lab`, 'POST');
export const getRemoteInvestigation = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/investigations/${encodeURIComponent(id)}`);
export const getRemotePassport = (apiUrl: string, id: string) => backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}/passport`);
export const getImmuneMemory = (apiUrl: string) => backendRequest(apiUrl, '/api/immune-memory');
