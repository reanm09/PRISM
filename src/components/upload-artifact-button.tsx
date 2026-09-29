'use client';

import { Upload } from 'lucide-react';
import { useState } from 'react';
import { UploadArtifactDialog } from './upload-artifact-dialog';

export function UploadArtifactButton({ compact = false }: { compact?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={`inline-flex items-center gap-2 rounded-md bg-[var(--cobalt)] px-3.5 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-[var(--cobalt-hover)] disabled:opacity-50 ${compact ? 'px-3 py-1.5 text-xs' : ''}`}
      >
        <Upload size={compact ? 14 : 16} strokeWidth={1.8} />
        Analyze Artifact
      </button>
      <UploadArtifactDialog open={open} onClose={() => setOpen(false)} />
    </>
  );
}
