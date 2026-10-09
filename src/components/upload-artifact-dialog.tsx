'use client';

import { AlertCircle, Check, FileUp, LoaderCircle, X } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { uploadArtifact } from '@/lib/api';
import { rememberArtifact } from '@/lib/recent-artifacts';

export function UploadArtifactDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);

  if (!open) return null;

  function selectFile(next: File | null) {
    setFile(next);
    setStatus(null);
  }

  async function submit() {
    if (!file || busy) return;
    setBusy(true);
    setStatus(null);
    try {
      const created = await uploadArtifact(file);
      rememberArtifact(created);
      onClose();
      router.push(`/artifacts/${created.artifact_id}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to submit artifact.');
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[rgba(20,21,24,0.32)] p-4 backdrop-blur-[3px]" role="dialog" aria-modal="true" aria-labelledby="analyze-artifact-title">
      <div className="w-full max-w-xl overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--panel)] shadow-[0_24px_70px_rgba(24,28,35,0.16)]">
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
          <div><h2 id="analyze-artifact-title" className="text-base font-semibold">Analyze artifact</h2><p className="mt-0.5 text-xs text-[var(--muted)]">Upload the original bytes to the connected PRISM backend.</p></div>
          <button onClick={onClose} disabled={busy} className="grid h-8 w-8 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--panel-muted)] disabled:opacity-40" aria-label="Close"><X size={17} /></button>
        </div>
        <div className="space-y-5 p-5">
          <label className={`block cursor-pointer rounded-lg border border-dashed p-8 text-center transition ${dragging ? 'border-[var(--cobalt)] bg-[var(--cobalt-soft)]' : 'border-[#c9c5bc] bg-[#fcfbf8] hover:border-[var(--cobalt)]'}`} onDragEnter={(e) => { e.preventDefault(); setDragging(true); }} onDragOver={(e) => e.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); selectFile(e.dataTransfer.files?.[0] ?? null); }}>
            <input type="file" className="sr-only" disabled={busy} onChange={(e) => selectFile(e.target.files?.[0] ?? null)} />
            {busy ? <LoaderCircle className="mx-auto animate-spin text-[var(--cobalt)]" size={28} /> : <FileUp className="mx-auto text-[var(--cobalt)]" size={28} />}
            <div className="mt-3 text-sm font-semibold">{file ? file.name : 'Drop an artifact here'}</div>
            <div className="mt-1 text-xs leading-5 text-[var(--muted)]">{file ? `${formatBytes(file.size)}${file.type ? ` · ${file.type}` : ''}` : 'or click to browse. The backend enforces its upload limit.'}</div>
          </label>
          <div className="rounded-md border border-[var(--border)] bg-[var(--panel-muted)] px-3 py-2.5"><div className="flex items-center gap-2 text-xs font-semibold"><Check size={14} className="text-[var(--success)]" /> Connected backend flow</div><p className="mt-1 text-xs leading-5 text-[var(--muted)]">Upload → FastScan and Laya triage → deterministic analysis when required. PDF, PNG, and ZIP are supported.</p></div>
          {status ? <div className="flex items-start gap-2 rounded-md border border-[#e6c7c4] bg-[#fff8f7] px-3 py-2.5 text-xs leading-5 text-[#7f4b47]"><AlertCircle size={15} className="mt-0.5 shrink-0" /><span>{status}</span></div> : null}
          <div className="flex justify-end gap-2"><button onClick={onClose} disabled={busy} className="rounded-md border border-[var(--border)] bg-[var(--panel)] px-3.5 py-2 text-sm font-semibold disabled:opacity-50">Cancel</button><button onClick={submit} disabled={!file || busy} className="inline-flex items-center gap-2 rounded-md bg-[var(--cobalt)] px-3.5 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{busy ? <LoaderCircle size={15} className="animate-spin" /> : null}{busy ? 'Uploading…' : 'Upload artifact'}</button></div>
        </div>
      </div>
    </div>
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}
