import React, { useEffect, useMemo, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { listen } from '@tauri-apps/api/event';
import {
  Activity, ArchiveRestore, ArrowRight, BookOpenCheck, BrainCircuit, CheckCircle2, ChevronRight,
  CircleAlert, CloudUpload, Code2, Database, FileArchive, FileSearch, FolderOpen, FolderSearch2,
  GitCompareArrows, HardDrive, History, Inbox, LayoutDashboard, Link2, LockKeyhole, Network,
  Radar, Radio, RefreshCw, RotateCcw, ScanLine, Search, Settings, ShieldCheck, ShieldEllipsis,
  ShieldQuestion, SlidersHorizontal, TerminalSquare, Trash2, Unplug, UploadCloud, X
} from 'lucide-react';
import './styles.css';
import prismLogo from './assets/prism-logo.png';
import {
  addWatch, clearHistory, getHealth, getHistory, getImmuneMemory, getQuarantine, getBackendQuarantine, getSentinelStatus, getSentinelWatchRoots, getSentinelEvents, getRemoteArtifact,
  getRemoteFastScan, getRemoteFractures, getRemoteGraph, getRemoteInterpretation, getRemoteInvestigation,
  getRemotePassport, getSettings, getWatches, handoffArtifact, openQuarantineFolder, pickFile, pickFolder,
  backendRequest, removeWatch, restoreQuarantine, restoreBackendQuarantine, revealFile, runRemoteAnalyze, runRemoteReason, runRemoteInvestigation, runRemoteFastScan, runRemoteGraph,
  runRemoteInterpret, scanDirectory, scanFile, scanWatchedFolder, setApiUrl,
  type BackendQuarantineItem, type BatchScanResult, type HistoryItem, type JsonValue, type QuarantineItem, type ScanResult
} from './lib/api';

type View =
  | 'overview' | 'intercept' | 'artifacts' | 'fractures' | 'review' | 'scan' | 'watch' | 'quarantine' | 'history'
  | 'graph' | 'lab' | 'experiments' | 'evidence' | 'compare' | 'passports' | 'capability' | 'immune'
  | 'local' | 'policies' | 'settings';

type DetectedEvent = { path: string; name: string; reason?: string; risk_score?: number };
type RemotePane = { title: string; body: JsonValue | null; loading?: boolean; error?: string };

const sections = [
  { group: 'SENTINEL', items: [
    ['overview', 'Overview', LayoutDashboard], ['intercept', 'Intercept', Radar], ['artifacts', 'Artifacts', FileArchive],
    ['fractures', 'Fractures', CircleAlert], ['review', 'Review Queue', Inbox], ['scan', 'Scan', ScanLine],
    ['watch', 'Watch Locations', Radio], ['quarantine', 'Quarantine', ArchiveRestore], ['history', 'History', History],
  ] as const },
  { group: 'INVESTIGATION', items: [
    ['graph', 'Interpretation Graph', Network], ['lab', 'PRISM Lab', BrainCircuit], ['experiments', 'Experiments', TerminalSquare],
    ['evidence', 'Evidence', Search], ['compare', 'Comparisons', GitCompareArrows],
  ] as const },
  { group: 'INTELLIGENCE', items: [
    ['passports', 'Artifact Passports', BookOpenCheck], ['capability', 'Capability Graph', Link2], ['immune', 'Immune Memory', Database],
  ] as const },
  { group: 'ENDPOINT', items: [
    ['local', 'Local Files', FolderOpen], ['policies', 'Policies', LockKeyhole],
  ] as const },
];

function titleFor(view: View) {
  const found = sections.flatMap(s => s.items as readonly (readonly [View, string, React.ComponentType<any>])[]).find(x => x[0] === view);
  return found?.[1] ?? 'Settings';
}

function formatBytes(n: number) {
  if (!Number.isFinite(n)) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(1)} GB`;
}

function timeAgo(value: string) {
  const stamp = value.startsWith('unix:') ? Number(value.slice(5)) * 1000 : new Date(value).getTime();
  if (!Number.isFinite(stamp)) return value || 'unknown';
  const m = Math.floor(Math.max(0, Date.now() - stamp) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function riskLabel(score: number) { return score >= 70 ? 'HIGH' : score >= 40 ? 'ELEVATED' : score >= 15 ? 'LOW' : 'MINIMAL'; }
function isObject(value: JsonValue): value is Record<string, JsonValue> { return typeof value === 'object' && value !== null && !Array.isArray(value); }

function App() {
  const [view, setView] = useState<View>('overview');
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [watches, setWatches] = useState<string[]>([]);
  const [quarantine, setQuarantine] = useState<QuarantineItem[]>([]);
  const [backendQuarantine, setBackendQuarantine] = useState<BackendQuarantineItem[]>([]);
  const [selectedBackendQ, setSelectedBackendQ] = useState<BackendQuarantineItem | null>(null);
  const [sentinelState, setSentinelState] = useState<JsonValue | null>(null);
  const [sentinelRoots, setSentinelRoots] = useState<JsonValue[]>([]);
  const [sentinelEvents, setSentinelEvents] = useState<JsonValue[]>([]);
  const [review, setReview] = useState<DetectedEvent[]>([]);
  const [selected, setSelected] = useState<ScanResult | null>(null);
  const [selectedQ, setSelectedQ] = useState<QuarantineItem | null>(null);
  const [apiUrl, setApiUrlState] = useState('http://127.0.0.1:8000');
  const [quarantineDir, setQuarantineDir] = useState<string | undefined>();
  const [apiConnected, setApiConnected] = useState(false);
  const [remoteId, setRemoteId] = useState<string | null>(null);
  const [remoteArtifact, setRemoteArtifact] = useState<RemotePane>({ title: 'Artifact record', body: null });
  const [remotePane, setRemotePane] = useState<RemotePane>({ title: '', body: null });
  const [immuneMemory, setImmuneMemory] = useState<RemotePane>({ title: 'Immune Memory', body: null });
  const [busy, setBusy] = useState(false);
  const [batch, setBatch] = useState<BatchScanResult | null>(null);
  const [statusMessage, setStatusMessage] = useState('Local Sentinel ready. Only locally observed telemetry is shown.');

  const refresh = async () => {
    const [h, w, q, s] = await Promise.all([getHistory(), getWatches(), getQuarantine(), getSettings()]);
    setHistory(h); setWatches(w); setQuarantine(q); setApiUrlState(s.api_url); setQuarantineDir(s.quarantine_dir);
  };

  const checkBackend = async (url = apiUrl) => {
    try { await getHealth(url); setApiConnected(true); return true; }
    catch { setApiConnected(false); return false; }
  };

  const refreshBackend = async (url = apiUrl) => {
    try {
      const [q, status, roots, events] = await Promise.all([
        getBackendQuarantine(url), getSentinelStatus(url), getSentinelWatchRoots(url), getSentinelEvents(url),
      ]);
      setBackendQuarantine(q);
      setSelectedBackendQ(current => q.find(item => item.quarantine_id === current?.quarantine_id) ?? null);
      setSentinelState(status);
      setSentinelRoots(Array.isArray(roots) ? roots : []);
      setSentinelEvents(Array.isArray(events) ? events : []);
      setApiConnected(true);
    } catch { setApiConnected(false); }
  };

  useEffect(() => {
    refresh().catch(() => setStatusMessage('Sentinel started, but local state could not be fully loaded.'));
    checkBackend();
    void refreshBackend();
    let a: (() => void) | undefined;
    let b: (() => void) | undefined;
    Promise.all([
      listen<DetectedEvent>('sentinel://artifact-detected', ({ payload }) => {
        setReview(r => [{ ...payload }, ...r.filter(x => x.path !== payload.path)]);
        setStatusMessage(`Watched file routed to review · ${payload.name}`);
        setView('review');
      }),
      listen('sentinel://quarantine-changed', () => getQuarantine().then(setQuarantine).catch(() => {})),
    ]).then(([x, y]) => { a = x; b = y; });
    return () => { a?.(); b?.(); };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => { void refreshBackend(); }, 5000);
    return () => window.clearInterval(timer);
  }, [apiUrl]);

  const stats = useMemo(() => ({
    scanned: history.length,
    review: review.length + history.filter(x => x.status === 'REVIEW').length,
    clear: history.filter(x => x.status === 'CLEAR').length,
    quarantined: backendQuarantine.filter(x => x.status === 'QUARANTINED').length + quarantine.length,
  }), [history, review, quarantine, backendQuarantine]);

  const selectScan = (result: ScanResult) => { setSelected(result); setSelectedQ(null); setView('scan'); };

  const runSingleScan = async () => {
    const path = await pickFile(); if (!path) return;
    setBusy(true); setStatusMessage(`Reading local artifact · ${path}`);
    try { const result = await scanFile(path); selectScan(result); await refresh(); setStatusMessage(`FastScan complete · ${result.risk_score}/100 · ${result.status}`); }
    catch (e) { setStatusMessage(`Scan failed · ${String(e)}`); }
    finally { setBusy(false); }
  };

  const runFolderScan = async () => {
    const path = await pickFolder(); if (!path) return;
    setBusy(true); setBatch(null); setStatusMessage(`Scanning directory recursively · ${path}`);
    try { const out = await scanDirectory(path); setBatch(out); await refresh(); setStatusMessage(`Directory scan complete · ${out.scanned} files inspected.`); setView('scan'); }
    catch (e) { setStatusMessage(`Directory scan failed · ${String(e)}`); }
    finally { setBusy(false); }
  };

  const addWatchLocation = async () => {
    const path = await pickFolder(); if (!path) return;
    try { await addWatch(path); setWatches(await getWatches()); setStatusMessage(`Monitoring enabled · ${path}`); }
    catch (e) { setStatusMessage(`Watch setup failed · ${String(e)}`); }
  };

  const scanWatched = async (path: string) => {
    setBusy(true); setStatusMessage(`Scanning watched directory · ${path}`);
    try { const out = await scanWatchedFolder(path); setBatch(out); await refresh(); setStatusMessage(`Watched directory scan complete · ${out.scanned} files.`); setView('scan'); }
    catch (e) { setStatusMessage(`Folder scan failed · ${String(e)}`); }
    finally { setBusy(false); }
  };

  const reviewArtifact = async (item: DetectedEvent) => {
    setBusy(true);
    try { const result = await scanFile(item.path); setReview(r => r.filter(x => x.path !== item.path)); selectScan(result); await refresh(); }
    catch (e) { setStatusMessage(`Review failed · ${String(e)}`); }
    finally { setBusy(false); }
  };

  const doQuarantine = async () => {
    setStatusMessage('Encrypted containment is performed by PRISM Sentinel for explicitly watched folders. Configure a watch root with prism watch add.');
    setView('watch');
  };

  const doRestore = async (item: QuarantineItem) => {
    setBusy(true);
    try { const path = await restoreQuarantine(item.id); await refresh(); setSelectedQ(null); setStatusMessage(`Restored · ${path}`); setView('history'); }
    catch (e) { setStatusMessage(`Restore failed · ${String(e)}`); }
    finally { setBusy(false); }
  };

  const doRestoreBackend = async (item: BackendQuarantineItem) => {
    setBusy(true);
    try { await restoreBackendQuarantine(apiUrl, item.quarantine_id); await refreshBackend(); setStatusMessage(`Authenticated restore completed · ${item.original_name}`); }
    catch (e) { setStatusMessage(`Restore failed · ${String(e)}`); }
    finally { setBusy(false); }
  };

  const sendToLab = async () => {
    if (!selected) return;
    setBusy(true); setStatusMessage('Uploading artifact to the PRISM backend…');
    try {
      const out = await handoffArtifact(selected.path, apiUrl);
      setRemoteId(out.artifact_id);
      setApiConnected(true);
      const analysis = await runRemoteAnalyze(apiUrl, out.artifact_id);
      setRemotePane({ title: 'analysis', body: analysis });
      setRemoteArtifact({ title: 'artifact', body: await getRemoteArtifact(apiUrl, out.artifact_id) });
      setStatusMessage(`Artifact analyzed by PRISM · ${out.artifact_id}`);
    } catch (e) { setStatusMessage(`Backend handoff or analysis failed · ${String(e)}`); }
    finally { setBusy(false); }
  };

  const loadRemote = async (kind: string, id = remoteId) => {
    if (!id) { setRemotePane({ title: titleFor(view), body: null, error: 'Select or upload an artifact first.' }); return; }
    setBusy(true);
    setRemotePane({ title: kind, body: null, loading: true });
    try {
      let body: JsonValue;
      if (kind === 'artifact') body = await getRemoteArtifact(apiUrl, id);
      else if (kind === 'fastscan') body = await getRemoteFastScan(apiUrl, id);
      else if (kind === 'interpretation') body = await getRemoteInterpretation(apiUrl, id);
      else if (kind === 'graph') body = await getRemoteGraph(apiUrl, id);
      else if (kind === 'fractures') body = await getRemoteFractures(apiUrl, id);
      else if (kind === 'lab') body = await getRemoteInvestigation(apiUrl, id);
      else if (kind === 'investigation') body = await getRemoteInvestigation(apiUrl, id);
      else if (kind === 'passport') body = await getRemotePassport(apiUrl, id);
      else body = await backendRequest(apiUrl, `/api/artifacts/${encodeURIComponent(id)}/${kind}`);
      setRemotePane({ title: kind, body }); if (kind === 'artifact') setRemoteArtifact({ title: kind, body }); setApiConnected(true);
      setStatusMessage(`Loaded backend evidence · ${kind}`);
    } catch (e) { setRemotePane({ title: kind, body: null, error: String(e) }); setStatusMessage(`Backend request unavailable · ${String(e)}`); }
    finally { setBusy(false); }
  };

  const runBackendStep = async (step: 'analyze' | 'fastscan' | 'interpret' | 'graph' | 'lab') => {
    if (!remoteId) { setStatusMessage('Connect an artifact before starting backend analysis.'); return; }
    setBusy(true);
    try {
      if (step === 'analyze') setRemotePane({ title: 'analysis', body: await runRemoteAnalyze(apiUrl, remoteId) });
      if (step === 'fastscan') await runRemoteFastScan(apiUrl, remoteId);
      if (step === 'interpret') await runRemoteInterpret(apiUrl, remoteId);
      if (step === 'graph') {
        try { await getRemoteGraph(apiUrl, remoteId); }
        catch (error) {
          if (!String(error).includes('DEEP_INTERPRETATION_NOT_PERFORMED')) throw error;
          await runRemoteInterpret(apiUrl, remoteId);
          await runRemoteGraph(apiUrl, remoteId);
        }
      }
      if (step === 'lab') { await runRemoteReason(apiUrl, remoteId); const result = await runRemoteInvestigation(apiUrl, remoteId); setRemotePane({ title: 'investigation', body: result }); }
      if (step !== 'lab' && step !== 'analyze') await loadRemote(step === 'interpret' ? 'interpretation' : step);
      setStatusMessage(`Backend operation completed · ${step}`);
    } catch (e) {
      setStatusMessage(`Backend operation failed · ${String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const loadImmune = async () => {
    setImmuneMemory({ title: 'Immune Memory', body: null, loading: true });
    try { const body = await getImmuneMemory(apiUrl); setImmuneMemory({ title: 'Immune Memory', body }); setApiConnected(true); }
    catch (e) { setImmuneMemory({ title: 'Immune Memory', body: null, error: String(e) }); }
  };

  const handleBackendView = (v: View) => {
    setView(v);
    if (['artifacts','fractures','graph','lab','evidence','passports','capability','compare','experiments'].includes(v)) {
      if (v === 'artifacts') loadRemote('artifact');
      if (v === 'fractures') loadRemote('fractures');
      if (v === 'graph') loadRemote('graph');
      if (v === 'lab') loadRemote('lab');
      if (v === 'evidence') loadRemote('fastscan');
      if (v === 'passports') loadRemote('passport');
      if (v === 'capability') loadRemote('graph');
      if (v === 'experiments') loadRemote('investigation');
    }
    if (v === 'immune') loadImmune();
  };

  const saveApi = async (value: string) => {
    try {
      await setApiUrl(value);
      setApiUrlState(value);
      const ok = await checkBackend(value);
      if (ok) await refreshBackend(value);
      setStatusMessage(ok ? 'PRISM backend connected.' : 'Endpoint saved. Backend is not reachable from this client.');
    } catch (error) { setStatusMessage(`Endpoint rejected · ${String(error)}`); }
  };

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><img src={prismLogo} alt="PRISM" draggable="false" /></div><div><div className="brand-name">PRISM</div><div className="brand-sub">SENTINEL</div></div></div>
      <div className="sidebar-caption">FULL PRISM CLIENT</div>
      <nav>{sections.map(section => <div key={section.group} className="nav-section"><div className="nav-group">{section.group}</div>{section.items.map(([id,label,Icon]) => <button key={id} className={`nav-item ${view===id?'active':''}`} onClick={()=>handleBackendView(id)}><Icon size={16}/><span>{label}</span>{id==='review'&&stats.review>0&&<b className="nav-count">{stats.review}</b>}{id==='quarantine'&&stats.quarantined>0&&<b className="nav-count">{stats.quarantined}</b>}</button>)}</div>)}</nav>
      <div className="sidebar-bottom"><button className={`nav-item ${view==='settings'?'active':''}`} onClick={()=>setView('settings')}><Settings size={16}/><span>Settings</span></button><div className="build">v0.7.3 · full native Windows client</div></div>
    </aside>

    <main className="main">
      <header className="topbar"><div><div className="eyebrow">PRISM SENTINEL</div><h1>{titleFor(view)}</h1></div><div className="top-actions"><div className={`connection-chip ${apiConnected?'connected':''}`}>{apiConnected?<CheckCircle2 size={14}/>:<Unplug size={14}/>} {apiConnected?'PRISM backend connected':'Local-only mode'}</div><button className="secondary" onClick={runFolderScan} disabled={busy}><FolderSearch2 size={16}/> Scan folder</button><button className="primary" onClick={runSingleScan} disabled={busy}><ScanLine size={16}/> Scan file</button></div></header>
      <div className="statusbar"><Activity size={14}/><span>{statusMessage}</span>{busy&&<span className="busy-pill">WORKING</span>}</div>

      <section className="content">
        {view==='overview'&&<Overview stats={stats} watches={watches} history={history} quarantine={backendQuarantine} remoteId={remoteId} onScan={runSingleScan} onFolder={runFolderScan} onReview={()=>setView('review')} onWatch={()=>setView('watch')} onQuarantine={()=>setView('quarantine')} onLab={()=>remoteId?handleBackendView('lab'):sendToLab()}/>} 
        {view==='intercept'&&<InterceptView review={review} watches={watches} onReview={reviewArtifact} onWatch={()=>setView('watch')} />}
        {view==='artifacts'&&<BackendArtifactView body={remotePane.body} error={remotePane.error} loading={remotePane.loading} remoteId={remoteId} selected={selected} onUpload={sendToLab} onRefresh={()=>loadRemote('artifact')} onFastScan={()=>runBackendStep('fastscan')} onInterpret={()=>runBackendStep('interpret')} onGraph={()=>runBackendStep('graph')} onLab={()=>runBackendStep('lab')} /> }
        {view==='fractures'&&<BackendEvidenceView title="Semantic Fractures" subtitle="Security-relevant interpretation disagreements returned by the connected PRISM backend." body={remotePane.body} error={remotePane.error} loading={remotePane.loading} remoteId={remoteId} onAction={()=>loadRemote('fractures')} actionLabel="Refresh" empty="Upload/select an artifact, then load its fracture evidence." />}
        {view==='review'&&<ReviewQueue items={review} history={history.filter(x=>x.status==='REVIEW')} onReview={reviewArtifact} />}
        {view==='scan'&&<ScanView selected={selected} batch={batch} onScan={runSingleScan} onFolder={runFolderScan} onQuarantine={doQuarantine} onLab={sendToLab} onReveal={()=>selected&&revealFile(selected.path)} onRisk={() => setStatusMessage(selected?.reason||'No additional local status message.')} />}
        {view==='watch'&&<><SentinelBackendPanel state={sentinelState} roots={sentinelRoots} events={sentinelEvents} connected={apiConnected}/><WatchView watches={watches} onAdd={addWatchLocation} onRemove={async p=>{await removeWatch(p);setWatches(await getWatches());setStatusMessage(`Monitoring removed · ${p}`)}} onScan={scanWatched} /></>}
        {view==='quarantine'&&<><BackendQuarantineView items={backendQuarantine} selected={selectedBackendQ} onSelect={setSelectedBackendQ} onRestore={doRestoreBackend} connected={apiConnected}/>{quarantine.length>0&&<QuarantineView items={quarantine} selected={selectedQ} onSelect={setSelectedQ} onRestore={doRestore} onOpenFolder={async()=>{const p=await openQuarantineFolder();setStatusMessage(`Legacy local quarantine folder · ${p}`)}} onReveal={revealFile} />}</>}
        {view==='history'&&<HistoryView history={history} onSelect={selectScan} onClear={async()=>{await clearHistory();await refresh();setStatusMessage('Local history cleared.')}} />}
        {view==='graph'&&<GraphView body={remotePane.body} error={remotePane.error} loading={remotePane.loading} remoteId={remoteId} onRefresh={()=>loadRemote('graph')} onGenerate={()=>runBackendStep('graph')} />}
        {view==='lab'&&<LabView body={remotePane.body} error={remotePane.error} loading={remotePane.loading} remoteId={remoteId} onStart={()=>runBackendStep('lab')} />}
        {view==='experiments'&&<ExperimentView body={remotePane.body} error={remotePane.error} loading={remotePane.loading} remoteId={remoteId} onRefresh={()=>loadRemote('investigation')} />}
        {view==='evidence'&&<EvidenceView selected={selected} body={remotePane.body} error={remotePane.error} loading={remotePane.loading} remoteId={remoteId} onRefresh={()=>loadRemote('fastscan')} />}
        {view==='compare'&&<CompareView selected={selected} remoteId={remoteId} remoteArtifact={remoteArtifact.body??remotePane.body} onRefresh={()=>loadRemote('artifact')} />}
        {view==='passports'&&<PassportView body={remotePane.body} error={remotePane.error} loading={remotePane.loading} remoteId={remoteId} onRefresh={()=>loadRemote('passport')} />}
        {view==='capability'&&<CapabilityView body={remotePane.body} error={remotePane.error} loading={remotePane.loading} remoteId={remoteId} onRefresh={()=>loadRemote('graph')} />}
        {view==='immune'&&<BackendEvidenceView title="Immune Memory" subtitle="Server-side findings, reproducers, regression knowledge, and retrieval memory when available." body={immuneMemory.body} error={immuneMemory.error} loading={immuneMemory.loading} remoteId="global" onAction={loadImmune} actionLabel="Refresh" empty="No memory data is available from the configured backend." />}
        {view==='local'&&<LocalFilesView onScan={runSingleScan} onFolder={runFolderScan} watches={watches} onWatch={()=>setView('watch')} />}
        {view==='policies'&&<PoliciesView watches={watches} />}
        {view==='settings'&&<SettingsView apiUrl={apiUrl} quarantineDir={quarantineDir} onSave={saveApi} />}
      </section>
    </main>
  </div>;
}

function Overview({stats,watches,history,quarantine,remoteId,onScan,onFolder,onReview,onWatch,onQuarantine,onLab}:{stats:{scanned:number;review:number;clear:number;quarantined:number};watches:string[];history:HistoryItem[];quarantine:BackendQuarantineItem[];remoteId:string|null;onScan:()=>void;onFolder:()=>void;onReview:()=>void;onWatch:()=>void;onQuarantine:()=>void;onLab:()=>void}){
  const latest=history[0];
  return <div className="page-stack">
    <div className="hero-grid"><div className="hero-copy"><div className="section-label">ENDPOINT + INVESTIGATION</div><h2>One PRISM client for the whole workflow.</h2><p>Sentinel can inspect local artifacts, monitor directories, quarantine files, and hand the same evidence to the deeper PRISM interpretation and Lab stack.</p><div className="hero-actions"><button className="primary" onClick={onScan}><ScanLine size={16}/> Scan artifact</button><button className="secondary" onClick={onFolder}><FolderSearch2 size={16}/> Scan directory</button>{remoteId&&<button className="secondary" onClick={onLab}><BrainCircuit size={16}/> Open Lab</button>}</div></div><div className="hero-evidence"><div className="section-label">LOCAL STATE</div><div className="metric-list"><Metric label="Artifacts scanned" value={stats.scanned}/><Metric label="Review queue" value={stats.review}/><Metric label="Watched locations" value={watches.length}/><Metric label="Quarantined" value={stats.quarantined}/></div></div></div>
    <div className="stat-row"><StatCard label="Scanned" value={stats.scanned} icon={FileSearch}/><StatCard label="Needs review" value={stats.review} icon={CircleAlert}/><StatCard label="Clear" value={stats.clear} icon={CheckCircle2}/><StatCard label="Quarantined" value={stats.quarantined} icon={ArchiveRestore}/></div>
    <div className="two-col"><div className="panel"><PanelTitle label="LATEST ARTIFACT" title="Local evidence"/><div className="artifact-strip">{latest?<><div className={`status-badge ${latest.status.toLowerCase()}`}>{latest.status}</div><div className="artifact-summary"><strong>{latest.name}</strong><span>{latest.path}</span><span>{latest.detected_type} · {formatBytes(latest.size_bytes)} · SHA {latest.sha256.slice(0,16)}…</span></div><div className={`risk-large ${riskLabel(latest.risk_score).toLowerCase()}`}>{latest.risk_score}<span>/100</span></div></>:<Empty icon={FileSearch} title="No local scans yet" body="Scan a file or directory to populate this workspace." action={onScan} actionLabel="Scan a file"/>}</div></div><div className="panel"><PanelTitle label="ENDPOINT" title="Protection surfaces"/><div className="surface-list"><button onClick={onWatch}><Radio size={16}/><span><strong>Watch locations</strong><small>{watches.length ? `${watches.length} configured` : 'No directories monitored'}</small></span><ChevronRight size={15}/></button><button onClick={onQuarantine}><ArchiveRestore size={16}/><span><strong>Quarantine</strong><small>{quarantine.length ? `${quarantine.length} isolated` : 'No isolated artifacts'}</small></span><ChevronRight size={15}/></button><button onClick={onReview}><Inbox size={16}/><span><strong>Review queue</strong><small>{stats.review ? `${stats.review} items need attention` : 'Queue is empty'}</small></span><ChevronRight size={15}/></button></div></div></div>
  </div>
}
function Metric({label,value}:{label:string;value:number}){return <div className="metric"><span>{label}</span><strong>{value}</strong></div>}
function StatCard({label,value,icon:Icon}:{label:string;value:number;icon:any}){return <div className="stat-card"><Icon size={17}/><span>{label}</span><strong>{value}</strong></div>}
function PanelTitle({label,title}:{label:string;title:string}){return <div className="panel-title"><div><div className="section-label">{label}</div><h3>{title}</h3></div></div>}

function InterceptView({review,watches,onReview,onWatch}:{review:DetectedEvent[];watches:string[];onReview:(i:DetectedEvent)=>void;onWatch:()=>void}){return <div className="page-stack"><div className="hero-grid compact"><div className="hero-copy"><div className="section-label">LOCAL INTERCEPTION SURFACE</div><h2>Observed files are routed through Sentinel.</h2><p>The current endpoint implementation watches selected directories. Created or modified files are re-inspected, and elevated evidence can enter Review Queue.</p><button className="secondary" onClick={onWatch}><Radio size={16}/> Configure watch locations</button></div><div className="hero-evidence"><div className="section-label">ACTIVE SCOPE</div><div className="metric-list"><Metric label="Watched locations" value={watches.length}/><Metric label="Pending review events" value={review.length}/></div></div></div><div className="panel"><PanelTitle label="INTERCEPTED ARTIFACTS" title="Review events"/>{review.length===0?<Empty icon={Radar} title="No pending interception events" body="New or modified files from watched folders appear here when local evidence requires review."/>:<div className="event-list">{review.map(item=><div className="event-row" key={item.path}><div className="event-icon"><Radar size={16}/></div><div><strong>{item.name}</strong><span>{item.path}</span><small>{item.reason||'Local evidence requires inspection'} · {item.risk_score??'—'}/100</small></div><button className="secondary small" onClick={()=>onReview(item)}>Inspect</button></div>)}</div>}</div></div>}

function ScanView({selected,batch,onScan,onFolder,onQuarantine,onLab,onReveal,onRisk}:{selected:ScanResult|null;batch:BatchScanResult|null;onScan:()=>void;onFolder:()=>void;onQuarantine:()=>void;onLab:()=>void;onReveal:()=>void;onRisk:()=>void}){return <div className="page-stack"><div className="action-banner"><div><div className="section-label">LOCAL FASTSCAN</div><h3>Inspect real bytes before deeper analysis.</h3><p>Claims come from the filename/extension; observed identity comes from the bytes Sentinel actually read.</p></div><div className="hero-actions"><button className="secondary" onClick={onFolder}><FolderSearch2 size={16}/> Scan directory</button><button className="primary" onClick={onScan}><ScanLine size={16}/> Scan file</button></div></div>{batch&&<div className="stat-row"><StatCard label="Scanned" value={batch.scanned} icon={ScanLine}/><StatCard label="Review" value={batch.review} icon={CircleAlert}/><StatCard label="Clear" value={batch.clear} icon={CheckCircle2}/><StatCard label="Failed" value={batch.failed} icon={ShieldQuestion}/></div>}{selected?<div className="scan-grid"><div className="panel"><div className="scan-header"><div><div className="section-label">SELECTED ARTIFACT</div><h2>{selected.name}</h2><p>{selected.path}</p></div><RiskScore score={selected.risk_score}/></div><div className="evidence-grid"><Evidence label="Claimed type" value={selected.declared_type}/><Evidence label="Observed type" value={selected.detected_type}/><Evidence label="Size" value={formatBytes(selected.size_bytes)}/><Evidence label="Entropy" value={`${selected.entropy.toFixed(2)} / 8.00`}/><Evidence label="SHA-256" value={selected.sha256} mono/><Evidence label="Status" value={selected.status}/></div></div><div className="panel"><PanelTitle label="LOCAL EVIDENCE" title="Risk factors"/>{selected.risk_factors.map((x,i)=><div className="marker" key={x+i}><CircleAlert size={14}/>{x}</div>)}<div className="action-stack"><button className="secondary" onClick={onRisk}><SlidersHorizontal size={15}/> Show decision rationale</button><button className="secondary" onClick={onReveal}><FolderOpen size={15}/> Reveal local file</button>{selected.status!=='QUARANTINED'&&<button className="danger" onClick={onQuarantine}><ArchiveRestore size={15}/> Configure encrypted Sentinel containment</button>}<button className="primary" onClick={onLab}><UploadCloud size={15}/> Connect to PRISM backend</button></div></div></div>:<Empty icon={ScanLine} title="No artifact selected" body="Select a local file or directory to begin." action={onScan} actionLabel="Scan a file"/>}</div>}
function RiskScore({score}:{score:number}){return <div className={`score-box ${riskLabel(score).toLowerCase()}`}><span>RISK SCORE</span><strong>{score}</strong><em>{riskLabel(score)}</em></div>}
function Evidence({label,value,mono}:{label:string;value:string;mono?:boolean}){return <div className="evidence"><span>{label}</span><strong className={mono?'mono':''}>{value}</strong></div>}

function ReviewQueue({items,history,onReview}:{items:DetectedEvent[];history:HistoryItem[];onReview:(x:DetectedEvent)=>void}){const combined=[...items,...history.map(h=>({path:h.path,name:h.name,reason:h.reason,risk_score:h.risk_score}))];return <div className="page-stack"><div className="action-banner"><div><div className="section-label">HUMAN REVIEW</div><h3>Evidence before action.</h3><p>Review items are driven by real local scan results and watch events. Sentinel does not fabricate alerts.</p></div></div><div className="panel">{combined.length===0?<Empty icon={Inbox} title="Review queue is empty" body="Elevated local evidence will appear here when Sentinel finds it."/>:<div className="event-list">{combined.map((x,i)=><div className="event-row" key={`${x.path}-${i}`}><div className="event-icon alert"><CircleAlert size={16}/></div><div><strong>{x.name}</strong><span>{x.path}</span><small>{x.reason||'Artifact requires inspection'} · {x.risk_score??'—'}/100</small></div><button className="secondary small" onClick={()=>onReview(x)}>Inspect</button></div>)}</div>}</div></div>}

function WatchView({watches,onAdd,onRemove,onScan}:{watches:string[];onAdd:()=>void;onRemove:(p:string)=>void;onScan:(p:string)=>void}){return <div className="page-stack"><div className="section-heading inline"><div><div className="section-label">LOCAL DIRECTORIES</div><h3>Continuous monitoring</h3></div><button className="primary" onClick={onAdd}><Radio size={16}/> Add directory</button></div><div className="callout neutral"><Radio size={18}/><div><strong>Native watcher</strong><span>Sentinel watches configured folders recursively. Created or modified files are FastScanned locally; elevated evidence is routed to Review Queue.</span></div></div><div className="panel">{watches.length===0?<Empty icon={Radio} title="No watched locations" body="Add Downloads, a project folder, removable-media mount, or another local directory." action={onAdd} actionLabel="Add directory"/>:watches.map(path=><div className="watch-row" key={path}><div className="watch-icon"><HardDrive size={16}/></div><div className="watch-path"><strong>{path}</strong><span>Recursive monitoring enabled</span></div><button className="secondary small" onClick={()=>onScan(path)}><ScanLine size={14}/> Scan now</button><button className="icon-btn" onClick={()=>onRemove(path)} title="Stop monitoring"><X size={17}/></button></div>)}</div></div>}

function HistoryView({history,onSelect,onClear}:{history:HistoryItem[];onSelect:(x:ScanResult)=>void;onClear:()=>void}){return <div className="page-stack"><div className="section-heading inline"><div><div className="section-label">LOCAL EVIDENCE LOG</div><h3>Completed scans</h3></div>{history.length>0&&<button className="danger small" onClick={onClear}><Trash2 size={14}/> Clear history</button>}</div><div className="panel">{history.length===0?<Empty icon={History} title="No history yet" body="Completed local scans appear here."/>:history.map(item=><button className="history-row" key={item.sha256} onClick={()=>onSelect(item)}><div className={`history-state ${item.status.toLowerCase()}`}>{item.status}</div><div><strong>{item.name}</strong><span>{item.path}</span></div><div className={`risk-mini ${riskLabel(item.risk_score).toLowerCase()}`}>{item.risk_score}/100</div><time>{timeAgo(item.scanned_at)}</time><ChevronRight size={15}/></button>)}</div></div>}

function SentinelBackendPanel({state,roots,events,connected}:{state:JsonValue|null;roots:JsonValue[];events:JsonValue[];connected:boolean}) {
  const status = state !== null && isObject(state) ? state : null;
  return <div className="panel"><PanelTitle label="PRISM BACKEND SENTINEL" title={connected ? 'Live watched-folder evidence' : 'Backend unavailable'}/><p>Backend watch roots are configured with <code>prism watch add</code>. Native desktop watches below are separate local review hints and do not trigger encrypted containment.</p><div className="metric-list"><Metric label="Configured backend folders" value={typeof status?.watch_root_count === 'number' ? status.watch_root_count : 0}/></div>{roots.map((root,i) => isObject(root) ? <div className="watch-row" key={i}><strong>{String(root.display_name ?? 'Watch root')}</strong><span>{root.recursive ? 'Recursive' : 'This folder only'}</span></div> : null)}<div className="section-label">RECENT BACKEND EVENTS</div>{events.slice(0,8).map((event,i) => isObject(event) ? <div className="event-row" key={String(event.event_id ?? i)}><strong>{String(event.event_type ?? 'Event')}</strong><span>{String(event.file_name ?? 'Sentinel')} · {String(event.message ?? '')}</span>{event.containment_trigger ? <small>Containment: {String(event.containment_trigger)} · Deterministic: {String(event.verified_state ?? 'No deterministic verified state')}</small> : null}</div> : null)}</div>;
}

function BackendQuarantineView({items,selected,onSelect,onRestore,connected}:{items:BackendQuarantineItem[];selected:BackendQuarantineItem|null;onSelect:(x:BackendQuarantineItem)=>void;onRestore:(x:BackendQuarantineItem)=>void;connected:boolean}) {
  return <div className="page-stack"><div className="section-heading inline"><div><div className="section-label">AUTHENTICATED PRISM CONTAINMENT</div><h3>Encrypted quarantine</h3></div></div><div className="quarantine-layout"><div className="panel">{!connected?<Empty icon={Unplug} title="Backend unavailable" body="Connect to the local PRISM backend to view encrypted quarantine records."/>:items.length===0?<Empty icon={ArchiveRestore} title="No backend quarantine records" body="Only real Sentinel containment events appear here."/>:items.map(item=><button key={item.quarantine_id} className={`quarantine-row ${selected?.quarantine_id===item.quarantine_id?'selected':''}`} onClick={()=>onSelect(item)}><div className="risk-dot elevated"><LockKeyhole size={15}/></div><div><strong>{item.original_name}</strong><span>{item.status} · {item.trigger}</span></div><ChevronRight size={15}/></button>)}</div>{selected?<div className="panel quarantine-detail"><div className="detail-header"><div><div className="section-label">{selected.status}</div><h2>{selected.original_name}</h2></div></div><div className="evidence-grid"><Evidence label="Containment trigger" value={selected.trigger}/><Evidence label="Laya prediction (advisory)" value={selected.laya_prediction ?? '—'}/><Evidence label="Model confidence" value={selected.laya_confidence === null ? '—' : `${Math.round(selected.laya_confidence*100)}%`}/><Evidence label="Deterministic verified state" value={selected.verified_state ?? 'No deterministic verified state'}/><Evidence label="Encrypted container" value={selected.container_name}/><Evidence label="SHA-256" value={selected.sha256} mono/></div>{selected.reason_codes.length ? <div className="marker">Verified reasons: {selected.reason_codes.join(', ')}</div> : null}<p className="note">Laya-triggered containment is precautionary. It does not establish deterministic SUSPICIOUS.</p>{selected.status==='QUARANTINED' ? <button className="primary" onClick={()=>onRestore(selected)}><RotateCcw size={15}/> Authenticate and restore</button> : null}</div>:<div className="panel empty-detail"><LockKeyhole size={28}/><h3>Select a contained artifact</h3><p>Containment and verified state remain separate.</p></div>}</div></div>;
}

function QuarantineView({items,selected,onSelect,onRestore,onOpenFolder,onReveal}:{items:QuarantineItem[];selected:QuarantineItem|null;onSelect:(x:QuarantineItem)=>void;onRestore:(x:QuarantineItem)=>void;onOpenFolder:()=>void;onReveal:(path:string)=>void}) {
  return <div className="page-stack"><div className="section-heading inline"><div><div className="section-label">LEGACY LOCAL RECORDS</div><h3>Previous desktop containment</h3></div><button className="secondary" onClick={onOpenFolder}>Open legacy folder</button></div><div className="callout neutral"><CircleAlert size={18}/><div><strong>Legacy records are not encrypted PRISM containers.</strong><span>They remain available here only for recovery. New containment uses backend Sentinel above.</span></div></div><div className="quarantine-layout"><div className="panel">{items.map(item=><button key={item.id} className={`quarantine-row ${selected?.id===item.id?'selected':''}`} onClick={()=>onSelect(item)}><strong>{item.name}</strong><span>Legacy local record</span></button>)}</div>{selected&&<div className="panel quarantine-detail"><h3>{selected.name}</h3><Evidence label="SHA-256" value={selected.sha256} mono/><div className="action-stack"><button className="secondary" onClick={()=>onReveal(selected.quarantined_path)}>Reveal legacy file</button><button className="primary" onClick={()=>onRestore(selected)}>Restore legacy file</button></div></div>}</div></div>;
}

function BackendArtifactView({body,error,loading,remoteId,selected,onUpload,onRefresh,onFastScan,onInterpret,onGraph,onLab}:{body:JsonValue|null;error?:string;loading?:boolean;remoteId:string|null;selected:ScanResult|null;onUpload:()=>void;onRefresh:()=>void;onFastScan:()=>void;onInterpret:()=>void;onGraph:()=>void;onLab:()=>void}){return <div className="page-stack"><div className="hero-grid compact"><div className="hero-copy"><div className="section-label">BACKEND ARTIFACT RECORD</div><h2>{remoteId?`Artifact ${remoteId}`:'Connect a local artifact to PRISM'}</h2><p>Use the native client to upload an inspected local artifact. Once connected, the desktop can drive the same FastScan, interpretation, graph and Lab stages used by the PRISM investigation stack.</p><div className="hero-actions"><button className="primary" onClick={onUpload} disabled={!selected}><CloudUpload size={16}/> Connect selected artifact</button><button className="secondary" onClick={onRefresh} disabled={!remoteId}><RefreshCw size={16}/> Refresh record</button></div></div><div className="hero-evidence"><div className="section-label">ANALYSIS STAGES</div><div className="stage-buttons"><button disabled={!remoteId} onClick={onFastScan}><ScanLine size={14}/> FastScan</button><button disabled={!remoteId} onClick={onInterpret}><FileSearch size={14}/> Interpret</button><button disabled={!remoteId} onClick={onGraph}><Network size={14}/> Build graph</button><button disabled={!remoteId} onClick={onLab}><BrainCircuit size={14}/> PRISM Lab</button></div></div></div><JsonPanel body={body} error={error} loading={loading} empty="No backend artifact is loaded yet." /></div>}

function GraphView({body,error,loading,remoteId,onRefresh,onGenerate}:{body:JsonValue|null;error?:string;loading?:boolean;remoteId:string|null;onRefresh:()=>void;onGenerate:()=>void}){return <div className="page-stack"><div className="action-banner"><div><div className="section-label">INTERPRETATION GRAPH</div><h3>Identities, structures, capabilities, parser observations.</h3><p>The graph is sourced from the connected PRISM backend. A clean early PASS may need explicit deterministic interpretation before a graph exists.</p></div><div className="hero-actions"><button className="secondary" disabled={!remoteId} onClick={onRefresh}><RefreshCw size={15}/> Refresh graph</button><button className="primary" disabled={!remoteId} onClick={onGenerate}><Network size={15}/> Run interpretation and build graph</button></div></div><JsonGraph body={body} error={error} loading={loading} /></div>}
function LabView({body,error,loading,remoteId,onStart}:{body:JsonValue|null;error?:string;loading?:boolean;remoteId:string|null;onStart:()=>void}){return <div className="page-stack"><div className="hero-grid compact"><div className="hero-copy"><div className="section-label">PRISM LAB</div><h2>Evidence-grounded investigation.</h2><p>The Lab is where retrieval, reasoning, semantic experiments, validation and minimization belong. The client only displays what the connected backend returns.</p><button className="primary" disabled={!remoteId} onClick={onStart}><BrainCircuit size={16}/> Start / refresh investigation</button></div><div className="hero-evidence"><div className="section-label">CONNECTED ARTIFACT</div><strong className="mono big-code">{remoteId||'none'}</strong></div></div><JsonPanel body={body} error={error} loading={loading} empty="Connect an artifact to enter PRISM Lab." /></div>}
function ExperimentView({body,error,loading,remoteId,onRefresh}:{body:JsonValue|null;error?:string;loading?:boolean;remoteId:string|null;onRefresh:()=>void}){return <div className="page-stack"><div className="action-banner"><div><div className="section-label">EXPERIMENTS / INVESTIGATION STATE</div><h3>Controlled experiments and investigation state.</h3><p>This view displays backend investigation data when the current API exposes it. No experiment results are fabricated locally.</p></div><button className="secondary" disabled={!remoteId} onClick={onRefresh}><RefreshCw size={15}/> Refresh</button></div><JsonPanel body={body} error={error} loading={loading} empty="No investigation data loaded." /></div>}
function EvidenceView({selected,body,error,loading,remoteId,onRefresh}:{selected:ScanResult|null;body:JsonValue|null;error?:string;loading?:boolean;remoteId:string|null;onRefresh:()=>void}){return <div className="page-stack"><div className="two-col"><div className="panel"><PanelTitle label="LOCAL FASTSCAN" title="Native evidence"/>{selected?<div className="evidence-grid"><Evidence label="Name" value={selected.name}/><Evidence label="Claimed" value={selected.declared_type}/><Evidence label="Observed" value={selected.detected_type}/><Evidence label="Entropy" value={selected.entropy.toFixed(2)}/><Evidence label="SHA-256" value={selected.sha256} mono/><Evidence label="Risk" value={`${selected.risk_score}/100`}/></div>:<Empty icon={FileSearch} title="No local artifact selected" body="Scan a file first."/>}</div><div className="panel"><PanelTitle label="BACKEND EVIDENCE" title="FastScan record"/><button className="secondary small" disabled={!remoteId} onClick={onRefresh}><RefreshCw size={14}/> Refresh backend evidence</button><JsonPanel body={body} error={error} loading={loading} empty="No backend FastScan loaded." embedded/></div></div></div>}
function PassportView({body,error,loading,remoteId,onRefresh}:{body:JsonValue|null;error?:string;loading?:boolean;remoteId:string|null;onRefresh:()=>void}){return <div className="page-stack"><div className="action-banner"><div><div className="section-label">ARTIFACT PASSPORT</div><h3>Machine-readable evidence summary.</h3><p>Passport content comes from the backend investigation. The desktop does not invent verdicts or capabilities.</p></div><button className="secondary" disabled={!remoteId} onClick={onRefresh}><RefreshCw size={15}/> Refresh</button></div><JsonPanel body={body} error={error} loading={loading} empty="No Passport loaded for the selected artifact." /></div>}
function CapabilityView({body,error,loading,remoteId,onRefresh}:{body:JsonValue|null;error?:string;loading?:boolean;remoteId:string|null;onRefresh:()=>void}){return <div className="page-stack"><div className="action-banner"><div><div className="section-label">CAPABILITY GRAPH</div><h3>What the artifact can expose or contain.</h3><p>Capabilities are modeled independently from simplistic benign/malicious labels.</p></div><button className="secondary" disabled={!remoteId} onClick={onRefresh}><RefreshCw size={15}/> Refresh</button></div><JsonGraph body={body} error={error} loading={loading}/></div>}
function BackendEvidenceView({title,subtitle,body,error,loading,remoteId,onAction,actionLabel,empty}:{title:string;subtitle:string;body:JsonValue|null;error?:string;loading?:boolean;remoteId?:string | null;onAction:()=>void;actionLabel:string;empty:string}){return <div className="page-stack"><div className="action-banner"><div><div className="section-label">BACKEND INTELLIGENCE</div><h3>{title}</h3><p>{subtitle}</p></div><button className="secondary" onClick={onAction}><RefreshCw size={15}/> {actionLabel}</button></div><JsonPanel body={body} error={error} loading={loading} empty={empty} /></div>}

function CompareView({selected,remoteId,remoteArtifact,onRefresh}:{selected:ScanResult|null;remoteId:string|null;remoteArtifact:JsonValue|null;onRefresh:()=>void}){return <div className="page-stack"><div className="compare-grid"><div className="panel"><PanelTitle label="LOCAL OBSERVATION" title="What Sentinel saw"/>{selected?<div className="evidence-stack"><Evidence label="Name" value={selected.name}/><Evidence label="Claimed identity" value={selected.declared_type}/><Evidence label="Observed identity" value={selected.detected_type}/><Evidence label="Risk score" value={`${selected.risk_score}/100`}/><Evidence label="SHA-256" value={selected.sha256} mono/></div>:<Empty icon={ScanLine} title="No local artifact" body="Scan a file to populate the comparison."/>}</div><div className="compare-divider"><GitCompareArrows size={18}/></div><div className="panel"><PanelTitle label="PRISM BACKEND" title="Deeper interpretation"/>{remoteId?<JsonPreview body={remoteArtifact} empty="No backend record loaded yet."/>:<Empty icon={CloudUpload} title="Not connected" body="Connect the selected local artifact to see its server-side interpretation here." action={onRefresh} actionLabel="Refresh"/>}</div></div></div>}
function LocalFilesView({onScan,onFolder,watches,onWatch}:{onScan:()=>void;onFolder:()=>void;watches:string[];onWatch:()=>void}){return <div className="page-stack"><div className="hero-grid compact"><div className="hero-copy"><div className="section-label">NATIVE FILE ACCESS</div><h2>Work directly with local files and folders.</h2><p>Sentinel can read real files, recursively scan directories, and maintain watch rules without requiring upload first.</p><div className="hero-actions"><button className="primary" onClick={onScan}><ScanLine size={16}/> Pick a file</button><button className="secondary" onClick={onFolder}><FolderSearch2 size={16}/> Pick a folder</button></div></div><div className="hero-evidence"><div className="section-label">WATCHED</div><strong className="big-number">{watches.length}</strong><span>local location(s)</span><button className="text-btn" onClick={onWatch}>Manage watches <ArrowRight size={14}/></button></div></div></div>}
function PoliciesView({watches}:{watches:string[]}){return <div className="page-stack"><div className="panel"><PanelTitle label="LOCAL POLICY" title="Evidence-first actions"/><p>These are the actual local decision rules implemented by Sentinel. They record evidence and route elevated observations to review; they do not claim malware certainty.</p><div className="policy-rule"><div><strong>Identity mismatch → Review</strong><span>Claimed type and observed magic signature disagree.</span></div><span className="rule-state">ENABLED</span></div><div className="policy-rule"><div><strong>Active-content markers → Review</strong><span>Format-specific markers remain attached to the evidence trail.</span></div><span className="rule-state">ENABLED</span></div><div className="policy-rule"><div><strong>Watched directories</strong><span>{watches.length ? `${watches.length} configured` : 'None configured.'}</span></div><span className="rule-state">LOCAL</span></div></div></div>}
function SettingsView({apiUrl,quarantineDir,onSave}:{apiUrl:string;quarantineDir?:string;onSave:(v:string)=>void}){const [value,setValue]=useState(apiUrl);return <div className="page-stack"><div className="panel settings-card"><PanelTitle label="BACKEND HANDOFF" title="PRISM API endpoint"/><p>Local scanning works without the backend. Use this endpoint when you want the desktop client to connect an artifact to the deeper PRISM investigation stack.</p><div className="form-row"><input value={value} onChange={e=>setValue(e.target.value)} placeholder="PRISM API base URL"/><button className="primary" onClick={()=>onSave(value)}>Save endpoint</button></div>{quarantineDir&&<div className="detail-path"><span>Local quarantine directory</span><code>{quarantineDir}</code></div>}</div><div className="panel"><PanelTitle label="CLIENT" title="Deployment"/><div className="surface-list"><div className="surface-static"><ShieldCheck size={16}/><span><strong>Native Tauri application</strong><small>Windows installer builds through Tauri / NSIS.</small></span></div><div className="surface-static"><LockKeyhole size={16}/><span><strong>Local-first evidence</strong><small>Actual local bytes, SHA-256, paths, and persisted quarantine metadata.</small></span></div></div></div></div>}
function JsonPanel({body,error,loading,empty,embedded=false}:{body:JsonValue|null;error?:string;loading?:boolean;empty:string;embedded?:boolean}){return <div className={embedded?'json-panel embedded':'panel json-wrap'}>{loading?<div className="loading"><RefreshCw size={17} className="spin"/> Loading backend evidence…</div>:error?<div className="error"><CircleAlert size={17}/><div><strong>Backend request failed</strong><span>{error}</span></div></div>:body===null?<div className="empty mini"><Code2 size={18}/><h3>{empty}</h3></div>:<JsonPreview body={body} empty={empty}/>}</div>}
function JsonPreview({body,empty}:{body:JsonValue|null;empty:string}){if(body===null)return <div className="empty mini"><Code2 size={18}/><h3>{empty}</h3></div>;return <pre className="json-pre">{JSON.stringify(body,null,2)}</pre>}
function JsonGraph({body,error,loading}:{body:JsonValue|null;error?:string;loading?:boolean}){return <div className="graph-panel">{loading?<div className="loading"><RefreshCw size={17} className="spin"/> Loading graph evidence…</div>:error?<div className="error"><CircleAlert size={17}/><div><strong>Graph unavailable</strong><span>{error}</span></div></div>:body===null?<div className="empty mini"><Network size={20}/><h3>No graph loaded</h3><p>Connect an artifact and request graph evidence.</p></div>:<GraphFromJson body={body}/>}</div>}
function GraphFromJson({body}:{body:JsonValue}){const obj=isObject(body)?body:null;const nodes=Array.isArray(obj?.nodes)?obj.nodes:[];const edges=Array.isArray(obj?.edges)?obj.edges:[];if(!nodes.length&&Array.isArray(body)) return <pre className="json-pre">{JSON.stringify(body,null,2)}</pre>;return <div className="graph-canvas"><div className="graph-note"><Network size={15}/> {nodes.length} nodes · {edges.length} relationships from backend</div><div className="graph-nodes">{nodes.map((node:any,i:number)=><div className="graph-node" key={i}><div className="node-kind">{String(node.kind??node.type??'node')}</div><strong>{String(node.label??node.name??node.id??`Node ${i+1}`)}</strong><span>{String(node.description??node.identity??'')}</span></div>)}</div>{edges.length>0&&<div className="edge-list">{edges.slice(0,80).map((edge:any,i:number)=><div key={i}><span>{String(edge.source??edge.from??'?')}</span><ArrowRight size={13}/><span>{String(edge.target??edge.to??'?')}</span><em>{String(edge.type??edge.label??edge.relation??'relates')}</em></div>)}</div>}</div>}

function Empty({icon:Icon,title,body,action,actionLabel}:{icon:any;title:string;body:string;action?:()=>void;actionLabel?:string}){return <div className="empty"><div className="empty-icon"><Icon size={21}/></div><h3>{title}</h3><p>{body}</p>{action&&actionLabel&&<button className="secondary" onClick={action}>{actionLabel}</button>}</div>}

ReactDOM.createRoot(document.getElementById('root')!).render(<App/>);
