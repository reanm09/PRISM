'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ChevronRight, Copy, GitBranch, RefreshCw, ScanSearch } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { EmptyState, ErrorState, LoadingState } from '@/components/empty-state';
import { buildGraph, getArtifact, getFastScan, getGraph, getInterpretation, PrismApiError, runFastScan, runInterpretation } from '@/lib/api';
import { rememberArtifact } from '@/lib/recent-artifacts';
import type { Artifact, FastScanResult, InterpretationGraph, InterpretationResult } from '@/lib/types';

const tabs = [['Overview', 'overview'], ['FastScan', 'fastscan'], ['Interpretations', 'interpretations'], ['Graph', 'graph']] as const;
type PipelineStage = 'idle' | 'running' | 'complete' | 'error';
type PipelineState = { fastscan: PipelineStage; interpretation: PipelineStage; graph: PipelineStage };

export default function ArtifactPage() {
  const params = useParams<{ id: string }>();
  const artifactId = params.id;
  const queryClient = useQueryClient();
  const router = useRouter();
  const [pipeline, setPipeline] = useState<PipelineState>({ fastscan: 'idle', interpretation: 'idle', graph: 'idle' });
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const started = useRef(false);

  const artifactQuery = useQuery({ queryKey: ['artifact', artifactId], queryFn: () => getArtifact(artifactId), enabled: Boolean(artifactId), retry: false });
  const fastscanQuery = useQuery({ queryKey: ['fastscan', artifactId], queryFn: () => getFastScan(artifactId), enabled: Boolean(artifactId) && !artifactQuery.isError, retry: false });
  const interpretationQuery = useQuery({ queryKey: ['interpretation', artifactId], queryFn: () => getInterpretation(artifactId), enabled: Boolean(artifactId) && Boolean(fastscanQuery.data) && !artifactQuery.isError, retry: false });
  const graphQuery = useQuery({ queryKey: ['graph', artifactId], queryFn: () => getGraph(artifactId), enabled: Boolean(artifactId) && Boolean(interpretationQuery.data) && !artifactQuery.isError, retry: false });

  async function runPipeline() {
    if (!artifactId) return;
    setPipelineError(null);
    let currentStage: keyof PipelineState = 'fastscan';
    try {
      if (!fastscanQuery.data) {
        setPipeline((v) => ({ ...v, fastscan: 'running', interpretation: 'idle', graph: 'idle' }));
        await runFastScan(artifactId);
        setPipeline((v) => ({ ...v, fastscan: 'complete' }));
      } else setPipeline((v) => ({ ...v, fastscan: 'complete' }));

      currentStage = 'interpretation';
      if (!interpretationQuery.data) {
        setPipeline((v) => ({ ...v, interpretation: 'running' }));
        await runInterpretation(artifactId);
        setPipeline((v) => ({ ...v, interpretation: 'complete' }));
      } else setPipeline((v) => ({ ...v, interpretation: 'complete' }));

      currentStage = 'graph';
      if (!graphQuery.data) {
        setPipeline((v) => ({ ...v, graph: 'running' }));
        await buildGraph(artifactId);
        setPipeline((v) => ({ ...v, graph: 'complete' }));
      } else setPipeline((v) => ({ ...v, graph: 'complete' }));

      await queryClient.invalidateQueries({ queryKey: ['fastscan', artifactId] });
      await queryClient.invalidateQueries({ queryKey: ['interpretation', artifactId] });
      await queryClient.invalidateQueries({ queryKey: ['graph', artifactId] });
    } catch (error) {
      setPipelineError(error instanceof Error ? error.message : 'Analysis pipeline failed.');
      setPipeline((v) => ({ ...v, [currentStage]: 'error' }));
    }
  }

  useEffect(() => {
    if (!artifactQuery.data || started.current) return;
    if (fastscanQuery.isLoading || interpretationQuery.isLoading || graphQuery.isLoading) return;
    started.current = true;
    if (!fastscanQuery.data || is404(fastscanQuery.error) || !interpretationQuery.data || is404(interpretationQuery.error) || !graphQuery.data || is404(graphQuery.error)) void runPipeline();
    else setPipeline({ fastscan: 'complete', interpretation: 'complete', graph: 'complete' });
    // One automatic run per artifact page; the button remains available for retries.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [artifactQuery.data, fastscanQuery.isLoading, interpretationQuery.isLoading, graphQuery.isLoading]);

  if (artifactQuery.isLoading) return <ShellState><LoadingState label="Loading artifact" /></ShellState>;
  if (artifactQuery.isError || !artifactQuery.data) return <ShellState><ErrorState title="Artifact could not be loaded" description={artifactQuery.error instanceof Error ? artifactQuery.error.message : 'The backend did not return this artifact.'} action={<Link href="/artifacts" className="rounded-md bg-[var(--cobalt)] px-3 py-2 text-sm font-medium text-white">Back to artifacts</Link>} /></ShellState>;

  rememberArtifact(artifactQuery.data);
  const signalCount = (fastscanQuery.data?.signals.length ?? 0) + (interpretationQuery.data?.signals.length ?? 0);
  return <ArtifactWorkspace artifact={artifactQuery.data} fastscan={fastscanQuery.data} interpretation={interpretationQuery.data} graph={graphQuery.data} signalCount={signalCount} pipeline={pipeline} pipelineError={pipelineError} running={Object.values(pipeline).includes('running')} onRun={runPipeline} onRefresh={() => { void artifactQuery.refetch(); void fastscanQuery.refetch(); void interpretationQuery.refetch(); void graphQuery.refetch(); }} onOpenGraph={() => router.push(`/graph?artifact=${encodeURIComponent(artifactId)}`)} />;
}

function ShellState({ children }: { children: React.ReactNode }) { return <AppShell><div className="mx-auto max-w-[1640px] px-6 py-7">{children}</div></AppShell>; }

function ArtifactWorkspace({ artifact, fastscan, interpretation, graph, signalCount, pipeline, pipelineError, running, onRun, onRefresh, onOpenGraph }: { artifact: Artifact; fastscan?: FastScanResult; interpretation?: InterpretationResult; graph?: InterpretationGraph; signalCount: number; pipeline: PipelineState; pipelineError: string | null; running: boolean; onRun: () => void; onRefresh: () => void; onOpenGraph: () => void }) {
  return <div className="mx-auto max-w-[1640px] px-6 py-7">
    <div className="mb-4 flex items-center gap-2 text-xs text-[var(--muted)]"><Link href="/artifacts" className="hover:text-[var(--ink)]">Artifacts</Link><ChevronRight size={13} /><span className="truncate font-medium text-[var(--ink)]">{artifact.original_name || 'Unnamed artifact'}</span></div>
    <section className="panel-card p-5"><div className="flex flex-wrap items-start justify-between gap-5"><div className="flex min-w-0 gap-4"><FileBadge extension={artifact.claimed_extension} /><div className="min-w-0"><h1 className="break-all text-[26px] font-semibold tracking-[-0.04em]">{artifact.original_name || '(unnamed artifact)'}</h1><div className="mt-1 flex items-center gap-2"><span className="max-w-[760px] truncate font-mono text-[11px] text-[var(--muted)]">{artifact.sha256}</span><CopyButton value={artifact.sha256} /></div><div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--muted)]"><span>{formatBytes(artifact.size_bytes)}</span><span>Claimed extension: {artifact.claimed_extension || '—'}</span><span>Artifact ID: {artifact.artifact_id}</span></div></div></div><div className="flex items-center gap-2"><button onClick={onRefresh} className="action-button"><RefreshCw size={14} />Refresh</button><button onClick={onRun} disabled={running} className="inline-flex min-h-8 items-center gap-2 rounded-md bg-[var(--cobalt)] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"><ScanSearch size={14} />{running ? 'Analyzing…' : 'Run analysis'}</button></div></div><div className="mt-5 flex flex-wrap items-center gap-3 rounded-md border border-[var(--border)] bg-[var(--panel-muted)] px-3 py-2.5 text-xs"><span className="font-medium">Backend pipeline</span><PipelineChip label="FastScan" state={pipeline.fastscan} /><PipelineChip label="Interpretation" state={pipeline.interpretation} /><PipelineChip label="Graph" state={pipeline.graph} />{pipelineError ? <span className="text-[var(--danger)]">{pipelineError}</span> : null}</div></section>

    <nav className="mt-4 flex flex-wrap gap-1 border-b border-[var(--border)]">{tabs.map(([label, id], index) => <a key={id} href={`#${id}`} className={`px-3 py-2.5 text-xs ${index === 0 ? 'border-b-2 border-[var(--cobalt)] font-semibold text-[var(--cobalt)]' : 'text-[var(--muted)] hover:text-[var(--ink)]'}`}>{label}</a>)}</nav>

    <div className="mt-4 space-y-4">
      <section id="overview" className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]"><section className="panel-card p-5"><SectionHeading title="Observed identity" text="Byte-level evidence returned by the current FastScan service." />{fastscan ? <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><InfoItem label="Detected type" value={fastscan.observed.detected_type} /><InfoItem label="Detected MIME" value={fastscan.observed.detected_mime} /><InfoItem label="Magic" value={fastscan.observed.magic_description} /><InfoItem label="Entropy" value={String(fastscan.statistics.entropy)} mono /></div> : <EmptyState compact title="FastScan not available" description="The analysis pipeline will populate this section." />}</section><section className="panel-card p-5"><SectionHeading title="Evidence summary" text="Counts below come from the backend responses for this artifact." /><div className="mt-4 space-y-2"><InfoRow label="FastScan signals" value={String(fastscan?.signals.length ?? 0)} /><InfoRow label="Disagreement signals" value={String(interpretation?.signals.length ?? 0)} /><InfoRow label="Total signals" value={String(signalCount)} /><InfoRow label="Graph nodes" value={graph ? String(graph.summary.node_count) : '—'} /></div></section></section>

      <section id="fastscan" className="panel-card p-5"><SectionHeading title="FastScan" text="SHA-256, byte-observed identity, extension consistency, entropy, header evidence, and integrity." />{fastscan ? <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1fr]"><div className="grid gap-3 sm:grid-cols-2"><InfoItem label="Claimed extension" value={fastscan.claimed_extension || '—'} /><InfoItem label="Observed identity" value={fastscan.observed.detected_type} /><InfoItem label="Extension match" value={formatBool(fastscan.consistency.extension_matches_observed)} /><InfoItem label="Hash integrity" value={formatBool(fastscan.integrity.sha256_matches_ingestion)} /><InfoItem label="Size" value={formatBytes(fastscan.size_bytes)} /><InfoItem label="First 32 bytes" value={fastscan.header.first_bytes_hex} mono /></div><div className="rounded-md border border-[var(--border)] bg-[var(--panel-muted)] p-4"><div className="text-xs font-semibold">Signals</div>{fastscan.signals.length ? <div className="mt-3 space-y-2">{fastscan.signals.map((s) => <SignalRow key={s.code} code={s.code} severity={s.severity} message={s.message} />)}</div> : <div className="mt-3 text-sm text-[var(--muted)]">No FastScan signals were returned.</div>}</div></div> : <EmptyState compact title="FastScan unavailable" description="Run analysis to create this result." />}</section>

      <section id="interpretations" className="panel-card p-5"><SectionHeading title="Interpretations" text="The backend runs two independent interpreters for the observed PDF, PNG, or ZIP family and compares their results." />{interpretation ? <div className="mt-4"><div className="mb-4 grid gap-3 sm:grid-cols-3"><InfoItem label="Family" value={interpretation.artifact_family} /><InfoItem label="Recognized" value={`${interpretation.comparison.interpreters_recognized} / ${interpretation.comparison.interpreters_run}`} /><InfoItem label="Valid" value={`${interpretation.comparison.interpreters_valid} / ${interpretation.comparison.interpreters_run}`} /></div><div className="overflow-hidden rounded-md border border-[var(--border)]"><div className="grid grid-cols-[1.1fr_90px_80px_1fr] gap-3 border-b border-[var(--border)] bg-[var(--panel-muted)] px-4 py-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--muted)]"><span>Interpreter</span><span>Recognized</span><span>Valid</span><span>Observations</span></div>{interpretation.interpreters.map((item) => <div key={item.interpreter} className="grid grid-cols-[1.1fr_90px_80px_1fr] gap-3 border-b border-[var(--border)] px-4 py-3 text-xs last:border-b-0"><div><div className="font-semibold">{item.interpreter}</div><div className="mt-0.5 font-mono text-[10px] text-[var(--muted)]">{item.interpreter_version}</div></div><span>{item.recognized ? 'Yes' : 'No'}</span><span>{item.valid ? 'Yes' : 'No'}</span><span className="text-[var(--muted)]">{Object.entries(item.observations).filter(([, value]) => value !== null && value !== undefined).map(([key, value]) => `${key}: ${String(value)}`).join(' · ') || 'No observations'}</span></div>)}</div></div> : <EmptyState compact title="Interpretation unavailable" description="Run FastScan first; the backend requires it before interpretation." />}</section>

      <section className="panel-card p-5"><SectionHeading title="Disagreement signals" text="The supplied backend records normalized comparison signals, not a separate fracture entity." />{interpretation?.signals.length ? <div className="mt-4 space-y-2">{interpretation.signals.map((signal) => <div key={signal.code} className="rounded-md border border-[#e8d7cf] bg-[#fff9f6] p-3"><div className="flex flex-wrap items-center gap-2"><span className="mono text-[10px] font-semibold text-[#8d4b3d]">{signal.code}</span><span className="text-[10px] text-[var(--muted)]">{signal.interpreters.join(' vs ')}</span></div><div className="mt-2 grid gap-2 sm:grid-cols-2">{Object.entries(signal.values).map(([name, value]) => <InfoRow key={name} label={name} value={String(value)} />)}</div></div>)}</div> : <EmptyState compact title="No disagreement signals" description="The interpreter comparison returned no differences for the tracked fields." />}</section>

      <section id="graph" className="panel-card p-5"><div className="flex items-start justify-between gap-3"><SectionHeading title="Interpretation Graph" text="Graph nodes and edges are generated directly by the supplied backend." />{graph ? <button onClick={onOpenGraph} className="action-button"><GitBranch size={14} />Open graph</button> : null}</div>{graph ? <div className="mt-4 grid gap-3 sm:grid-cols-4"><InfoItem label="Nodes" value={String(graph.summary.node_count)} /><InfoItem label="Edges" value={String(graph.summary.edge_count)} /><InfoItem label="Interpreters" value={String(graph.summary.interpreter_count)} /><InfoItem label="Disagreement" value={String(graph.summary.disagreement_count)} /></div> : <EmptyState compact title="Graph unavailable" description="Interpretation must complete before the graph endpoint can build a graph." />}</section>
    </div>
  </div>;
}

function PipelineChip({ label, state }: { label: string; state: PipelineStage }) { const text = state === 'complete' ? 'Complete' : state === 'running' ? 'Running' : state === 'error' ? 'Error' : 'Pending'; return <span className="rounded-full border border-[var(--border)] bg-[var(--panel)] px-2.5 py-1 text-[10px] font-semibold">{label}: {text}</span>; }
function SectionHeading({ title, text }: { title: string; text?: string }) { return <div><h2 className="text-sm font-semibold tracking-[-0.015em]">{title}</h2>{text ? <p className="mt-1 max-w-3xl text-xs leading-5 text-[var(--muted)]">{text}</p> : null}</div>; }
function InfoItem({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) { return <div className="rounded-md border border-[var(--border)] bg-[var(--panel-muted)] px-3 py-3"><div className="text-[10px] uppercase tracking-[0.11em] text-[var(--muted)]">{label}</div><div className={`mt-1 break-words text-sm font-semibold ${mono ? 'mono text-xs' : ''}`}>{value}</div></div>; }
function InfoRow({ label, value }: { label: string; value: string }) { return <div className="flex items-center justify-between gap-4 border-b border-[var(--border)] py-2 last:border-b-0"><span className="text-xs text-[var(--muted)]">{label}</span><span className="text-right text-xs font-medium">{value}</span></div>; }
function SignalRow({ code, severity, message }: { code: string; severity: string; message: string }) { const tone = severity === 'ERROR' ? 'text-[var(--danger)]' : severity === 'WARNING' ? 'text-[var(--warning)]' : 'text-[var(--muted)]'; return <div className="rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2.5"><div className="flex items-center justify-between gap-3"><span className="mono text-[10px] font-semibold">{code}</span><span className={`text-[10px] font-semibold ${tone}`}>{severity}</span></div><div className="mt-1 text-xs leading-5 text-[var(--muted)]">{message}</div></div>; }
function FileBadge({ extension }: { extension: string }) { return <div className="grid h-14 w-14 shrink-0 place-items-center rounded-lg border border-[#d9d2c9] bg-[#f3efe9] text-[10px] font-bold tracking-[0.08em] text-[#6f6a62]">{(extension.replace('.', '').toUpperCase() || 'FILE').slice(0,7)}</div>; }
function CopyButton({ value }: { value: string }) { return <button className="icon-button h-7 w-7" onClick={() => void navigator.clipboard?.writeText(value)} aria-label="Copy SHA-256"><Copy size={13} /></button>; }
function formatBytes(bytes: number) { if (bytes < 1024) return `${bytes} B`; if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`; if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`; return `${(bytes / 1024 ** 3).toFixed(1)} GB`; }
function formatBool(value: boolean | null | undefined) { return value == null ? '—' : value ? 'Yes' : 'No'; }
function is404(error: unknown) { return error instanceof PrismApiError && error.status === 404; }
