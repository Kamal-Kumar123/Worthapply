"""Scoring functions implementing the WorthApply evaluation rubric."""

from __future__ import annotations

import statistics
from typing import Any


PRIORITY_LEVELS = ["LOW", "MEDIUM", "HIGH"]
RECOMMENDATION_LEVELS = ["LOW_PRIORITY", "APPLY_IF_TIME", "APPLY"]


def _ordinal_distance(predicted: str, expected: str, levels: list[str]) -> int:
    """Return the ordinal distance between two values on a scale."""
    try:
        return abs(levels.index(predicted.upper()) - levels.index(expected.upper()))
    except ValueError:
        return len(levels)


def score_priority(predicted: str, expected: str) -> float:
    """Score opportunity priority classification.

    Returns:
        1.0 for exact match, 0.5 for adjacent (HIGH↔MEDIUM or MEDIUM↔LOW),
        0.0 for opposite (HIGH↔LOW) or invalid values.
    """
    dist = _ordinal_distance(predicted, expected, PRIORITY_LEVELS)
    if dist == 0:
        return 1.0
    if dist == 1:
        return 0.5
    return 0.0


def score_fit(predicted_score: float, expected_range: list[float]) -> float:
    """Score student fit accuracy.

    Args:
        predicted_score: The system's numeric fit score (0-100).
        expected_range: Two-element list [low, high] defining the acceptable range.

    Returns:
        1.0 if within range, 0.5 if within 15 points of the range, 0.0 otherwise.
    """
    low, high = expected_range[0], expected_range[1]
    if low <= predicted_score <= high:
        return 1.0
    distance = min(abs(predicted_score - low), abs(predicted_score - high))
    if distance <= 15:
        return 0.5
    return 0.0


def score_recommendation(predicted: str, expected: str) -> float:
    """Score recommendation accuracy.

    Returns:
        1.0 for exact match, 0.5 for adjacent, 0.0 for opposite or invalid.
    """
    dist = _ordinal_distance(predicted, expected, RECOMMENDATION_LEVELS)
    if dist == 0:
        return 1.0
    if dist == 1:
        return 0.5
    return 0.0


def score_risk_detection(
    detected_signals: list[str], expected_signals: list[str]
) -> float:
    """Score risk signal detection as recall.

    Matching is case-insensitive substring: a detected signal matches an expected
    signal if either is a substring of the other after lowercasing.

    Returns:
        Fraction of expected signals that were detected. 1.0 if there are no
        expected signals.
    """
    if not expected_signals:
        return 1.0

    detected_lower = [s.lower() for s in detected_signals]
    hits = 0
    for expected in expected_signals:
        exp_lower = expected.lower()
        for det in detected_lower:
            if exp_lower in det or det in exp_lower:
                hits += 1
                break
    return hits / len(expected_signals)


def score_evidence_support(claims: list[dict[str, Any]]) -> float:
    """Score evidence support rate.

    Each claim dict should have a ``statement`` and ``evidence`` field.

    Returns:
        Fraction of claims whose evidence is non-empty. 1.0 if there are no claims.
    """
    if not claims:
        return 1.0

    supported = 0
    for claim in claims:
        evidence = claim.get("evidence")
        if evidence and (not isinstance(evidence, str) or evidence.strip()):
            supported += 1
    return supported / len(claims)


def evaluate_case(predicted: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single case against ground truth.

    Expected keys in *predicted*:
        - priority: str ("HIGH", "MEDIUM", or "LOW")
        - fit_score: float (0-100)
        - recommendation: str ("APPLY", "APPLY_IF_TIME", or "LOW_PRIORITY")
        - risk_signals: list[str]
        - claims: list[dict] with "statement" and "evidence" keys
        - latency_seconds: float (optional)
        - cost_usd: float (optional)

    Expected keys in *ground_truth*:
        - priority: str
        - fit_range: [low, high]
        - recommendation: str
        - expected_risk_signals: list[str]

    Returns:
        Dictionary of individual metric scores.
    """
    scores: dict[str, Any] = {
        "priority_score": score_priority(
            predicted.get("priority", ""),
            ground_truth.get("priority", ""),
        ),
        "fit_score": score_fit(
            predicted.get("fit_score", 0.0),
            ground_truth.get("fit_range", [0, 100]),
        ),
        "recommendation_score": score_recommendation(
            predicted.get("recommendation", ""),
            ground_truth.get("recommendation", ""),
        ),
        "risk_recall": score_risk_detection(
            predicted.get("risk_signals", []),
            ground_truth.get("expected_risk_signals", []),
        ),
        "evidence_support": score_evidence_support(
            predicted.get("claims", []),
        ),
    }

    if "latency_seconds" in predicted:
        scores["latency_seconds"] = predicted["latency_seconds"]
    if "cost_usd" in predicted:
        scores["cost_usd"] = predicted["cost_usd"]

    return scores


def evaluate_batch(
    results: list[dict[str, Any]], ground_truths: list[dict[str, Any]]
) -> dict[str, Any]:
    """Evaluate a full batch and return aggregate scores.

    Returns a dictionary with:
        - per_case: list of individual case score dicts
        - accuracy: fraction of exact priority matches
        - weighted_accuracy: mean priority score (with partial credit)
        - mean_fit_score, mean_recommendation_score, mean_risk_recall,
          mean_evidence_support
        - per_category: dict mapping ground-truth priority to sub-metrics
        - latency: dict with mean, median, p95, max (if available)
        - cost: dict with mean, total (if available)
    """
    per_case: list[dict[str, Any]] = []
    for pred, gt in zip(results, ground_truths):
        per_case.append(evaluate_case(pred, gt))

    priority_scores = [c["priority_score"] for c in per_case]
    fit_scores = [c["fit_score"] for c in per_case]
    rec_scores = [c["recommendation_score"] for c in per_case]
    risk_recalls = [c["risk_recall"] for c in per_case]
    evidence_rates = [c["evidence_support"] for c in per_case]

    evaluation: dict[str, Any] = {
        "per_case": per_case,
        "accuracy": sum(1 for s in priority_scores if s == 1.0) / max(len(priority_scores), 1),
        "weighted_accuracy": _safe_mean(priority_scores),
        "mean_fit_score": _safe_mean(fit_scores),
        "mean_recommendation_score": _safe_mean(rec_scores),
        "mean_risk_recall": _safe_mean(risk_recalls),
        "mean_evidence_support": _safe_mean(evidence_rates),
    }

    # Per-category breakdown by ground-truth priority
    categories: dict[str, list[dict[str, Any]]] = {}
    for case_scores, gt in zip(per_case, ground_truths):
        cat = gt.get("priority", "UNKNOWN").upper()
        categories.setdefault(cat, []).append(case_scores)

    per_category: dict[str, dict[str, Any]] = {}
    for cat, cases in categories.items():
        cat_priority = [c["priority_score"] for c in cases]
        per_category[cat] = {
            "count": len(cases),
            "accuracy": sum(1 for s in cat_priority if s == 1.0) / len(cases),
            "weighted_accuracy": _safe_mean(cat_priority),
            "mean_fit_score": _safe_mean([c["fit_score"] for c in cases]),
            "mean_recommendation_score": _safe_mean([c["recommendation_score"] for c in cases]),
            "mean_risk_recall": _safe_mean([c["risk_recall"] for c in cases]),
            "mean_evidence_support": _safe_mean([c["evidence_support"] for c in cases]),
        }
    evaluation["per_category"] = per_category

    # Latency statistics
    latencies = [c["latency_seconds"] for c in per_case if "latency_seconds" in c]
    if latencies:
        sorted_lat = sorted(latencies)
        p95_idx = min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)
        evaluation["latency"] = {
            "mean": _safe_mean(latencies),
            "median": statistics.median(latencies),
            "p95": sorted_lat[p95_idx],
            "max": max(latencies),
        }

    # Cost statistics
    costs = [c["cost_usd"] for c in per_case if "cost_usd" in c]
    if costs:
        evaluation["cost"] = {
            "mean": _safe_mean(costs),
            "total": sum(costs),
        }

    return evaluation


def generate_report(evaluation: dict[str, Any]) -> str:
    """Generate a human-readable markdown summary from evaluation results.

    Args:
        evaluation: Output of ``evaluate_batch``.

    Returns:
        A markdown-formatted string.
    """
    lines: list[str] = []
    lines.append("# WorthApply Evaluation Report\n")

    lines.append("## Primary Metric: Opportunity Decision Accuracy\n")
    lines.append(f"- **Accuracy (exact match):** {evaluation.get('accuracy', 'NOT YET EVALUATED'):.2%}"
                 if isinstance(evaluation.get("accuracy"), (int, float))
                 else f"- **Accuracy:** {evaluation.get('accuracy', 'NOT YET EVALUATED')}")
    lines.append(f"- **Weighted Accuracy:** {evaluation.get('weighted_accuracy', 'NOT YET EVALUATED'):.2%}"
                 if isinstance(evaluation.get("weighted_accuracy"), (int, float))
                 else f"- **Weighted Accuracy:** {evaluation.get('weighted_accuracy', 'NOT YET EVALUATED')}")

    per_category = evaluation.get("per_category", {})
    if per_category:
        lines.append("\n### Per-Category Breakdown\n")
        lines.append("| Category | Count | Accuracy | Weighted Acc | Fit | Recommendation | Risk Recall | Evidence |")
        lines.append("|----------|------:|----------|-------------|-----|---------------|------------|----------|")
        for cat in ["HIGH", "MEDIUM", "LOW"]:
            if cat in per_category:
                c = per_category[cat]
                lines.append(
                    f"| {cat} | {c['count']} "
                    f"| {c['accuracy']:.2%} "
                    f"| {c['weighted_accuracy']:.2%} "
                    f"| {c['mean_fit_score']:.2%} "
                    f"| {c['mean_recommendation_score']:.2%} "
                    f"| {c['mean_risk_recall']:.2%} "
                    f"| {c['mean_evidence_support']:.2%} |"
                )

    lines.append("\n## Secondary Metrics\n")
    _append_metric(lines, "Mean Fit Score", evaluation.get("mean_fit_score"))
    _append_metric(lines, "Mean Recommendation Score", evaluation.get("mean_recommendation_score"))
    _append_metric(lines, "Mean Risk Recall", evaluation.get("mean_risk_recall"))
    _append_metric(lines, "Mean Evidence Support", evaluation.get("mean_evidence_support"))

    latency = evaluation.get("latency")
    if latency:
        lines.append("\n### Latency\n")
        lines.append(f"- **Mean:** {latency['mean']:.2f}s")
        lines.append(f"- **Median:** {latency['median']:.2f}s")
        lines.append(f"- **p95:** {latency['p95']:.2f}s")
        lines.append(f"- **Max:** {latency['max']:.2f}s")

    cost = evaluation.get("cost")
    if cost:
        lines.append("\n### Cost\n")
        lines.append(f"- **Mean per case:** ${cost['mean']:.4f}")
        lines.append(f"- **Total:** ${cost['total']:.4f}")

    lines.append("\n## Qualitative Rubric\n")
    lines.append("| Dimension | Score |")
    lines.append("|-----------|-------|")
    for dim in ["evidence_quality", "uncertainty_handling", "separation_of_dimensions", "actionability"]:
        label = dim.replace("_", " ").title()
        val = evaluation.get(dim, "NOT YET EVALUATED")
        if isinstance(val, (int, float)):
            lines.append(f"| {label} | {val}/5 |")
        else:
            lines.append(f"| {label} | {val} |")

    n_cases = len(evaluation.get("per_case", []))
    lines.append(f"\n---\n*Evaluated on {n_cases} case(s).*\n")

    return "\n".join(lines)


def _safe_mean(values: list[float]) -> float:
    """Return the arithmetic mean, or 0.0 for an empty list."""
    return statistics.mean(values) if values else 0.0


def _append_metric(lines: list[str], label: str, value: Any) -> None:
    """Append a formatted metric line."""
    if isinstance(value, (int, float)):
        lines.append(f"- **{label}:** {value:.2%}")
    else:
        lines.append(f"- **{label}:** {value if value is not None else 'NOT YET EVALUATED'}")
