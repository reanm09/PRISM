import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from app.schemas.laya_triage import FEATURE_CONTRACT_VERSION, FEATURE_STAGE, LayaTrainingRecord
from app.services.fracture_dataset_service import FractureDatasetService, SAMPLE_ID_PATTERN
from app.services.laya_training_service import LayaTrainingService, validate_model_input


MIN_ELIGIBLE_RECORDS = 100  
MIN_RECORDS_PER_REQUIRED_STATE = 20  
MIN_RECORDS_PER_REQUIRED_STATE_SPLIT = 1
MIN_DISTINCT_ARTIFACT_STATES = 2
REQUIRED_ARTIFACT_STATES = ("BENIGN", "AMBIGUOUS", "SUSPICIOUS", "FRACTURED")
V1_SPLIT_STRATEGY = "LINEAGE_STABLE_80_10_10_V1"
V2_SPLIT_STRATEGY = "LINEAGE_STRATIFIED_80_10_10_V2"
SPLIT_STRATEGY = "LINEAGE_EXACT_INPUT_STRATIFIED_80_10_10_V3"
OUTPUT_FILES = ("all.jsonl", "train.jsonl", "validation.jsonl", "test.jsonl", "rejected.jsonl", "manifest.json")


def _json_line(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _split(split_group_id: str, artifact_sha256: str) -> str:
    canonical = (f"prism-laya-v1:{artifact_sha256.lower()}" if split_group_id == artifact_sha256
                 else f"prism-laya-lineage-v1:{split_group_id}")
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    bucket = int.from_bytes(digest, "big") % 100
    return "train" if bucket < 80 else "validation" if bucket < 90 else "test"


def _tie_score(namespace: str, name: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{namespace}:{name}".encode("utf-8")).digest(), "big")


def _hamilton(total: int, weights: dict[str, int], minimums: dict[str, int],
              maximums: dict[str, int], namespace: str) -> dict[str, int]:
    denominator = sum(weights.values())
    if denominator <= 0 or sum(minimums.values()) > total or sum(maximums.values()) < total:
        raise ValueError("STRATIFIED_QUOTA_INFEASIBLE")
    quotas = {name: max(minimums[name], min(maximums[name], total * weight // denominator))
              for name, weight in weights.items()}
    remainders = {name: (total * weight) % denominator for name, weight in weights.items()}
    while sum(quotas.values()) < total:
        choices = [name for name in weights if quotas[name] < maximums[name]]
        if not choices:
            raise ValueError("STRATIFIED_QUOTA_INFEASIBLE")
        chosen = min(choices, key=lambda name: (-remainders[name], _tie_score(namespace, name), name))
        quotas[chosen] += 1
    while sum(quotas.values()) > total:
        choices = [name for name in weights if quotas[name] > minimums[name]]
        if not choices:
            raise ValueError("STRATIFIED_QUOTA_INFEASIBLE")
        chosen = min(choices, key=lambda name: (remainders[name], _tie_score(namespace, name), name))
        quotas[chosen] -= 1
    return quotas


def _split_v3(
    records: list[LayaTrainingRecord],
) -> tuple[dict[str, str], dict[str, dict[str, int]]]:
    """
    V3 split policy.

    Records are inseparable when they share either:
      1. split_group_id / lineage, or
      2. the exact final Laya-visible model_input.

    The relation is transitive. Connected records are assigned
    to exactly one split.

    Returns:
      assignments: record_id -> split
      quotas: exact record-count quotas by artifact state
    """

    if not records:
        return {}, {}

    # --------------------------------------------------------
    # Disjoint-set / union-find
    # --------------------------------------------------------

    parent = {
        record.record_id: record.record_id
        for record in records
    }

    def find(record_id: str) -> str:
        while parent[record_id] != record_id:
            parent[record_id] = parent[parent[record_id]]
            record_id = parent[record_id]
        return record_id

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)

        if left_root == right_root:
            return

        # Deterministic root.
        if left_root < right_root:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    # --------------------------------------------------------
    # Union by lineage
    # --------------------------------------------------------

    first_by_lineage: dict[str, str] = {}

    for record in records:
        previous = first_by_lineage.setdefault(
            record.split_group_id,
            record.record_id,
        )

        union(previous, record.record_id)

    # --------------------------------------------------------
    # Union by exact final model_input
    # --------------------------------------------------------

    first_by_input: dict[str, str] = {}

    for record in records:
        input_key = _json_line(
            record.model_input.model_dump(mode="json")
        ).rstrip("\n")

        previous = first_by_input.setdefault(
            input_key,
            record.record_id,
        )

        union(previous, record.record_id)

    # Compress roots after all unions.
    for record_id in parent:
        parent[record_id] = find(record_id)

    # --------------------------------------------------------
    # Build connected components
    # --------------------------------------------------------

    components: dict[str, list[LayaTrainingRecord]] = defaultdict(list)

    for record in records:
        components[parent[record.record_id]].append(record)

    by_state: dict[
        str,
        list[tuple[str, list[LayaTrainingRecord]]],
    ] = defaultdict(list)

    for root, members in components.items():
        states = {
            item.targets.artifact_state
            for item in members
        }

        if len(states) != 1:
            raise ValueError(
                f"MIXED_STATE_V3_COMPONENT: {root}"
            )

        state = next(iter(states))

        component_id = min(
            item.record_id
            for item in members
        )

        by_state[state].append(
            (component_id, members)
        )

    # --------------------------------------------------------
    # Exact 80/10/10 record quotas per state
    # --------------------------------------------------------

    quotas: dict[str, dict[str, int]] = {}

    for state in REQUIRED_ARTIFACT_STATES:
        total = sum(
            len(members)
            for _, members in by_state[state]
        )

        quotas[state] = _hamilton(
            total,
            {
                "train": 80,
                "validation": 10,
                "test": 10,
            },
            {
                "train": 0,
                "validation": 0,
                "test": 0,
            },
            {
                "train": total,
                "validation": total,
                "test": total,
            },
            f"prism-laya-v3-quota:{state}",
        )

    # --------------------------------------------------------
    # Deterministic exact subset selection
    # --------------------------------------------------------

    def choose_exact(
        candidates: list[
            tuple[str, list[LayaTrainingRecord]]
        ],
        target: int,
        namespace: str,
    ) -> set[str]:

        if target == 0:
            return set()

        ranked = sorted(
            candidates,
            key=lambda item: (
                _tie_score(namespace, item[0]),
                item[0],
            ),
        )

        # sum -> tuple(component IDs)
        dp: dict[int, tuple[str, ...]] = {
            0: (),
        }

        for component_id, members in ranked:
            size = len(members)

            snapshot = list(dp.items())

            for current, chosen in reversed(snapshot):
                new_total = current + size

                if new_total > target:
                    continue

                if new_total not in dp:
                    dp[new_total] = (
                        chosen + (component_id,)
                    )

            if target in dp:
                # Continue processing is unnecessary because
                # ranked order already defines deterministic
                # selection.
                break

        if target not in dp:
            raise ValueError(
                "V3_EXACT_STRATIFICATION_INFEASIBLE:"
                f"{namespace}:target={target}"
            )

        return set(dp[target])

    # --------------------------------------------------------
    # Assign components
    # --------------------------------------------------------

    assignments: dict[str, str] = {}

    for state in REQUIRED_ARTIFACT_STATES:
        state_components = by_state[state]

        train_ids = choose_exact(
            state_components,
            quotas[state]["train"],
            f"prism-laya-v3:{state}:train",
        )

        remaining = [
            item
            for item in state_components
            if item[0] not in train_ids
        ]

        validation_ids = choose_exact(
            remaining,
            quotas[state]["validation"],
            f"prism-laya-v3:{state}:validation",
        )

        for component_id, members in state_components:

            if component_id in train_ids:
                split = "train"

            elif component_id in validation_ids:
                split = "validation"

            else:
                split = "test"

            for record in members:
                assignments[record.record_id] = split

    if len(assignments) != len(records):
        raise ValueError(
            "V3_ASSIGNMENT_COVERAGE_FAILURE"
        )

    return assignments, quotas


def _gap(current: int, required: int) -> dict[str, int]:
    return {"current": current, "required": required, "missing": max(required - current, 0)}


class LayaDatasetService:
    def __init__(self, source_root: Path, output_root: Path):
        self.source_root = source_root
        self.output_root = output_root
        self.source = FractureDatasetService(source_root)
        self.training = LayaTrainingService()

    def _prepare(self) -> tuple[dict, dict[str, str]]:
        source_records = self.source_root / "records"
        if self.output_root.resolve() != (self.source_root / "laya").resolve():
            raise ValueError("Laya output must be the laya directory under the source root")
        if not source_records.is_dir() or not source_records.resolve().is_relative_to(self.source_root.resolve()):
            raise ValueError("PRISM-Fracture source records directory is unavailable")

        eligible: dict[str, LayaTrainingRecord] = {}
        rejected: list[dict] = []
        source_count = 0
        duplicate_count = 0
        for path in sorted(source_records.glob("pf_*.json")):
            if SAMPLE_ID_PATTERN.fullmatch(path.stem) is None or not path.is_file():
                continue
            source_count += 1
            source = self.source.read(path.stem)
            candidate = self.training.build(source)
            if not candidate.eligibility.eligible or candidate.record is None:
                rejected.append({
                    "source_record_id": source.sample_id,
                    "artifact_id": str(source.artifact.artifact_id),
                    "sha256": source.artifact.sha256,
                    "reasons": candidate.eligibility.reasons or ["NO_TRAINING_RECORD"],
                })
                continue
            record = candidate.record
            validate_model_input(record.model_input.model_dump(mode="json"))
            previous = eligible.get(record.record_id)
            if previous is not None:
                if previous.model_dump(mode="json") != record.model_dump(mode="json"):
                    raise ValueError(f"Conflicting training records share record ID {record.record_id}")
                duplicate_count += 1
                continue
            eligible[record.record_id] = record

        by_sha: dict[str, list[LayaTrainingRecord]] = defaultdict(list)
        for record in eligible.values():
            by_sha[record.sha256.lower()].append(record)
        final: list[LayaTrainingRecord] = []
        conflicting_count = 0
        for sha, group in sorted(by_sha.items()):
            group.sort(key=lambda item: item.record_id)
            targets = {_json_line(item.targets.model_dump(mode="json")) for item in group}
            if len(targets) > 1:
                conflicting_count += len(group)
                rejected.extend({
                    "source_record_id": item.source_record_id,
                    "artifact_id": str(item.artifact_id),
                    "sha256": item.sha256,
                    "reasons": ["CONFLICTING_TARGETS_FOR_SHA256"],
                } for item in group)
                continue
            final.append(group[0])
            for item in group[1:]:
                duplicate_count += 1
                rejected.append({
                    "source_record_id": item.source_record_id,
                    "artifact_id": str(item.artifact_id),
                    "sha256": item.sha256,
                    "reasons": ["DUPLICATE_SHA256"],
                })

        final.sort(key=lambda item: item.record_id)
        rejected.sort(key=lambda item: (item["source_record_id"], item["reasons"]))
        lines = [_json_line(item.model_dump(mode="json")) for item in final]
        assignments, quotas = _split_v3(final)
        split_records = {name: [] for name in ("train", "validation", "test")}
        group_splits: dict[str, str] = {}
        exact_input_splits: dict[str, str] = {}
        group_sizes: Counter[str] = Counter()
        explicit_groups: set[str] = set()
        fallback_groups: set[str] = set()
        state_support = {
            state: {"total": 0, "train": 0, "validation": 0, "test": 0}
            for state in REQUIRED_ARTIFACT_STATES
        }
        for item, line in zip(final, lines):
            split = assignments[item.record_id]
            existing_split = group_splits.setdefault(item.split_group_id, split)
            if existing_split != split:
                raise ValueError("CROSS_SPLIT_LINEAGE_LEAKAGE")

            exact_input_key = _json_line(
                item.model_input.model_dump(mode="json")
            ).rstrip("\n")

            existing_input_split = exact_input_splits.setdefault(
                exact_input_key,
                split,
            )

            if existing_input_split != split:
                raise ValueError(
                    "CROSS_SPLIT_EXACT_MODEL_INPUT_LEAKAGE"
                )

            group_sizes[item.split_group_id] += 1
            controlled = item.label_provenance.controlled_source
            if controlled is not None and controlled.lineage_group_id is not None:
                explicit_groups.add(item.split_group_id)
            else:
                fallback_groups.add(item.split_group_id)
            split_records[split].append(line)
            state_support[item.targets.artifact_state]["total"] += 1
            state_support[item.targets.artifact_state][split] += 1
        states = Counter(item.targets.artifact_state for item in final)
        escalations = Counter(item.targets.escalation for item in final)
        families = Counter(item.source_family for item in final)
        reasons = []
        if len(final) < MIN_ELIGIBLE_RECORDS:
            reasons.append("INSUFFICIENT_ELIGIBLE_RECORDS")
        for name in ("train", "validation", "test"):
            if not split_records[name]:
                reasons.append(f"EMPTY_{name.upper()}_SPLIT")
        if len(states) < MIN_DISTINCT_ARTIFACT_STATES:
            reasons.append("INSUFFICIENT_ARTIFACT_STATE_COVERAGE")
        required_support = list(state_support.values())
        if any(support["total"] < MIN_RECORDS_PER_REQUIRED_STATE for support in required_support):
            reasons.append("INSUFFICIENT_PER_STATE_SUPPORT")
        if any(any(support[split] < MIN_RECORDS_PER_REQUIRED_STATE_SPLIT
                   for split in ("train", "validation", "test"))
               for support in required_support):
            reasons.append("INSUFFICIENT_PER_STATE_SPLIT_COVERAGE")
        readiness_gap = {
            "eligible_records": _gap(len(final), MIN_ELIGIBLE_RECORDS),
            "distinct_artifact_states": _gap(len(states), MIN_DISTINCT_ARTIFACT_STATES),
            "artifact_states": {
                state: _gap(support["total"], MIN_RECORDS_PER_REQUIRED_STATE)
                for state, support in state_support.items()
            },
            "split_coverage": {
                state: {
                    split: _gap(support[split], MIN_RECORDS_PER_REQUIRED_STATE_SPLIT)
                    for split in ("train", "validation", "test")
                }
                for state, support in state_support.items()
            },
        }
        label_sources = {
            "BENIGN": {"available": True, "requirement": "Verified controlled harmless baseline provenance without a fracture or FastScan ambiguity."},
            "AMBIGUOUS": {"available": True, "requirement": "Existing deterministic FastScan ambiguity evidence."},
            "SUSPICIOUS": {"available": True, "requirement": "Verified deterministic security-relevant capability or structural-hazard evidence."},
            "FRACTURED": {"available": True, "requirement": "Verified Semantic Fracture evidence."},
        }
        missing_label_sources = [
            state for state in REQUIRED_ARTIFACT_STATES if not label_sources[state]["available"]
        ]
        if missing_label_sources:
            reasons.append("MISSING_AUTHORITATIVE_LABEL_SOURCE")
        acquisition_targets = []
        for state in REQUIRED_ARTIFACT_STATES:
            state_gap = readiness_gap["artifact_states"][state]["missing"]
            split_gap = sum(item["missing"] for item in readiness_gap["split_coverage"][state].values())
            if state_gap or split_gap:
                acquisition_targets.append({
                    "artifact_state": state,
                    "minimum_additional_records": max(state_gap, split_gap),
                    "label_source_available": label_sources[state]["available"],
                    "reason": label_sources[state]["requirement"],
                })
        total_eligible_deficit = readiness_gap["eligible_records"]["missing"]
        state_support_additions = sum(
            item["missing"] for item in readiness_gap["artifact_states"].values()
        )
        manifest = {
            "dataset_name": "PRISM-Laya",
            "schema_version": "1.0",
            "feature_stage": FEATURE_STAGE,
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "split_strategy": SPLIT_STRATEGY,
            "split_quotas_by_state": quotas,
            "split_grouping": {
                "strategy": "connected_components",
                "edges": [
                    "lineage_group_id_or_sha256_fallback",
                    "exact_model_input",
                ],
                "transitive": True,
            },
            "source": {"type": "PRISM_FRACTURE_VERIFIED_EVIDENCE"},
            "counts": {
                "source_records": source_count,
                "eligible_records": len(final),
                "rejected_records": len(rejected),
                "deduplicated_records": duplicate_count,
                "conflicting_records": conflicting_count,
            },
            "splits": {name: len(items) for name, items in split_records.items()},
            "exact_model_input": {
                "unique_inputs": len(exact_input_splits),
                "cross_split_violations": 0,
            },
            "lineage": {
                "groups": len(group_sizes),
                "explicit_lineage_groups": len(explicit_groups),
                "sha256_fallback_groups": len(fallback_groups),
                "largest_group_records": max(group_sizes.values(), default=0),
                "cross_split_violations": 0,
            },
            "artifact_states": {name: states[name] for name in REQUIRED_ARTIFACT_STATES},
            "state_support": state_support,
            "unsupported_artifact_states": [name for name in REQUIRED_ARTIFACT_STATES if states[name] == 0],
            "readiness_gap": readiness_gap,
            "label_sources": label_sources,
            "missing_authoritative_label_source_states": missing_label_sources,
            "evidence_acquisition_targets": acquisition_targets,
            "acquisition_summary": {
                "total_eligible_deficit": total_eligible_deficit,
                "minimum_state_support_additions": state_support_additions,
                "unallocated_eligible_deficit_after_state_minima": max(
                    total_eligible_deficit - state_support_additions, 0
                ),
            },
            "escalations": {name: escalations[name] for name in ("PASS", "DEEP_SCAN", "PRISM_LAB", "QUARANTINE")},
            "families": {name: families[name] for name in ("PDF", "ZIP", "PNG")},
            "dataset_fingerprint": "sha256:" + hashlib.sha256((
                "prism-laya-lineage-exact-input-v3\n" + "".join(lines) +
                "".join(f"{name}\n{''.join(split_records[name])}" for name in ("train", "validation", "test"))
            ).encode("utf-8")).hexdigest(),
            "training_ready": not reasons,
            "training_readiness_reasons": reasons,
        }
        contents = {
            "all.jsonl": "".join(lines),
            "rejected.jsonl": "".join(_json_line(item) for item in rejected),
            "manifest.json": json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        }
        contents.update({f"{name}.jsonl": "".join(items) for name, items in split_records.items()})
        return manifest, contents

    def preview(self) -> tuple[dict, dict[str, str]]:
        """Construct the complete official V3 output without writing files."""
        return self._prepare()

    def build(self) -> dict:
        manifest, contents = self._prepare()
        self.output_root.mkdir(parents=True, exist_ok=True)
        staged = {}
        try:
            for filename in OUTPUT_FILES:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", newline="\n", dir=self.output_root,
                    prefix=".laya-", suffix=".tmp", delete=False,
                ) as output:
                    output.write(contents[filename])
                    staged[filename] = Path(output.name)
            for filename in OUTPUT_FILES:
                os.replace(staged[filename], self.output_root / filename)
        finally:
            for temporary in staged.values():
                temporary.unlink(missing_ok=True)
        return manifest
