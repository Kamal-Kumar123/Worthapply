# Baseline Evaluation Report

## Primary Metric: Opportunity Decision Accuracy

- **Exact Accuracy:** 0.8824
- **Weighted Accuracy:** 0.9412

## Secondary Metrics

- Recommendation Accuracy: 0.8529
- Fit Accuracy: 0.9706
- Risk Accuracy: 0.8529

## Per-Category Breakdown

| Category | Count | Avg Priority Score |
|----------|-------|--------------------|
| A | 3 | 1.0 |
| B | 3 | 1.0 |
| C | 3 | 0.8333 |
| G | 1 | 1.0 |
| H | 2 | 1.0 |
| I | 2 | 0.75 |
| J | 3 | 1.0 |

## Failures (10 total)

- **case_009** [C]: predicted HIGH, expected MEDIUM (rec: APPLY vs APPLY_IF_TIME)
- **case_010**: execution_error — Request timed out.
- **case_011**: execution_error — Request timed out.
- **case_012**: execution_error — Request timed out.
- **case_013**: execution_error — Request timed out.
- **case_014**: execution_error — Request timed out.
- **case_015**: execution_error — Request timed out.
- **case_016**: execution_error — Request timed out.
- **case_018**: execution_error — Request timed out.
- **case_021** [I]: predicted MEDIUM, expected LOW (rec: APPLY_IF_TIME vs LOW_PRIORITY)
