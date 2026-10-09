import json

from pydantic import BaseModel, ConfigDict, ValidationError

from app.schemas.investigation_agents import (
    EvidenceAgentResult,
    ExperimentAgentResult,
    HypothesisAgentResult,
)
from app.schemas.semantic_reasoning import ProposedExperiment


EXPERIMENT_SYSTEM_PROMPT = """
You are PRISM's Experiment Agent.

Your role is proposal-only.

Given deterministic evidence and advisory hypotheses, propose bounded
experiments that could reduce uncertainty.

You may propose only these typed experiment kinds:
- FORCE_DEEP_INTERPRETATION
- VERIFY_PDF_ACTIONS
- VERIFY_ZIP_ENTRY_PATHS
- UNSUPPORTED

Rules:
- You do not execute experiments.
- You do not authorize experiments.
- The server-side PRISM Lab planner is the execution authority.
- Do not output shell commands, Python code, file operations, or tool calls.
- Do not manufacture BENIGN, SUSPICIOUS, or FRACTURED state.
- Do not claim that an experiment has already been executed.
- Prefer experiments that address an explicit evidence gap or hypothesis.
- Do not propose experiments merely to confirm a model prediction.
- Return only JSON satisfying the supplied schema.
""".strip()


class ExperimentAgentError(RuntimeError):
    pass


class _ExperimentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_experiments: list[ProposedExperiment]


class ExperimentAgentService:
    def __init__(self, rag_service):
        self.rag = rag_service

    def propose(
        self,
        evidence_result: EvidenceAgentResult,
        hypothesis_result: HypothesisAgentResult,
    ) -> ExperimentAgentResult:
        self._validate_inputs(
            evidence_result,
            hypothesis_result,
        )

        if (
            evidence_result.deterministic_verified_state
            in {"FRACTURED", "SUSPICIOUS"}
        ):
            return ExperimentAgentResult(
                artifact_id=evidence_result.artifact_id,
                investigation_round=(
                    evidence_result.investigation_round
                ),
                proposed_experiments=(),
            )

        prompt = self._prompt(
            evidence_result,
            hypothesis_result,
        )

        schema = _ExperimentPayload.model_json_schema()

        proposal_schema = (
            schema.get("$defs", {})
            .get("ProposedExperiment")
        )

        if proposal_schema is None:
            raise ExperimentAgentError(
                "M6 ProposedExperiment schema is unavailable"
            )

        kind_schema = (
            proposal_schema
            .get("properties", {})
            .get("experiment_kind")
        )

        if kind_schema is None:
            raise ExperimentAgentError(
                "M6 experiment_kind schema is unavailable"
            )

        kind_schema.clear()
        kind_schema.update(
            {
                "title": "Experiment Kind",
                "type": "string",
                "enum": [
                    "FORCE_DEEP_INTERPRETATION",
                    "VERIFY_PDF_ACTIONS",
                    "VERIFY_ZIP_ENTRY_PATHS",
                    "UNSUPPORTED",
                ],
            }
        )

        required = proposal_schema.setdefault(
            "required",
            [],
        )

        if "experiment_kind" not in required:
            required.insert(
                0,
                "experiment_kind",
            )

        answer = self.rag.generator.generate(
            EXPERIMENT_SYSTEM_PROMPT,
            prompt,
            format_json=schema,
        )

        try:
            payload = self._parse(answer)
        except ExperimentAgentError as exc:
            repair_prompt = (
                prompt
                + "\n\nSTRUCTURED OUTPUT CORRECTION REQUIRED:\n"
                + f"Validation failure: {exc}\n"
                + "Regenerate the COMPLETE JSON object.\n"
                + "The only top-level field is "
                + "proposed_experiments.\n"
                + "Each proposed experiment must satisfy the "
                + "supplied ProposedExperiment schema.\n"
                + "experiment_kind must be exactly one of:\n"
                + "- FORCE_DEEP_INTERPRETATION\n"
                + "- VERIFY_PDF_ACTIONS\n"
                + "- VERIFY_ZIP_ENTRY_PATHS\n"
                + "- UNSUPPORTED\n"
                + "If no justified experiment exists, return "
                + "an empty proposed_experiments array instead "
                + "of emitting a null experiment_kind.\n"
                + "Do not output commands, code, tool calls, "
                + "verified state, or execution results.\n"
                + "Return only the corrected JSON object."
            )

            repaired = self.rag.generator.generate(
                EXPERIMENT_SYSTEM_PROMPT,
                repair_prompt,
                format_json=schema,
            )

            payload = self._parse(repaired)

        return ExperimentAgentResult(
            artifact_id=evidence_result.artifact_id,
            investigation_round=(
                evidence_result.investigation_round
            ),
            proposed_experiments=tuple(
                payload.proposed_experiments
            ),
        )

    @staticmethod
    def _validate_inputs(
        evidence_result: EvidenceAgentResult,
        hypothesis_result: HypothesisAgentResult,
    ) -> None:
        if (
            evidence_result.artifact_id
            != hypothesis_result.artifact_id
        ):
            raise ExperimentAgentError(
                "Evidence and hypothesis artifact IDs do not agree"
            )

        if (
            evidence_result.investigation_round
            != hypothesis_result.investigation_round
        ):
            raise ExperimentAgentError(
                "Evidence and hypothesis investigation rounds do not agree"
            )

        if (
            evidence_result.evidence.verified_state
            != evidence_result.deterministic_verified_state
        ):
            raise ExperimentAgentError(
                "Evidence verified state does not match Evidence Agent authority field"
            )

    @staticmethod
    def _prompt(
        evidence_result: EvidenceAgentResult,
        hypothesis_result: HypothesisAgentResult,
    ) -> str:
        evidence = evidence_result.evidence

        completed_experiments = []

        if evidence.investigation is not None:
            completed_experiments = [
                {
                    "experiment_kind": (
                        item.result.experiment_kind.value
                    ),
                    "status": item.result.status,
                    "deterministic": (
                        item.result.deterministic
                    ),
                    "verified_state": (
                        item.result.verified_state
                    ),
                    "reason_codes": (
                        item.result.reason_codes[:20]
                    ),
                    "observations": (
                        item.result.observations
                    ),
                }
                for item in (
                    evidence.investigation
                    .completed_experiments[-10:]
                )
            ]

        payload = {
            "artifact_id": str(
                evidence_result.artifact_id
            ),
            "investigation_round": (
                evidence_result.investigation_round
            ),
            "deterministic_verified_state": (
                evidence_result.deterministic_verified_state
            ),
            "evidence_gaps": list(
                evidence_result.evidence_gaps
            ),
            "contradictions": list(
                evidence_result.contradictions
            ),
            "observed_identity": (
                evidence.observed.get(
                    "byte_observed_identity"
                )
            ),
            "claimed_extension": (
                evidence.observed.get(
                    "claimed_extension"
                )
            ),
            "routing_decision": (
                evidence.routing_decision
            ),
            "completed_experiments": (
                completed_experiments
            ),
            "hypotheses": [
                item.model_dump(mode="json")
                for item in hypothesis_result.hypotheses
            ],
            "uncertainties": list(
                hypothesis_result.uncertainties
            ),
        }

        return (
            "PRISM INVESTIGATION CONTEXT:\n"
            + json.dumps(
                payload,
                sort_keys=True,
                default=str,
            )
            + "\n\nPropose only typed experiments that "
            + "could reduce the remaining uncertainty. "
            + "Every emitted proposal MUST have a non-null "
            + "experiment_kind. If no experiment is justified, "
            + "return an empty proposed_experiments array. "
            + "When DEEP_INTERPRETATION_NOT_PERFORMED is an "
            + "evidence gap and no terminal deterministic state "
            + "exists, FORCE_DEEP_INTERPRETATION is the typed "
            + "experiment vocabulary for resolving that gap. "
            + "The server-side planner will independently "
            + "decide whether any proposal is executable."
        )

    @staticmethod
    def _parse(
        raw_answer: str,
    ) -> _ExperimentPayload:
        candidate = raw_answer.strip()

        if candidate.startswith("```json"):
            lines = candidate.splitlines()

            if (
                not lines
                or lines[0].strip() != "```json"
            ):
                raise ExperimentAgentError(
                    "Unsupported structured-output wrapper"
                )

            closing_index = next(
                (
                    index
                    for index, line in enumerate(
                        lines[1:],
                        start=1,
                    )
                    if line.strip() == "```"
                ),
                None,
            )

            if closing_index is None:
                raise ExperimentAgentError(
                    "Unterminated JSON code fence"
                )

            candidate = "\n".join(
                lines[1:closing_index]
            ).strip()

        elif candidate.startswith("```"):
            raise ExperimentAgentError(
                "Unsupported structured-output fence"
            )

        try:
            decoded = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ExperimentAgentError(
                "Experiment Agent returned invalid JSON "
                f"(line={exc.lineno}, column={exc.colno})"
            ) from exc

        if not isinstance(decoded, dict):
            raise ExperimentAgentError(
                "Experiment Agent output must be a JSON object"
            )

        try:
            payload = _ExperimentPayload.model_validate(
                decoded
            )

            for index, proposal in enumerate(
                payload.proposed_experiments
            ):
                if proposal.experiment_kind is None:
                    raise ExperimentAgentError(
                        "Experiment Agent emitted proposal "
                        f"{index} with null experiment_kind; "
                        "use an empty proposal list when no "
                        "typed experiment is justified"
                    )

            return payload
        except ValidationError as exc:
            failures = [
                {
                    "location": ".".join(
                        str(part)
                        for part in item["loc"]
                    ),
                    "type": item["type"],
                }
                for item in exc.errors(
                    include_url=False,
                    include_input=False,
                    include_context=False,
                )
            ]

            raise ExperimentAgentError(
                "Experiment Agent schema validation failed: "
                f"{failures}"
            ) from exc
