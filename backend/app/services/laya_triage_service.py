from __future__ import annotations

import json
import os
import threading
from uuid import UUID

from app.core.config import settings
from app.schemas.artifact import ArtifactMetadata
from app.schemas.fastscan import FastScanResult
from app.schemas.laya_triage import LayaModelInput, LayaTriageResult


# IMPORTANT:
# Keep this exact option order.
#
# It is the canonical option order used for the frozen
# PRISM-Laya Exp2 V3 validation/test inference.
ARTIFACT_STATE_QUESTION = {
    "artifact_state": {
        "type": "choice",
        "instructions": "What is the artifact state?",
        "criteria": {
            "AMBIGUOUS":
                "FastScan evidence indicates ambiguity requiring deeper interpretation.",

            "BENIGN":
                "No verified ambiguity, fracture, or security-relevant capability.",

            "FRACTURED":
                "Verified Semantic Fracture: interpreters disagree about the artifact.",

            "SUSPICIOUS":
                "Verified security-relevant capability or structural hazard without a verified Semantic Fracture.",
        },
    }
}


# This is routing policy, NOT ground truth.
#
# A predicted FRACTURED or SUSPICIOUS artifact must still
# pass through deterministic PRISM evidence generation.
ROUTE_BY_STATE = {
    "BENIGN": "PASS",
    "AMBIGUOUS": "DEEP_SCAN",
    "SUSPICIOUS": "PRISM_LAB",
    "FRACTURED": "PRISM_LAB",
}


class LayaTriageError(RuntimeError):
    pass


class LayaTriageService:

    def __init__(self) -> None:
        self._agent = None
        self._load_lock = threading.Lock()
        self._results: dict[UUID, LayaTriageResult] = {}


    def get(
        self,
        artifact_id: UUID,
    ) -> LayaTriageResult | None:

        return self._results.get(
            artifact_id
        )


    def _load_agent(self):

        if self._agent is not None:
            return self._agent

        with self._load_lock:

            if self._agent is not None:
                return self._agent

            model_path = (
                settings.laya_model_path
            )

            if not model_path.is_dir():
                raise LayaTriageError(
                    "Laya checkpoint directory not found: "
                    f"{model_path}"
                )

            # Keep local serving numerics aligned with
            # the frozen Exp2 evaluation environment.
            os.environ[
                "LAYA_CUDA_AMP"
            ] = settings.laya_cuda_amp

            try:
                import laya
            except ImportError as exc:
                raise LayaTriageError(
                    "Laya runtime is not installed "
                    "in the backend environment"
                ) from exc

            device = (
                None
                if settings.laya_device.lower()
                == "auto"
                else settings.laya_device
            )

            try:
                self._agent = laya.load(
                    str(model_path),

                    device=device,

                    expected_sha256={
                        "model.safetensors":
                            settings.laya_model_sha256,
                    },
                )

            except Exception as exc:
                raise LayaTriageError(
                    "Unable to load frozen Laya "
                    f"checkpoint: {exc}"
                ) from exc

        return self._agent


    @staticmethod
    def build_model_input(
        artifact: ArtifactMetadata,
        fastscan: FastScanResult,
    ) -> LayaModelInput:

        # Never let model inference mix evidence from
        # different artifact bytes.
        if (
            artifact.artifact_id
            != fastscan.artifact_id
            or artifact.sha256
            != fastscan.sha256
        ):
            raise LayaTriageError(
                "Artifact and FastScan evidence "
                "do not describe the same bytes"
            )

        if not (
            fastscan.integrity
            .sha256_matches_ingestion
        ):
            raise LayaTriageError(
                "FastScan byte-integrity "
                "verification failed"
            )

        if (
            fastscan.size_bytes
            != artifact.size_bytes
        ):
            raise LayaTriageError(
                "FastScan size does not match "
                "ingested artifact"
            )

        if (
            fastscan.structural_features
            is None
        ):
            raise LayaTriageError(
                "FastScan structural features "
                "are unavailable"
            )

        # EXACT frozen v4 / FASTSCAN_PRE_TRIAGE
        # nine-field contract.
        return LayaModelInput(
            claimed_extension=
                artifact.claimed_extension,

            observed_identity=
                fastscan.observed.detected_type,

            mime=
                fastscan.observed.detected_mime,

            size_bytes=
                fastscan.size_bytes,

            entropy=
                fastscan.statistics.entropy,

            extension_consistent=
                fastscan.consistency
                .extension_matches_observed,

            fastscan_signals=[
                item.code
                for item
                in fastscan.signals
            ],

            structural_features=
                fastscan.structural_features,

            pretriage_security_features=
                fastscan
                .pretriage_security_features,
        )


    def predict(
        self,
        artifact: ArtifactMetadata,
        fastscan: FastScanResult,
    ) -> LayaTriageResult:

        model_input = (
            self.build_model_input(
                artifact,
                fastscan,
            )
        )

        # EXACT deterministic serialization used by
        # PRISM-Laya Exp2 train/validation/test.
        state = json.dumps(
            model_input.model_dump(
                mode="json"
            ),
            sort_keys=True,
            separators=(",", ":"),
        )

        agent = self._load_agent()

        try:
            raw = agent.predict(
                state,
                ARTIFACT_STATE_QUESTION,
                max_len=512,
                head_max_len=192,
            )

        except Exception as exc:
            raise LayaTriageError(
                f"Laya inference failed: {exc}"
            ) from exc


        answer = raw[
            "answers"
        ][
            "artifact_state"
        ]

        predicted_state = (
            answer["choice"]
        )

        probabilities = {
            key: float(value)
            for key, value
            in answer[
                "probabilities"
            ].items()
        }


        expected_states = set(
            ROUTE_BY_STATE
        )

        if (
            set(probabilities)
            != expected_states
            or predicted_state
            not in expected_states
        ):
            raise LayaTriageError(
                "Laya returned an unexpected "
                "artifact-state schema"
            )


        result = LayaTriageResult(
            artifact_id=
                artifact.artifact_id,

            sha256=
                artifact.sha256,

            predicted_state=
                predicted_state,

            # Calibrated probability of the
            # reported answer.
            answer_confidence=float(
                answer[
                    "answer_confidence"
                ]
            ),

            probabilities=
                probabilities,

            recommended_route=
                ROUTE_BY_STATE[
                    predicted_state
                ],

            model_sha256=
                settings.laya_model_sha256,

            model_input=
                model_input,
        )

        self._results[
            artifact.artifact_id
        ] = result

        return result
