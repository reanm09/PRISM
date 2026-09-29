'use client';

import '@xyflow/react/dist/style.css';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Background, Controls, Edge, Node, ReactFlow, ReactFlowProvider, useEdgesState, useNodesState, useReactFlow } from '@xyflow/react';
import { Maximize2, Minus, Plus, RefreshCw } from 'lucide-react';
import { Suspense, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AppShell } from '@/components/app-shell';
import { EmptyState, ErrorState, LoadingState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { getGraph, PrismApiError } from '@/lib/api';
import { getRecentArtifacts } from '@/lib/recent-artifacts';

type GraphData = Awaited<ReturnType<typeof getGraph>>;

export default function GraphPage() {
  return <Suspense fallback={<AppShell><div className="mx-auto max-w-[1640px] px-6 py-7"><LoadingState label="Loading graph workspace" /></div></AppShell>}><GraphContent /></Suspense>;
}

function GraphContent() {
  const params = useSearchParams();
  const artifactId = params.get('artifact') || getRecentArtifacts()[0]?.artifact_id || '';
  const query = useQuery({ queryKey: ['graph', artifactId], queryFn: () => getGraph(artifactId), enabled: Boolean(artifactId), retry: false });
  return <AppShell><div className="mx-auto max-w-[1640px] px-6 py-7"><PageHeader eyebrow="Investigation" title="Interpretation Graph" description="Relationships generated from the connected backend's FastScan and interpreter observations." />{!artifactId ? <EmptyState title="No artifact selected" description="Upload an artifact first, then open its graph from the artifact analysis workspace." action={<Link href="/artifacts" className="rounded-md bg-[var(--cobalt)] px-3 py-2 text-sm font-medium text-white">Open artifacts</Link>} /> : query.isLoading ? <LoadingState label="Loading interpretation graph" /> : query.isError ? <ErrorState title="Graph unavailable" description={query.error instanceof PrismApiError && query.error.status === 404 ? 'The artifact has not produced a graph yet. Run its analysis pipeline first.' : query.error instanceof Error ? query.error.message : 'The graph endpoint could not be reached.'} action={<Link href={`/artifacts/${artifactId}`} className="rounded-md bg-[var(--cobalt)] px-3 py-2 text-sm font-medium text-white">Open artifact</Link>} /> : <GraphWorkspace artifactId={artifactId} graph={query.data} onRefresh={() => void query.refetch()} refreshing={query.isFetching} />}</div></AppShell>;
}

function GraphWorkspace({ artifactId, graph, onRefresh, refreshing }: { artifactId: string; graph: GraphData; onRefresh: () => void; refreshing: boolean }) {
  return <ReactFlowProvider><GraphCanvas artifactId={artifactId} graph={graph} onRefresh={onRefresh} refreshing={refreshing} /></ReactFlowProvider>;
}

function GraphCanvas({ artifactId, graph, onRefresh, refreshing }: { artifactId: string; graph: GraphData; onRefresh: () => void; refreshing: boolean }) {
  const initialNodes = useMemo<Node[]>(() => layoutNodes(graph.nodes), [graph.nodes]);
  const initialEdges = useMemo<Edge[]>(() => graph.edges.map((edge) => ({ id: `${edge.source}-${edge.target}-${edge.type}`, source: edge.source, target: edge.target, label: edge.type, type: 'smoothstep' })), [graph.edges]);
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);
  const { fitView, zoomIn, zoomOut } = useReactFlow();

  useEffect(() => { void fitView({ padding: 0.18, duration: 200 }); }, [fitView, graph]);

  return <section className="panel-card overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3"><div><div className="text-sm font-semibold">{graph.artifact_family} interpretation graph</div><div className="mt-0.5 text-xs text-[var(--muted)]">{graph.summary.node_count} nodes · {graph.summary.edge_count} edges · {graph.summary.interpreter_count} interpreters · {graph.summary.disagreement_count} disagreement signals</div></div><div className="flex items-center gap-1"><button onClick={() => void zoomOut()} className="icon-button" aria-label="Zoom out"><Minus size={15} /></button><button onClick={() => void zoomIn()} className="icon-button" aria-label="Zoom in"><Plus size={15} /></button><button onClick={() => void fitView({ padding: 0.18 })} className="icon-button" aria-label="Fit graph"><Maximize2 size={15} /></button><button onClick={onRefresh} disabled={refreshing} className="action-button ml-1"><RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />Refresh</button><Link href={`/artifacts/${artifactId}`} className="action-button">Artifact</Link></div></div><div className="grid-paper h-[680px]"><ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} fitView minZoom={0.2} maxZoom={2} attributionPosition="bottom-left"><Background gap={24} size={1} /><Controls showInteractive={false} /></ReactFlow></div></section>;
}

function layoutNodes(records: GraphData['nodes']): Node[] {
  const columns: Record<string, number> = { ARTIFACT: 0, CLAIM: 1, OBSERVED_IDENTITY: 1, INTERPRETER: 2, OBSERVATION: 3, SIGNAL: 3 };
  const offsets: Record<number, number> = {};
  return records.map((record) => {
    const col = columns[record.type] ?? 2;
    offsets[col] = (offsets[col] ?? 0) + 1;
    const row = offsets[col] - 1;
    return { id: record.id, position: { x: col * 270, y: row * 105 }, data: { label: <div><div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">{record.type}</div><div className="mt-1 text-xs font-semibold leading-4">{record.label}</div></div> }, style: { width: 220, border: '1px solid #d9d4cc', borderRadius: 8, background: '#fbfaf7', padding: 12, boxShadow: '0 5px 18px rgba(26,29,35,0.035)' } };
  });
}
