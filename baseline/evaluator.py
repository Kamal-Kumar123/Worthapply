"""Evaluate baseline results against ground truth.

Usage:
    python -m baseline.evaluator
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "results" / "baseline"


def score_priority(predicted: str, expected: str) -> float:
    """Score priority classification: 1.0 exact, 0.5 adjacent, 0.0 opposite."""
    if not predicted or not expected:
        return 0.0
    predicted = predicted.upper().strip()
    expected = expected.upper().strip()
    if predicted == expected:
        return 1.0
    ordered = ["HIGH", "MEDIUM", "LOW"]
    if predicted in ordered and expected in ordered:
        diff = abs(ordered.index(predicted) - ordered.index(expected))
        return 0.5 if diff == 1 else 0.0
    return 0.0


def score_recommendation(predicted: str, expected: str) -> float:
    if not predicted or not expected:
        return 0.0
    predicted = predicted.upper().strip()
    expected = expected.upper().strip()
    if predicted == expected:
        return 1.0
    ordered = ["APPLY", "APPLY_IF_TIME", "LOW_PRIORITY"]
    if predicted in ordered and expected in ordered:
        diff = abs(ordered.index(predicted) - ordered.index(expected))
        return 0.5 if diff == 1 else 0.0
    return 0.0


def score_fit(predicted_score: float, expected_range: list[float]) -> float:
    if len(expected_range) != 2:
        return 0.0
    low, high = expected_range
    if low <= predicted_score <= high:
        return 1.0
    extended_low = max(0, low - 15)
    extended_high = min(100, high + 15)
    if extended_low <= predicted_score <= extended_high:
        return 0.5
    return 0.0


def score_risk(predicted: str, expected: str) -> float:
    if not predicted or not expected:
        return 0.0
    return score_priority(predicted, expected)


def evaluate_results() -> dict:
    """Load baseline results and score against ground truth."""
    raw_path = RESULTS_DIR / "raw_results.json"
    if not raw_path.exists():
        print(f"No results found at {raw_path}. Run baseline first.")
        return {}

    with open(raw_path, encoding="utf-8") as f:
        results = json.load(f)

    scores = []
    category_scores: dict[str, list[float]] = {}
    failures: list[dict] = []

    for r in results:
        if r.get("status") != "success":
            failures.append({
                "case_id": r["case_id"],
                "failure_type": "execution_error",
                "error": r.get("error", "unknown"),
            })
            continue

        predicted = r.get("predicted", {})
        gt = r.get("ground_truth", {})

        case_scores = {
            "case_id": r["case_id"],
            "category": r.get("category", ""),
            "priority_score": score_priority(
                predicted.get("priority", ""), gt.get("expected_priority", "")
            ),
            "recommendation_score": score_recommendation(
                predicted.get("recommendation", ""),
                gt.get("expected_recommendation", ""),
            ),
            "fit_score": score_fit(
                predicted.get("fit_score", 50),
                gt.get("expected_fit_range", [0, 100]),
            ),
            "risk_score": score_risk(
                predicted.get("risk_level", ""),
                gt.get("expected_risk_level", ""),
            ),
            "predicted": predicted,
            "expected": gt,
        }

        scores.append(case_scores)

        cat = r.get("category", "?")
        if cat not in category_scores:
            category_scores[cat] = []
        category_scores[cat].append(case_scores["priority_score"])

        if case_scores["priority_score"] < 1.0:
            failures.append({
                "case_id": r["case_id"],
                "category": r.get("category", ""),
                "failure_type": "priority_mismatch",
                "predicted_priority": predicted.get("priority", ""),
                "expected_priority": gt.get("expected_priority", ""),
                "predicted_recommendation": predicted.get("recommendation", ""),
                "expected_recommendation": gt.get("expected_recommendation", ""),
                "predicted_fit": predicted.get("fit_score", 0),
                "expected_fit_range": gt.get("expected_fit_range", []),
                "predicted_risk": predicted.get("risk_level", ""),
                "expected_risk": gt.get("expected_risk_level", ""),
            })

    n = len(scores)
    if n == 0:
        return {"error": "No successful results to evaluate"}

    evaluation = {
        "total_cases": len(results),
        "evaluated": n,
        "errors": len(results) - n,
        "primary_metric": {
            "name": "Opportunity Decision Accuracy",
            "exact_accuracy": round(
                sum(1 for s in scores if s["priority_score"] == 1.0) / n, 4
            ),
            "weighted_accuracy": round(
                sum(s["priority_score"] for s in scores) / n, 4
            ),
        },
        "secondary_metrics": {
            "recommendation_accuracy": round(
                sum(s["recommendation_score"] for s in scores) / n, 4
            ),
            "fit_accuracy": round(
                sum(s["fit_score"] for s in scores) / n, 4
            ),
            "risk_accuracy": round(
                sum(s["risk_score"] for s in scores) / n, 4
            ),
        },
        "per_category": {
            cat: {
                "count": len(vals),
                "avg_priority_score": round(sum(vals) / len(vals), 4),
            }
            for cat, vals in sorted(category_scores.items())
        },
        "failures": failures,
        "case_scores": scores,
    }

    return evaluation


def save_evaluation(evaluation: dict) -> None:
    """Save evaluation results to disk."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    eval_path = RESULTS_DIR / "evaluation.json"
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(evaluation, f, indent=2, default=str)

    report_lines = [
        "# Baseline Evaluation Report",
        "",
        "## Primary Metric: Opportunity Decision Accuracy",
        "",
    ]

    pm = evaluation.get("primary_metric", {})
    report_lines.append(f"- **Exact Accuracy:** {pm.get('exact_accuracy', 'N/A')}")
    report_lines.append(f"- **Weighted Accuracy:** {pm.get('weighted_accuracy', 'N/A')}")
    report_lines.append("")

    sm = evaluation.get("secondary_metrics", {})
    report_lines.append("## Secondary Metrics")
    report_lines.append("")
    report_lines.append(f"- Recommendation Accuracy: {sm.get('recommendation_accuracy', 'N/A')}")
    report_lines.append(f"- Fit Accuracy: {sm.get('fit_accuracy', 'N/A')}")
    report_lines.append(f"- Risk Accuracy: {sm.get('risk_accuracy', 'N/A')}")
    report_lines.append("")

    report_lines.append("## Per-Category Breakdown")
    report_lines.append("")
    report_lines.append("| Category | Count | Avg Priority Score |")
    report_lines.append("|----------|-------|--------------------|")
    for cat, data in evaluation.get("per_category", {}).items():
        report_lines.append(f"| {cat} | {data['count']} | {data['avg_priority_score']} |")
    report_lines.append("")

    failures = evaluation.get("failures", [])
    report_lines.append(f"## Failures ({len(failures)} total)")
    report_lines.append("")
    for f in failures:
        case_id = f.get("case_id", "?")
        ftype = f.get("failure_type", "?")
        if ftype == "priority_mismatch":
            report_lines.append(
                f"- **{case_id}** [{f.get('category', '?')}]: "
                f"predicted {f.get('predicted_priority', '?')}, "
                f"expected {f.get('expected_priority', '?')} "
                f"(rec: {f.get('predicted_recommendation', '?')} vs "
                f"{f.get('expected_recommendation', '?')})"
            )
        else:
            report_lines.append(
                f"- **{case_id}**: {ftype} — {f.get('error', '')}"
            )
    report_lines.append("")

    report_path = RESULTS_DIR / "report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Evaluation saved to {eval_path}")
    print(f"Report saved to {report_path}")


def main():
    evaluation = evaluate_results()
    if evaluation and "error" not in evaluation:
        save_evaluation(evaluation)
        pm = evaluation["primary_metric"]
        print(f"\n{'='*60}")
        print(f"BASELINE RESULTS")
        print(f"{'='*60}")
        print(f"Exact Accuracy:    {pm['exact_accuracy']:.1%}")
        print(f"Weighted Accuracy: {pm['weighted_accuracy']:.1%}")
        sm = evaluation["secondary_metrics"]
        print(f"Recommendation:    {sm['recommendation_accuracy']:.1%}")
        print(f"Fit Accuracy:      {sm['fit_accuracy']:.1%}")
        print(f"Risk Accuracy:     {sm['risk_accuracy']:.1%}")
        print(f"Failures:          {len(evaluation['failures'])}")
        print(f"{'='*60}")
    elif evaluation:
        print(evaluation.get("error", "Unknown error"))


if __name__ == "__main__":
    main()
