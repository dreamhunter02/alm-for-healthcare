"""Deterministic checks for the medical-device Deep Agent evaluation set."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CaseEvaluation:
    case_id: str
    passed: bool
    checks: dict[str, bool]
    failures: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "checks": self.checks,
            "failures": self.failures,
        }


def _normalize(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _contains_concept(answer: str, phrase: str) -> bool:
    normalized_answer = _normalize(answer)
    if _normalize(phrase) in normalized_answer:
        return True
    phrase_normalized = _normalize(phrase)
    answer_casefold = answer.casefold()
    asset_reference = "asset" in answer_casefold or "unit" in answer_casefold
    non_attribution = "attribut" in answer_casefold and asset_reference and any(
        word in answer_casefold for word in ("not", "cannot", "no ")
    )
    if phrase_normalized == "missingeventtounitlinkage":
        return ("link" in answer_casefold and asset_reference) or non_attribution
    if phrase_normalized == "cannotlink":
        explicit_non_link = "link" in answer_casefold and any(
            word in answer_casefold for word in ("not", "cannot")
        )
        return explicit_non_link or non_attribution
    if phrase_normalized == "missingdenominator":
        return "denominator" in answer_casefold and any(word in answer_casefold for word in ("no", "missing", "lack"))
    if phrase_normalized.startswith("fictionalhospital"):
        return "fictional" in answer_casefold and ("data" in answer_casefold or "inventory" in answer_casefold)
    if phrase_normalized == "cannotcalculateafailurerate":
        rate_denied = "failure rate" in answer_casefold and any(
            word in answer_casefold for word in ("cannot", "no ", "not ")
        )
        return rate_denied and any(word in answer_casefold for word in ("calculat", "quantif", "deriv", "estimat"))
    if phrase_normalized == "modellevelevidence":
        model_level = any(term in answer_casefold for term in ("model-level", "model level", "product-level"))
        return model_level and any(term in answer_casefold for term in ("evidence", "signal", "data", "record"))
    stop_words = {"a", "an", "are", "is", "of", "the", "to"}
    words = [word for word in re.findall(r"[a-z0-9]+", phrase.casefold()) if word not in stop_words]
    return bool(words) and all(word in answer.casefold() for word in words)


def _numbers(answer: str) -> list[float]:
    values: list[float] = []
    for token in re.findall(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?", answer):
        try:
            values.append(float(token.replace(",", "")))
        except ValueError:
            continue
    return values


def _artifact_valid(path: Path, media_type: str) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    prefix = path.read_bytes()[:16]
    if media_type == "image/png":
        return prefix.startswith(b"\x89PNG\r\n\x1a\n")
    if media_type == "text/csv":
        try:
            path.read_text()
        except UnicodeDecodeError:
            return False
        return path.suffix.casefold() == ".csv"
    return True


def evaluate_case(case: dict[str, Any], record: dict[str, Any], run_dir: Path) -> CaseEvaluation:
    answer = str(record.get("answer") or "")
    answer_normalized = _normalize(answer)
    tools = set(record.get("tools") or [])

    required_facts = all(_contains_concept(answer, str(fact)) for fact in case["required_facts"])
    required_tools = all(
        any(actual == required or actual.endswith(f"__{required}") for actual in tools)
        for required in case["required_tools"]
    )
    forbidden_claims = not any(_normalize(claim) in answer_normalized for claim in case["forbidden_claims"])
    required_disclaimers = all(_contains_concept(answer, disclaimer) for disclaimer in case["required_disclaimers"])
    numeric_values = _numbers(answer)
    numeric_tolerances = all(
        any(abs(value - float(item["expected"])) <= float(item["absolute"]) for value in numeric_values)
        for item in case["numeric_tolerances"]
    )
    artifacts = all(
        _artifact_valid(run_dir / item["path"], item["media_type"])
        for item in case["artifact_expectations"]
    )
    no_runtime_failure = not record.get("failure_reason")

    checks = {
        "required_facts": required_facts,
        "required_tools": required_tools,
        "forbidden_claims": forbidden_claims,
        "required_disclaimers": required_disclaimers,
        "numeric_tolerances": numeric_tolerances,
        "artifacts": artifacts,
        "no_runtime_failure": no_runtime_failure,
    }
    failures = [name for name, passed in checks.items() if not passed]
    return CaseEvaluation(
        case_id=case["id"],
        passed=not failures,
        checks=checks,
        failures=failures,
    )
