export interface Artifact {
  artifact_id: string;
  sha256: string;
  original_name: string;
  size_bytes: number;
  claimed_extension: string;
  status: 'INGESTED';
}

export interface ObservedIdentity {
  detected_type: string;
  detected_mime: string;
  magic_description: string;
}

export interface ExtensionConsistency {
  extension_matches_observed: boolean | null;
}

export interface Statistics {
  entropy: number;
}

export interface HeaderEvidence {
  first_bytes_hex: string;
}

export interface IntegrityEvidence {
  sha256_matches_ingestion: boolean;
}

export interface FastScanSignal {
  code: string;
  severity: 'INFO' | 'WARNING' | 'ERROR';
  message: string;
}

export interface FastScanResult {
  artifact_id: string;
  sha256: string;
  size_bytes: number;
  claimed_extension: string;
  observed: ObservedIdentity;
  consistency: ExtensionConsistency;
  statistics: Statistics;
  header: HeaderEvidence;
  integrity: IntegrityEvidence;
  signals: FastScanSignal[];
  scan_status: 'COMPLETE';
}

export interface InterpretationObservations {
  page_count?: number | null;
  encrypted?: boolean | null;
  metadata_present?: boolean | null;
  embedded_files_detected?: boolean | null;
  entry_count?: number | null;
  total_uncompressed_size?: number | null;
  directory_entries?: number | null;
  encrypted_entries?: number | null;
  width?: number | null;
  height?: number | null;
  color_mode?: string | null;
  frame_count?: number | null;
}

export interface InterpreterResult {
  interpreter: string;
  interpreter_version: string;
  recognized: boolean;
  identity: string | null;
  valid: boolean;
  observations: InterpretationObservations;
  warnings: string[];
  errors: string[];
}

export interface Agreement {
  identity: boolean | null;
  validity: boolean;
  page_count?: boolean | null;
  encrypted?: boolean | null;
  entry_count?: boolean | null;
  total_uncompressed_size?: boolean | null;
  image_dimensions?: boolean | null;
}

export interface InterpretationComparison {
  interpreters_run: number;
  interpreters_recognized: number;
  interpreters_valid: number;
  agreement: Agreement;
}

export interface DisagreementSignal {
  code: string;
  interpreters: string[];
  values: Record<string, string | number | boolean>;
}

export interface InterpretationResult {
  artifact_id: string;
  sha256: string;
  artifact_family: 'PDF' | 'ZIP' | 'PNG';
  interpreters: InterpreterResult[];
  comparison: InterpretationComparison;
  signals: DisagreementSignal[];
  status: 'COMPLETE';
}

export interface GraphNodeRecord {
  id: string;
  type: 'ARTIFACT' | 'CLAIM' | 'OBSERVED_IDENTITY' | 'INTERPRETER' | 'OBSERVATION' | 'SIGNAL';
  label: string;
  data: Record<string, unknown>;
}

export interface GraphEdgeRecord {
  source: string;
  target: string;
  type: 'HAS_CLAIM' | 'FASTSCAN_OBSERVED_AS' | 'ANALYZED_BY' | 'INTERPRETED_AS' | 'OBSERVED' | 'HAS_SIGNAL';
}

export interface GraphSummary {
  node_count: number;
  edge_count: number;
  interpreter_count: number;
  disagreement_count: number;
}

export interface InterpretationGraph {
  artifact_id: string;
  sha256: string;
  artifact_family: 'PDF' | 'ZIP' | 'PNG';
  nodes: GraphNodeRecord[];
  edges: GraphEdgeRecord[];
  summary: GraphSummary;
  status: 'COMPLETE';
}
