"use client";

import type {
  InterpretationResult,
  SemanticReasoningResult,
} from '@/lib/types';


export function EvidenceIntelligence({
  reasoning,
}: {
  reasoning: SemanticReasoningResult;
}) {
  const verifiedCodes =
    reasoning.evidence_summary.verified_findings
      .suspicious_reason_codes ?? [];

  const fractures =
    reasoning.evidence_summary.verified_findings.fractures ?? [];

  const model = reasoning.evidence_summary.model_prediction;
  const containment = reasoning.evidence_summary.containment;

  return (
    <section className="panel-card mt-4 p-5">
      <div>
        <h2 className="text-sm font-semibold tracking-[-0.015em]">
          Evidence Intelligence
        </h2>

        <p className="mt-1 max-w-3xl text-xs leading-5 text-[var(--muted)]">
          Deterministic evidence, system actions, and advisory model
          reasoning are separated so containment or model predictions
          are never mistaken for verified artifact state.
        </p>
      </div>


      {/* ====================================================== */}
      {/* WHY PRISM REACHED THIS STATE                          */}
      {/* ====================================================== */}

      <div className="mt-5">
        <Subheading
          title="Why PRISM reached this state"
          text="This trace is assembled by backend code from recorded evidence and actions."
        />

        <div className="mt-3 space-y-2">
          {reasoning.why_prism_reached_state.map((step) => (
            <div
              key={`${step.sequence}-${step.stage}`}
              className="grid gap-3 rounded-md border border-[var(--border)] bg-[var(--panel-muted)] px-3 py-3 md:grid-cols-[36px_180px_150px_minmax(0,1fr)]"
            >
              <span className="font-mono text-[10px] text-[var(--muted)]">
                {String(step.sequence).padStart(2, '0')}
              </span>

              <span className="text-xs font-semibold">
                {humanize(step.stage)}
              </span>

              <AuthorityBadge authority={step.authority} />

              <div>
                <p className="text-xs leading-5">
                  {step.summary}
                </p>

                {step.evidence_codes.length ? (
                  <p className="mt-1 font-mono text-[10px] text-[var(--muted)]">
                    {step.evidence_codes.join(' ? ')}
                  </p>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </div>


      {/* ====================================================== */}
      {/* VERIFIED EVIDENCE + MODEL ASSESSMENT                  */}
      {/* ====================================================== */}

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <div className="rounded-md border border-[var(--border)] p-4">
          <Subheading
            title="Verified evidence"
            text="Only deterministic findings appear here."
          />

          {verifiedCodes.length || fractures.length ? (
            <div className="mt-3 space-y-2">
              {verifiedCodes.map((code) => (
                <EvidenceCode
                  key={code}
                  code={code}
                />
              ))}

              {fractures.map((fracture, index) => (
                <EvidenceCode
                  key={`fracture-${index}`}
                  code={
                    stringField(fracture, 'source_signal') ??
                    stringField(fracture, 'fracture_type') ??
                    `SEMANTIC_FRACTURE_${index + 1}`
                  }
                  detail="Semantic Fracture verified by deterministic analysis"
                />
              ))}
            </div>
          ) : (
            <p className="mt-3 text-xs leading-5 text-[var(--muted)]">
              Current deterministic evidence has not established
              SUSPICIOUS or FRACTURED. PRISM does not convert that
              absence into verified BENIGN.
            </p>
          )}
        </div>


        <div className="rounded-md border border-[var(--border)] p-4">
          <Subheading
            title="Model assessment"
            text="Laya is routing evidence, not verification authority."
          />

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <Metric
              label="Prediction"
              value={model.state ?? 'Unavailable'}
            />

            <Metric
              label="Confidence"
              value={
                typeof model.confidence === 'number'
                  ? `${(model.confidence * 100).toFixed(2)}%`
                  : 'Unavailable'
              }
            />

            <Metric
              label="Recommended route"
              value={model.recommended_route ?? 'Unavailable'}
            />

            <Metric
              label="Authority"
              value="MODEL ADVISORY"
            />
          </div>


          {containment ? (
            <div className="mt-3 rounded-md border border-[var(--border)] bg-[var(--panel-muted)] p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold">
                  {containment.status === 'QUARANTINED'
                    ? 'Active containment'
                    : 'Containment history'}
                </span>

                <AuthorityBadge authority="SYSTEM_ACTION" />
              </div>

              <p className="mt-2 text-xs leading-5 text-[var(--muted)]">
                Trigger: {containment.trigger}. Containment is a
                protective system action and does not independently
                establish verified state.
              </p>
            </div>
          ) : null}
        </div>
      </div>


      {/* ====================================================== */}
      {/* ADVISORY SEMANTIC REASONING                           */}
      {/* ====================================================== */}

      <div className="mt-5 rounded-md border border-[var(--border)] p-4">
        <Subheading
          title="Semantic reasoning"
          text="Grounded generative interpretation remains advisory."
        />

        <p className="mt-3 text-sm leading-6">
          {reasoning.reasoning_summary}
        </p>


        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <TextList
            title="Hypotheses"
            items={reasoning.hypotheses.map(
              (item) => item.statement
            )}
            empty="No hypotheses proposed."
          />

          <TextList
            title="Uncertainties"
            items={reasoning.uncertainties}
            empty="No uncertainties reported."
          />
        </div>


        <div className="mt-4">
          <h4 className="text-xs font-semibold">
            Recommended investigation
          </h4>

          {reasoning.recommended_experiments.length ? (
            <div className="mt-2 space-y-2">
              {reasoning.recommended_experiments.map(
                (experiment, index) => (
                  <div
                    key={`${experiment.experiment_kind ?? 'proposal'}-${index}`}
                    className="rounded-md bg-[var(--panel-muted)] px-3 py-3"
                  >
                    <div className="text-xs font-semibold">
                      {experiment.experiment_kind ??
                        experiment.objective}
                    </div>

                    <p className="mt-1 text-xs leading-5 text-[var(--muted)]">
                      {experiment.rationale}
                    </p>
                  </div>
                )
              )}
            </div>
          ) : (
            <p className="mt-2 text-xs text-[var(--muted)]">
              No additional experiment is currently recommended.
            </p>
          )}
        </div>
      </div>


      {/* ====================================================== */}
      {/* EXPERIMENT HISTORY + KNOWLEDGE REFERENCES             */}
      {/* ====================================================== */}

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <div className="rounded-md border border-[var(--border)] p-4">
          <Subheading
            title="Experiment history"
            text="Completed deterministic Lab work already known to this reasoning pass."
          />

          {reasoning.experiment_history.length ? (
            <div className="mt-3 space-y-2">
              {reasoning.experiment_history.map(
                (experiment, index) => (
                  <div
                    key={`${experiment.experiment_kind}-${index}`}
                    className="rounded-md bg-[var(--panel-muted)] px-3 py-3"
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <strong>
                        {experiment.experiment_kind}
                      </strong>

                      <span>
                        {experiment.status}
                      </span>

                      <span className="text-[var(--muted)]">
                        {experiment.deterministic
                          ? 'Deterministic'
                          : 'Non-deterministic'}
                      </span>
                    </div>

                    <p className="mt-1 text-xs text-[var(--muted)]">
                      {experiment.verified_state
                        ? `Verified state: ${experiment.verified_state}`
                        : 'No deterministic verified state established by this experiment.'}
                    </p>

                    {experiment.reason_codes.length ? (
                      <p className="mt-1 font-mono text-[10px] text-[var(--muted)]">
                        {experiment.reason_codes.join(' ? ')}
                      </p>
                    ) : null}
                  </div>
                )
              )}
            </div>
          ) : (
            <p className="mt-3 text-xs text-[var(--muted)]">
              No completed Lab experiments are recorded for this
              reasoning pass.
            </p>
          )}
        </div>


        <div className="rounded-md border border-[var(--border)] p-4">
          <Subheading
            title="Knowledge references"
            text="User-facing references are sanitized; local knowledge paths are not exposed."
          />

          {reasoning.knowledge_references.length ? (
            <div className="mt-3 space-y-2">
              {reasoning.knowledge_references.map(
                (reference, index) => (
                  <div
                    key={`${reference.document}-${reference.chunk_id}-${index}`}
                    className="rounded-md bg-[var(--panel-muted)] px-3 py-3"
                  >
                    <div className="text-xs font-semibold">
                      {reference.title}
                    </div>

                    <div className="mt-1 text-[10px] text-[var(--muted)]">
                      {reference.document}
                    </div>
                  </div>
                )
              )}
            </div>
          ) : (
            <p className="mt-3 text-xs text-[var(--muted)]">
              No knowledge references were returned.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}



/* ============================================================ */
/* INTERPRETER COMPARISON V2                                    */
/* ============================================================ */

export function InterpreterComparisonPanel({
  interpretation,
}: {
  interpretation?: InterpretationResult;
}) {
  if (!interpretation) {
    return (
      <section className="panel-card p-5">
        <Subheading
          title="Interpreter comparison"
          text="Property-level comparison becomes available after deterministic interpretation."
        />

        <p className="mt-3 text-xs text-[var(--muted)]">
          No interpreter comparison evidence is available yet.
        </p>
      </section>
    );
  }


  const coverage = interpretation.comparison.coverage;
  const properties = interpretation.comparison.properties;

  const names = interpretation.interpreters.map(
    (item) => item.interpreter
  );


  const status =
    coverage.total === 0
      ? 'NOT AVAILABLE'
      : coverage.disagreement_count > 0
        ? 'DISAGREEMENT PRESENT'
        : coverage.not_comparable_count > 0
          ? 'PARTIAL COMPARABILITY'
          : 'COMPARABLE PROPERTIES AGREE';


  const explanation =
    coverage.total === 0
      ? 'No tracked properties were available for property-level comparison.'
      : coverage.disagreement_count > 0
        ? 'At least one tracked property differs between interpreters.'
        : coverage.not_comparable_count > 0
          ? 'Comparable tracked properties agree, but one or more properties were not exposed by every interpreter.'
          : 'All tracked properties exposed by both interpreters agree. This does not imply universal parser agreement.';


  return (
    <section className="panel-card p-5">
      <Subheading
        title="Interpreter comparison"
        text="AGREEMENT, DISAGREEMENT, and NOT_COMPARABLE are deterministic property-level states."
      />


      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Metric
          label="Status"
          value={status}
        />

        <Metric
          label="Compared properties"
          value={String(coverage.total)}
        />

        <Metric
          label="Agreements"
          value={String(coverage.agreement_count)}
        />

        <Metric
          label="Disagreements"
          value={String(coverage.disagreement_count)}
        />

        <Metric
          label="Not comparable"
          value={String(coverage.not_comparable_count)}
        />
      </div>


      <p className="mt-3 text-xs leading-5 text-[var(--muted)]">
        {explanation}
      </p>


      {properties.length ? (
        <div className="mt-4 overflow-x-auto rounded-md border border-[var(--border)]">
          <table className="w-full min-w-[760px] border-collapse text-left text-xs">
            <thead className="bg-[var(--panel-muted)] text-[10px] uppercase tracking-[0.1em] text-[var(--muted)]">
              <tr>
                <th className="px-3 py-3 font-semibold">
                  Property
                </th>

                {names.map((name) => (
                  <th
                    key={name}
                    className="px-3 py-3 font-semibold"
                  >
                    {name}
                  </th>
                ))}

                <th className="px-3 py-3 font-semibold">
                  Comparison
                </th>
              </tr>
            </thead>


            <tbody>
              {properties.map((property) => (
                <tr
                  key={`${property.signal_code}-${property.property_name}`}
                  className="border-t border-[var(--border)]"
                >
                  <td className="px-3 py-3">
                    <div className="font-semibold">
                      {humanize(property.property_name)}
                    </div>

                    <div className="mt-0.5 font-mono text-[9px] text-[var(--muted)]">
                      {property.signal_code}
                    </div>
                  </td>


                  {names.map((name) => (
                    <td
                      key={name}
                      className="px-3 py-3"
                    >
                      {formatObservation(
                        property.values[name]
                      )}
                    </td>
                  ))}


                  <td className="px-3 py-3">
                    <ComparisonBadge
                      status={property.status}
                    />

                    {property.reason ? (
                      <div className="mt-1 text-[9px] text-[var(--muted)]">
                        {humanize(property.reason)}
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-xs text-[var(--muted)]">
          No property-level comparison rows were returned.
        </p>
      )}


      {interpretation.signals.length ? (
        <div className="mt-4">
          <h4 className="text-xs font-semibold">
            Fracture-bearing disagreement signals
          </h4>

          <div className="mt-2 flex flex-wrap gap-2">
            {interpretation.signals.map((signal) => (
              <span
                key={signal.code}
                className="rounded-full border border-[var(--border)] px-2.5 py-1 font-mono text-[10px]"
              >
                {signal.code}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <p className="mt-4 text-xs text-[var(--muted)]">
          No fracture-bearing disagreement signal was emitted.
          This is not a claim that every interpreter property agrees.
        </p>
      )}
    </section>
  );
}



/* ============================================================ */
/* SMALL PRESENTATION HELPERS                                   */
/* ============================================================ */

function Subheading({
  title,
  text,
}: {
  title: string;
  text?: string;
}) {
  return (
    <div>
      <h3 className="text-xs font-semibold">
        {title}
      </h3>

      {text ? (
        <p className="mt-1 text-xs leading-5 text-[var(--muted)]">
          {text}
        </p>
      ) : null}
    </div>
  );
}


function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--panel-muted)] px-3 py-3">
      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--muted)]">
        {label}
      </div>

      <div className="mt-1 break-words text-xs font-semibold">
        {value}
      </div>
    </div>
  );
}


function AuthorityBadge({
  authority,
}: {
  authority:
    | 'DETERMINISTIC'
    | 'MODEL_ADVISORY'
    | 'SYSTEM_ACTION';
}) {
  const label =
    authority === 'MODEL_ADVISORY'
      ? 'MODEL ADVISORY'
      : authority === 'SYSTEM_ACTION'
        ? 'SYSTEM ACTION'
        : 'DETERMINISTIC';

  return (
    <span className="w-fit rounded-full border border-[var(--border)] bg-[var(--panel)] px-2 py-1 text-[9px] font-semibold tracking-[0.08em]">
      {label}
    </span>
  );
}


function ComparisonBadge({
  status,
}: {
  status:
    | 'AGREEMENT'
    | 'DISAGREEMENT'
    | 'NOT_COMPARABLE';
}) {
  return (
    <span className="inline-flex rounded-full border border-[var(--border)] bg-[var(--panel-muted)] px-2 py-1 text-[9px] font-semibold tracking-[0.06em]">
      {status.replace('_', ' ')}
    </span>
  );
}


function EvidenceCode({
  code,
  detail = 'Deterministically verified',
}: {
  code: string;
  detail?: string;
}) {
  return (
    <div className="rounded-md bg-[var(--panel-muted)] px-3 py-3">
      <div className="font-mono text-[10px] font-semibold">
        {code}
      </div>

      <div className="mt-1 text-xs text-[var(--muted)]">
        {detail}
      </div>
    </div>
  );
}


function TextList({
  title,
  items,
  empty,
}: {
  title: string;
  items: string[];
  empty: string;
}) {
  return (
    <div>
      <h4 className="text-xs font-semibold">
        {title}
      </h4>

      {items.length ? (
        <div className="mt-2 space-y-2">
          {items.map((item, index) => (
            <p
              key={`${title}-${index}`}
              className="rounded-md bg-[var(--panel-muted)] px-3 py-2.5 text-xs leading-5"
            >
              {item}
            </p>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-xs text-[var(--muted)]">
          {empty}
        </p>
      )}
    </div>
  );
}


function humanize(value: string) {
  return value
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(
      /\b\w/g,
      (letter) => letter.toUpperCase()
    );
}


function formatObservation(value: unknown) {
  if (value === null || value === undefined) {
    return '?';
  }

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }

  if (Array.isArray(value)) {
    return value.length
      ? value.join(', ')
      : '[]';
  }

  if (typeof value === 'object') {
    return JSON.stringify(value);
  }

  return String(value);
}


function stringField(
  value: Record<string, unknown>,
  key: string
) {
  const candidate = value[key];

  return typeof candidate === 'string'
    ? candidate
    : null;
}
