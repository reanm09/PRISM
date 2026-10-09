import json
import re

from pydantic import BaseModel, ConfigDict, ValidationError

from app.schemas.investigation_agents import (
    EvidenceAgentResult,
    HypothesisAgentResult,
)
from app.schemas.semantic_reasoning import SemanticHypothesis
from app.services.semantic_reasoning_service import (
    SemanticReasoningService,
)


HYPOTHESIS_SYSTEM_PROMPT = """
You are PRISM's Hypothesis Agent.

Your role is advisory only.

Generate grounded hypotheses that may explain the supplied artifact
evidence and identify remaining uncertainty.

Rules:
- Deterministic PRISM evidence is authoritative.
- Model predictions are non-authoritative.
- Do not declare BENIGN, SUSPICIOUS, or FRACTURED state.
- Do not claim an unverified absence of Semantic Fracture.
- Do not claim an unverified absence of security-relevant capability.
- Do not claim interpreters agree unless deterministic evidence says so.
- Do not propose, select, authorize, or execute experiments.
- Do not output commands or executable actions.
- A hypothesis is an explanation to test, not a verified finding.
- Return only JSON satisfying the supplied schema.
""".strip()


class HypothesisAgentError(RuntimeError):
    pass


class _HypothesisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning_summary: str
    hypotheses: list[SemanticHypothesis]
    uncertainties: list[str]


class HypothesisAgentService:
    def __init__(self, rag_service):
        self.rag = rag_service

    def generate(
        self,
        evidence_result: EvidenceAgentResult,
        *,
        top_k: int = 5,
    ) -> HypothesisAgentResult:
        evidence = evidence_result.evidence

        if evidence.artifact_id != evidence_result.artifact_id:
            raise HypothesisAgentError(
                "Evidence Agent artifact ID does not match evidence bundle"
            )

        if (
            evidence.verified_state
            != evidence_result.deterministic_verified_state
        ):
            raise HypothesisAgentError(
                "Evidence Agent verified state does not match evidence bundle"
            )

        query = SemanticReasoningService.retrieval_query(
            evidence
        )

        sources = self.rag.retrieve(
            query,
            top_k=top_k,
        )

        if not sources:
            return HypothesisAgentResult(
                artifact_id=evidence_result.artifact_id,
                investigation_round=(
                    evidence_result.investigation_round
                ),
                hypotheses=(),
                uncertainties=(
                    "Retrieved PRISM knowledge is insufficient "
                    "for grounded hypothesis generation.",
                ),
                reasoning_summary=(
                    "No relevant indexed PRISM knowledge was "
                    "retrieved; hypothesis generation is limited."
                ),
                sources=(),
            )

        prompt = self._prompt(
            evidence_result,
            sources,
        )

        schema = _HypothesisPayload.model_json_schema()

        answer = self.rag.generator.generate(
            HYPOTHESIS_SYSTEM_PROMPT,
            prompt,
            format_json=schema,
        )

        try:
            payload = self._parse(answer)

        except HypothesisAgentError as exc:
            repair_prompt = (
                prompt
                + "\n\nSTRUCTURED OUTPUT CORRECTION REQUIRED:\n"
                + f"Validation failure: {exc}\n"
                + "Regenerate the COMPLETE JSON object.\n"
                + "Required top-level fields are exactly:\n"
                + "- reasoning_summary: string\n"
                + "- hypotheses: array\n"
                + "- uncertainties: array of strings\n"
                + "Each hypothesis must contain exactly the "
                + "SemanticHypothesis fields required by the schema.\n"
                + "Do NOT include recommended_experiments, "
                + "experiment_kind, commands, or actions.\n"
                + "Return only the corrected JSON object."
            )

            repaired = self.rag.generator.generate(
                HYPOTHESIS_SYSTEM_PROMPT,
                repair_prompt,
                format_json=schema,
            )

            # Second structural failure fails closed.
            payload = self._parse(repaired)

        violation = self._epistemic_violation(
            payload,
            evidence_result,
        )

        if violation is not None:
            repair_prompt = (
                prompt
                + "\n\nEPISTEMIC CORRECTION REQUIRED:\n"
                + "The previous candidate exceeded PRISM's "
                + "deterministic evidence boundary.\n"
                + f"Violation: {violation}\n"
                + "Regenerate once.\n"
                + "Treat hypotheses as unverified explanations.\n"
                + "Do not describe the artifact as benign or safe.\n"
                + "Do not claim absence of Semantic Fracture, "
                + "security-relevant capability, malicious activity, "
                + "or interpreter disagreement unless deterministic "
                + "evidence explicitly established that fact.\n"
                + "Retrieved knowledge is background only and "
                + "must not be converted into an artifact-specific "
                + "positive capability claim. Specific JavaScript, "
                + "Launch, RichMedia, path-traversal, or absolute-"
                + "path claims require a corresponding positive "
                + "artifact evidence signal.\n"
                + "Do not manufacture PRISM verified state.\n"
                + "Do not propose experiments.\n"
                + "Return only the required JSON object."
            )

            repaired = self.rag.generator.generate(
                HYPOTHESIS_SYSTEM_PROMPT,
                repair_prompt,
                format_json=schema,
            )

            payload = self._parse(repaired)

            second_violation = self._epistemic_violation(
                payload,
                evidence_result,
            )

            if second_violation is not None:
                raise HypothesisAgentError(
                    "Hypothesis Agent exceeded deterministic "
                    "evidence after bounded repair"
                )

        return HypothesisAgentResult(
            artifact_id=evidence_result.artifact_id,
            investigation_round=(
                evidence_result.investigation_round
            ),
            hypotheses=tuple(payload.hypotheses),
            uncertainties=tuple(payload.uncertainties),
            reasoning_summary=payload.reasoning_summary,
            sources=tuple(sources),
        )

    @staticmethod
    def _prompt(
        evidence_result,
        sources,
    ) -> str:
        evidence = evidence_result.evidence

        excerpts = [
            {
                "chunk_id": source.chunk_id,
                "source": source.source,
                "title": source.title,
                "text": source.text[:800],
            }
            for source in sources
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
            "contradictions": list(
                evidence_result.contradictions
            ),
            "evidence_gaps": list(
                evidence_result.evidence_gaps
            ),
            "observed": evidence.observed,
            "model_prediction": evidence.model_prediction,
            "verified_findings": (
                evidence.verified_findings
            ),
            "routing_decision": evidence.routing_decision,
        }

        return (
            "PRISM EVIDENCE AGENT OUTPUT:\n"
            + json.dumps(
                payload,
                sort_keys=True,
                default=str,
            )
            + "\n\nRETRIEVED KNOWLEDGE:\n"
            + json.dumps(
                excerpts,
                sort_keys=True,
                default=str,
            )
            + "\n\nGenerate grounded hypotheses only. "
            + "Retrieved knowledge is background knowledge, "
            + "NOT evidence that a capability exists in this "
            + "specific artifact. Do not assert that this "
            + "artifact contains JavaScript, launch actions, "
            + "RichMedia, path traversal entries, absolute "
            + "paths, or another specific capability unless "
            + "the PRISM Evidence Agent output contains a "
            + "corresponding positive artifact signal. "
            + "Without such a signal, describe only the "
            + "remaining generic uncertainty. "
            + "Do not propose experiments."
        )

    @staticmethod
    def _parse(
        raw_answer: str,
    ) -> _HypothesisPayload:
        candidate = raw_answer.strip()

        if candidate.startswith("```json"):
            lines = candidate.splitlines()

            if (
                not lines
                or lines[0].strip() != "```json"
            ):
                raise HypothesisAgentError(
                    "Unsupported structured-output wrapper"
                )

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
                raise HypothesisAgentError(
                    "Unterminated JSON code fence"
                )

            candidate = "\n".join(
                lines[1:closing_index]
            ).strip()

        elif candidate.startswith("```"):
            raise HypothesisAgentError(
                "Unsupported structured-output fence"
            )

        try:
            decoded = json.loads(candidate)

        except json.JSONDecodeError as exc:
            raise HypothesisAgentError(
                "Hypothesis Agent returned invalid JSON "
                f"(line={exc.lineno}, "
                f"column={exc.colno})"
            ) from exc

        if not isinstance(decoded, dict):
            raise HypothesisAgentError(
                "Hypothesis Agent output must be a JSON object"
            )

        try:
            return _HypothesisPayload.model_validate(
                decoded
            )

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

            raise HypothesisAgentError(
                "Hypothesis Agent schema validation "
                f"failed: {failures}"
            ) from exc

    @staticmethod
    def _epistemic_violation(
        payload: _HypothesisPayload,
        evidence_result: EvidenceAgentResult,
    ) -> str | None:
        generated = json.dumps(
            {
                "reasoning_summary": (
                    payload.reasoning_summary
                ),
                "hypotheses": [
                    item.model_dump()
                    for item in payload.hypotheses
                ],
            },
            ensure_ascii=False,
        ).lower()

        # The model may refer to a model prediction named BENIGN,
        # but it may not convert that into an artifact conclusion.
        unsupported = (
            r"\b(?:artifact|file|document|pdf|zip|png)\s+"
            r"(?:is|appears(?:\s+to\s+be)?|"
            r"seems(?:\s+to\s+be)?|looks)\s+"
            r"(?:likely\s+|probably\s+|apparently\s+)?"
            r"(?:benign|safe)\b",

            r"\b(?:likely|probably|apparently|seemingly)\s+"
            r"(?:benign|safe)\b",

            r"\b(?:no|not|without)\s+(?:a\s+)?"
            r"(?:semantic\s+)?fractures?\b",

            r"\b(?:lack|absence)\s+of\s+(?:a\s+)?"
            r"(?:semantic\s+)?fractures?\b",

            r"\binterpreters?\s+"
            r"(?:agree|agreed|are\s+in\s+agreement)\b",

            r"\b(?:no|without)\s+(?:verified\s+)?"
            r"(?:suspicious|malicious|security[- ]relevant)\s+"
            r"(?:capabilit(?:y|ies)|activity|behavior|behaviour)\b",

            r"\bprism(?:'s)?\s+(?:verified\s+)?"
            r"state\s+is\s+"
            r"(?:benign|fractured|suspicious)\b",
        )

        for pattern in unsupported:
            if re.search(pattern, generated):
                return pattern

        # Retrieved RAG knowledge is contextual knowledge, not
        # evidence that a capability exists in this artifact.
        #
        # Reject artifact-specific positive capability claims unless
        # the deterministic evidence bundle contains a corresponding
        # positive precursor or verified finding.
        def has_positive_signal(
            keys,
            reason_codes,
        ):
            def walk(value):
                if hasattr(value, "model_dump"):
                    value = value.model_dump(
                        mode="json"
                    )

                if isinstance(value, dict):
                    for key, child in value.items():
                        if key in keys:
                            if isinstance(child, bool):
                                if child:
                                    return True

                            elif isinstance(
                                child,
                                (int, float),
                            ):
                                if child > 0:
                                    return True

                            elif isinstance(child, str):
                                normalized = (
                                    child.strip().lower()
                                )

                                if normalized not in {
                                    "",
                                    "0",
                                    "false",
                                    "none",
                                    "null",
                                }:
                                    return True

                        if walk(child):
                            return True

                elif isinstance(
                    value,
                    (list, tuple, set),
                ):
                    return any(
                        walk(item)
                        for item in value
                    )

                return False

            if walk(
                evidence_result.evidence.observed
            ):
                return True

            verified_text = json.dumps(
                evidence_result
                .evidence
                .verified_findings,
                sort_keys=True,
                default=str,
            ).upper()

            return any(
                code in verified_text
                for code in reason_codes
            )

        capability_rules = (
            (
                "javascript",
                (
                    r"\b(?:artifact|file|document|pdf)\b"
                    r".{0,120}\b"
                    r"(?:contain(?:s)?|has|have|include(?:s)?|"
                    r"embed(?:s)?|carry|carries)\b"
                    r".{0,120}\b"
                    r"(?:javascript|java\s*script|js\s+action)\b",
                ),
                {
                    "javascript_action_candidate_count",
                },
                {
                    "PDF_JAVASCRIPT_ACTION",
                },
            ),
            (
                "launch action",
                (
                    r"\b(?:artifact|file|document|pdf)\b"
                    r".{0,120}\b"
                    r"(?:contain(?:s)?|has|have|include(?:s)?|"
                    r"embed(?:s)?|carry|carries)\b"
                    r".{0,120}\b"
                    r"launch\s+action\b",
                ),
                {
                    "launch_action_candidate_count",
                },
                {
                    "PDF_LAUNCH_ACTION",
                },
            ),
            (
                "richmedia",
                (
                    r"\b(?:artifact|file|document|pdf)\b"
                    r".{0,120}\b"
                    r"(?:contain(?:s)?|has|have|include(?:s)?|"
                    r"embed(?:s)?|carry|carries)\b"
                    r".{0,120}\b"
                    r"rich\s*media\b",
                ),
                {
                    "richmedia_annotation_candidate_count",
                },
                {
                    "PDF_RICHMEDIA_CONTENT",
                },
            ),
            (
                "path traversal",
                (
                    r"\b(?:artifact|file|zip)\b"
                    r".{0,120}\b"
                    r"(?:contain(?:s)?|has|have|include(?:s)?|"
                    r"carry|carries)\b"
                    r".{0,120}\b"
                    r"(?:path\s+traversal|parent\s+traversal)\b",
                ),
                {
                    "parent_traversal_entry_candidate_count",
                },
                {
                    "ZIP_PATH_TRAVERSAL_ENTRY",
                },
            ),
            (
                "absolute path",
                (
                    r"\b(?:artifact|file|zip)\b"
                    r".{0,120}\b"
                    r"(?:contain(?:s)?|has|have|include(?:s)?|"
                    r"carry|carries)\b"
                    r".{0,120}\b"
                    r"absolute\s+path\b",
                ),
                {
                    "absolute_path_entry_candidate_count",
                },
                {
                    "ZIP_ABSOLUTE_PATH_ENTRY",
                },
            ),
        )

        for (
            capability,
            patterns,
            evidence_keys,
            reason_codes,
        ) in capability_rules:
            claimed = any(
                re.search(
                    pattern,
                    generated,
                    flags=re.DOTALL,
                )
                for pattern in patterns
            )

            if (
                claimed
                and not has_positive_signal(
                    evidence_keys,
                    reason_codes,
                )
            ):
                return (
                    "unsupported artifact-specific "
                    f"{capability} capability claim "
                    "without deterministic evidence signal"
                )

        # Even if the current deterministic state is terminal, the
        # Hypothesis Agent does not get to restate itself as authority.
        # The authoritative value remains separately typed on the
        # Evidence Agent result.
        return None
