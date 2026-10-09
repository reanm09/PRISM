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
  structural_features?: Record<string, unknown> | null;
  pretriage_security_features?: Record<string, unknown> | null;
  scan_status: 'COMPLETE';
}

export interface PrismAnalysis {
  artifact_id: string;
  triage: { predicted_state: string; answer_confidence: number; recommended_route: string; feature_stage: string; feature_contract_version: string };
  routing_decision: 'PASS' | 'DEEP_SCAN' | 'PRISM_LAB';
  deep_scan_performed: boolean;
  verified_state: 'SUSPICIOUS' | 'FRACTURED' | null;
  reason_codes: string[];
}

export type VerifiedState = 'SUSPICIOUS' | 'FRACTURED' | null;

export interface ContainmentEvidence {
  status: 'QUARANTINED' | 'RESTORED';
  trigger: 'LAYA_SUSPICIOUS' | 'DETERMINISTIC_SUSPICIOUS';
  laya_prediction: string | null;
  laya_confidence: number | null;
  verified_state: VerifiedState;
  reason_codes: string[];
  quarantined_at: string;
  restored_at: string | null;
}

export interface SemanticEvidenceBundle {
  artifact_id: string;
  sha256: string;
  observed: Record<string, unknown>;
  model_prediction: {
    state?: string;
    confidence?: number;
    recommended_route?: string;
    [key: string]: unknown;
  };
  verified_findings: {
    semantic_fracture_detected?: boolean;
    fractures?: Array<Record<string, unknown>>;
    suspicious_reason_codes?: string[];
    [key: string]: unknown;
  };
  routing_decision: string;
  verified_state: VerifiedState;
  containment: ContainmentEvidence | null;
  investigation?: unknown;
}

export interface InterpreterComparisonSummary {
  total_properties: number;
  agreement_count: number;
  disagreement_count: number;
  not_comparable_count: number;
  status:
    | 'NOT_AVAILABLE'
    | 'COMPARABLE_PROPERTIES_AGREE'
    | 'DISAGREEMENT_PRESENT'
    | 'PARTIAL_COMPARABILITY';
}

export interface ReasoningTraceStep {
  sequence: number;
  stage: string;
  authority: 'DETERMINISTIC' | 'MODEL_ADVISORY' | 'SYSTEM_ACTION';
  summary: string;
  evidence_codes: string[];
}

export interface ExperimentHistoryEntry {
  experiment_kind: string;
  status: string;
  deterministic: boolean;
  deep_scan_performed: boolean;
  verified_state: VerifiedState;
  reason_codes: string[];
}

export interface KnowledgeReference {
  title: string;
  document: string;
  chunk_id: string;
}

export interface SemanticReasoningResult {
  artifact_id: string;
  evidence_summary: SemanticEvidenceBundle;
  reasoning_summary: string;
  retrieval_query: string;

  // Retained backend provenance. The UI intentionally renders the
  // sanitized knowledge_references field instead of raw local paths.
  sources: Array<{
    chunk_id: string;
    source: string;
    score: number;
    metadata: Record<string, unknown>;
  }>;

  hypotheses: Array<{
    statement: string;
    rationale: string;
    supporting_evidence: string[];
  }>;

  uncertainties: string[];

  recommended_experiments: Array<{
    experiment_kind: string | null;
    objective: string;
    rationale: string;
    suggested_action: string;
    expected_information_gain: string;
  }>;

  verified_state: VerifiedState;

  comparison_summary: InterpreterComparisonSummary | null;
  why_prism_reached_state: ReasoningTraceStep[];
  experiment_history: ExperimentHistoryEntry[];
  knowledge_references: KnowledgeReference[];
}

export interface AutonomousInvestigationResult {
  artifact_id: string;
  status: string;
  rounds_completed: number;
  experiments_executed: number;
  stop_reason: string;
  final_verified_state: 'SUSPICIOUS' | 'FRACTURED' | null;
  failure_detail: string | null;
  rounds: Array<{ round_number: number; outcome: string; selected_experiment_kind: string | null; planning?: { plans?: Array<{ status: string; rejection_reason?: string | null }> }; validation_agent?: { assessment: { assessment: string } } | null }>;
}

export interface SentinelStatus {
  enabled: boolean;
  running: boolean;
  watch_root_count: number;
  supported_families: string[];
}

export interface SentinelWatchRoot {
  root_id: string;
  display_name: string;
  recursive: boolean;
  enabled: boolean;
}

export interface SentinelEvent {
  event_id: string;
  timestamp: string;
  event_type: string;
  file_name: string | null;
  artifact_id: string | null;
  artifact_family: 'PDF' | 'ZIP' | 'PNG' | null;
  message: string;
  verified_state: 'SUSPICIOUS' | 'FRACTURED' | null;
  routing_decision: 'PASS' | 'DEEP_SCAN' | 'PRISM_LAB' | null;
  laya_prediction: string | null;
  reason_codes: string[];
  quarantine_id?: string | null;
  containment_state?: 'QUARANTINED' | null;
  containment_trigger?: 'LAYA_SUSPICIOUS' | 'DETERMINISTIC_SUSPICIOUS' | null;
  container_name?: string | null;
  laya_confidence?: number | null;
}

export interface QuarantineRecord {
  quarantine_id: string;
  artifact_id: string;
  original_name: string;
  container_name: string;
  sha256: string;
  trigger: 'LAYA_SUSPICIOUS' | 'DETERMINISTIC_SUSPICIOUS';
  laya_prediction: string | null;
  laya_confidence: number | null;
  verified_state: 'SUSPICIOUS' | 'FRACTURED' | null;
  reason_codes: string[];
  quarantined_at: string;
  status: 'QUARANTINED' | 'RESTORED';
  restored_at: string | null;
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

  javascript_action_count?: number | null;
  launch_action_count?: number | null;
  richmedia_count?: number | null;

  entry_names?: string[] | null;
  duplicate_entry_names?: string[] | null;
  path_traversal_entry_count?: number | null;
  absolute_path_entry_count?: number | null;
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

export type ComparisonStatus =
  | 'AGREEMENT'
  | 'DISAGREEMENT'
  | 'NOT_COMPARABLE';

export interface PropertyComparison {
  property_name: string;
  signal_code: string;
  status: ComparisonStatus;
  interpreters: string[];
  values: Record<string, unknown>;
  reason: string | null;
}

export interface ComparisonCoverage {
  total: number;
  agreement_count: number;
  disagreement_count: number;
  not_comparable_count: number;
}

export interface InterpretationComparison {
  interpreters_run: number;
  interpreters_recognized: number;
  interpreters_valid: number;

  // Legacy compact comparison retained by the backend.
  agreement: Agreement;

  // Evidence Intelligence V2.
  properties: PropertyComparison[];
  coverage: ComparisonCoverage;
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
