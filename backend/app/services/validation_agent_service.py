import json
import re

from pydantic import BaseModel, ConfigDict, ValidationError

from app.schemas.investigation_agents import (
    EvidenceAgentResult,
    HypothesisAgentResult,
    ValidationAgentResult,
    ValidationAssessment,
)
from app.schemas.prism_lab import PrismLabExperimentResult


VALIDATION_SYSTEM_PROMPT = """
You are PRISM's Validation Agent.

Your role is advisory only.

Compare the pre-experiment hypotheses against the actual deterministic
PRISM Lab experiment result.

Return one overall assessment:
- CONSISTENT: the deterministic observations support the hypothesis.
- INCONSISTENT: the deterministic observations conflict with it.
- INCONCLUSIVE: the experiment does not discriminate sufficiently.

Rules:
- The experiment result is empirical evidence.
- Do not modify or reinterpret its deterministic fields.
- Do not manufacture BENIGN, SUSPICIOUS, or FRACTURED state.
- Do not claim the artifact is safe or benign.
- Do not propose or execute another experiment.
- Do not output commands, code, or tool calls.
- Validation is advisory; Investigation State remains authoritative.
- Return only JSON satisfying the supplied schema.
""".strip()


class ValidationAgentError(RuntimeError):
    pass


class _ValidationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment: str
    rationale: str


class ValidationAgentService:
    def __init__(self, rag_service):
        self.rag = rag_service

    def validate(
        self,
        post_evidence: EvidenceAgentResult,
        hypothesis_result: HypothesisAgentResult,
        experiment_result: PrismLabExperimentResult,
    ) -> ValidationAgentResult:
        self._validate_inputs(
            post_evidence,
            hypothesis_result,
            experiment_result,
        )

        # There is nothing to semantically compare if the previous
        # Hypothesis Agent produced no hypotheses.
        if not hypothesis_result.hypotheses:
            return ValidationAgentResult(
                artifact_id=post_evidence.artifact_id,
                investigation_round=(
                    post_evidence.investigation_round
                ),
                experiment_result=experiment_result,
                assessment=ValidationAssessment(
                    experiment_kind=(
                        experiment_result.experiment_kind
                    ),
                    assessment="INCONCLUSIVE",
                    rationale=(
                        "No advisory hypothesis was supplied "
                        "for comparison with the deterministic "
                        "experiment result."
                    ),
                ),
                deterministic_verified_state=(
                    post_evidence.deterministic_verified_state
                ),
            )

        prompt = self._prompt(
            post_evidence,
            hypothesis_result,
            experiment_result,
        )

        schema = self._schema()

        answer = self.rag.generator.generate(
            VALIDATION_SYSTEM_PROMPT,
            prompt,
            format_json=schema,
        )

        try:
            payload = self._parse(answer)

        except ValidationAgentError as exc:
            repair_prompt = (
                prompt
                + "\n\nSTRUCTURED OUTPUT CORRECTION REQUIRED:\n"
                + f"Validation failure: {exc}\n"
                + "Regenerate the COMPLETE JSON object.\n"
                + "The only fields are:\n"
                + "- assessment: CONSISTENT, INCONSISTENT, "
                + "or INCONCLUSIVE\n"
                + "- rationale: string\n"
                + "Do not include experiment_kind, verified_state, "
                + "commands, experiments, or execution results.\n"
                + "Return only the corrected JSON object."
            )

            repaired = self.rag.generator.generate(
                VALIDATION_SYSTEM_PROMPT,
                repair_prompt,
                format_json=schema,
            )

            payload = self._parse(repaired)

        violation = self._epistemic_violation(payload)

        if violation is not None:
            repair_prompt = (
                prompt
                + "\n\nEPISTEMIC CORRECTION REQUIRED:\n"
                + "The previous validation exceeded the advisory "
                + "authority boundary.\n"
                + f"Violation: {violation}\n"
                + "Describe only whether the deterministic experiment "
                + "observations are consistent, inconsistent, or "
                + "inconclusive relative to the supplied hypotheses.\n"
                + "Do not declare the artifact benign, safe, "
                + "suspicious, or fractured.\n"
                + "Do not declare PRISM verified state.\n"
                + "Return only the required JSON object."
            )

            repaired = self.rag.generator.generate(
                VALIDATION_SYSTEM_PROMPT,
                repair_prompt,
                format_json=schema,
            )

            payload = self._parse(repaired)

            if self._epistemic_violation(payload) is not None:
                raise ValidationAgentError(
                    "Validation Agent exceeded advisory "
                    "authority after bounded repair"
                )

        return ValidationAgentResult(
            artifact_id=post_evidence.artifact_id,
            investigation_round=(
                post_evidence.investigation_round
            ),
            experiment_result=experiment_result,
            assessment=ValidationAssessment(
                experiment_kind=(
                    experiment_result.experiment_kind
                ),
                assessment=payload.assessment,
                rationale=payload.rationale,
            ),
            deterministic_verified_state=(
                post_evidence.deterministic_verified_state
            ),
        )

    @staticmethod
    def _validate_inputs(
        post_evidence: EvidenceAgentResult,
        hypothesis_result: HypothesisAgentResult,
        experiment_result: PrismLabExperimentResult,
    ) -> None:
        if (
            post_evidence.artifact_id
            != hypothesis_result.artifact_id
            or post_evidence.artifact_id
            != experiment_result.artifact_id
        ):
            raise ValidationAgentError(
                "Validation artifact IDs do not agree"
            )

        # One successful deterministic experiment increments the
        # accumulated investigation round exactly once.
        if (
            post_evidence.investigation_round
            != hypothesis_result.investigation_round + 1
        ):
            raise ValidationAgentError(
                "Post-experiment investigation round does not "
                "follow the hypothesis round"
            )

        if (
            post_evidence.evidence.verified_state
            != post_evidence.deterministic_verified_state
        ):
            raise ValidationAgentError(
                "Post-experiment verified state does not match "
                "Evidence Agent authority field"
            )

        investigation = post_evidence.evidence.investigation

        if investigation is None:
            raise ValidationAgentError(
                "Post-experiment Investigation State is missing"
            )

        if (
            investigation.investigation_round
            != post_evidence.investigation_round
        ):
            raise ValidationAgentError(
                "Evidence Agent round does not match "
                "Investigation State"
            )

        if (
            investigation.verified_state
            != post_evidence.deterministic_verified_state
        ):
            raise ValidationAgentError(
                "Evidence Agent verified state does not match "
                "Investigation State"
            )

        latest = investigation.latest_lab_result

        if latest is None:
            raise ValidationAgentError(
                "Latest deterministic Lab result is missing"
            )

        if (
            latest.experiment_id
            != experiment_result.experiment_id
        ):
            raise ValidationAgentError(
                "Validation experiment is not the latest "
                "recorded deterministic Lab result"
            )

        if (
            latest.experiment_kind
            != experiment_result.experiment_kind
        ):
            raise ValidationAgentError(
                "Recorded Lab experiment kind does not match "
                "validation input"
            )

    @staticmethod
    def _schema() -> dict:
        # Build a narrow schema manually so the LLM has no surface
        # for experiment_kind or verified state.
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "assessment": {
                    "type": "string",
                    "enum": [
                        "CONSISTENT",
                        "INCONSISTENT",
                        "INCONCLUSIVE",
                    ],
                },
                "rationale": {
                    "type": "string",
                },
            },
            "required": [
                "assessment",
                "rationale",
            ],
        }

    @staticmethod
    def _prompt(
        post_evidence,
        hypothesis_result,
        experiment_result,
    ) -> str:
        payload = {
            "artifact_id": str(
                post_evidence.artifact_id
            ),
            "pre_experiment_hypothesis_round": (
                hypothesis_result.investigation_round
            ),
            "post_experiment_investigation_round": (
                post_evidence.investigation_round
            ),
            "hypotheses": [
                item.model_dump(mode="json")
                for item in hypothesis_result.hypotheses
            ],
            "uncertainties": list(
                hypothesis_result.uncertainties
            ),
            "experiment": {
                "experiment_id": str(
                    experiment_result.experiment_id
                ),
                "experiment_kind": (
                    experiment_result.experiment_kind.value
                ),
                "deterministic": (
                    experiment_result.deterministic
                ),
                "deep_scan_performed": (
                    experiment_result.deep_scan_performed
                ),
                "ambiguity_observed": (
                    experiment_result.ambiguity_observed
                ),
                "suspicious_verified": (
                    experiment_result.suspicious_verified
                ),
                "fracture_detected": (
                    experiment_result.fracture_detected
                ),
                "reason_codes": (
                    experiment_result.reason_codes[:20]
                ),
                "observations": (
                    experiment_result.observations
                ),
            },
        }

        return (
            "PRISM VALIDATION CONTEXT:\n"
            + json.dumps(
                payload,
                sort_keys=True,
                default=str,
            )
            + "\n\nAssess only whether the deterministic "
            + "experiment evidence is consistent with, "
            + "inconsistent with, or inconclusive relative "
            + "to the advisory hypotheses."
        )

    @staticmethod
    def _parse(
        raw_answer: str,
    ) -> _ValidationPayload:
        candidate = raw_answer.strip()

        if candidate.startswith("```json"):
            lines = candidate.splitlines()

            closing_index = next(
                (
                    index
                    for index, line
                    in enumerate(lines[1:], start=1)
                    if line.strip() == "```"
                ),
                None,
            )

            if closing_index is None:
                raise ValidationAgentError(
                    "Unterminated JSON code fence"
                )

            candidate = "\n".join(
                lines[1:closing_index]
            ).strip()

        elif candidate.startswith("```"):
            raise ValidationAgentError(
                "Unsupported structured-output fence"
            )

        try:
            decoded = json.loads(candidate)

        except json.JSONDecodeError as exc:
            raise ValidationAgentError(
                "Validation Agent returned invalid JSON"
            ) from exc

        if not isinstance(decoded, dict):
            raise ValidationAgentError(
                "Validation Agent output must be a JSON object"
            )

        allowed = {
            "assessment",
            "rationale",
        }

        if set(decoded) != allowed:
            raise ValidationAgentError(
                "Validation Agent returned unsupported fields"
            )

        try:
            payload = _ValidationPayload.model_validate(
                decoded
            )

        except ValidationError as exc:
            raise ValidationAgentError(
                "Validation Agent schema validation failed"
            ) from exc

        if payload.assessment not in {
            "CONSISTENT",
            "INCONSISTENT",
            "INCONCLUSIVE",
        }:
            raise ValidationAgentError(
                "Validation Agent returned unsupported assessment"
            )

        return payload

    @staticmethod
    def _epistemic_violation(
        payload: _ValidationPayload,
    ) -> str | None:
        generated = payload.rationale.lower()

        unsupported = (
            r"\b(?:artifact|file|document|pdf|zip|png)\s+"
            r"(?:is|appears(?:\s+to\s+be)?|"
            r"seems(?:\s+to\s+be)?)\s+"
            r"(?:benign|safe|suspicious|fractured)\b",

            r"\bprism(?:'s)?\s+(?:verified\s+)?"
            r"state\s+is\s+"
            r"(?:benign|suspicious|fractured)\b",
        )

        for pattern in unsupported:
            if re.search(pattern, generated):
                return pattern

        return None
