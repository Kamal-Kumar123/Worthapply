# WorthApply — Architecture

## Overview

WorthApply uses a staged agentic pipeline where each agent handles one
verification dimension. The architecture was determined through measured
experiments, not designed upfront.

## LLM Provider Layer

```
┌─────────────────────────────────┐
│         LLMProvider (ABC)       │
│  generate() / generate_structured()  │
│  token tracking / cost estimation    │
├────────────────┬────────────────┤
│  XAIProvider   │ LocalProvider  │
│  (xAI Grok)   │ (Ollama, opt.) │
└────────────────┴────────────────┘
```

All agents depend on the `LLMProvider` abstraction. Switching providers
changes zero agent code.

## Target Pipeline (to be validated)

```
INPUT: Resume + Job URL/Description
           │
           ▼
    ┌──────────────┐
    │ Job Intel.   │  → Structured job profile
    │ Agent        │
    └──────┬───────┘
           │
    ┌──────┼──────────────┬──────────────┐
    │      │              │              │
    ▼      ▼              ▼              ▼
┌────────┐ ┌───────────┐ ┌────────────┐
│Company │ │Risk/Fresh.│ │Student Fit │
│Verify  │ │Agent      │ │Agent       │
│Agent   │ │           │ │            │
└───┬────┘ └─────┬─────┘ └──────┬─────┘
    │            │               │
    └────────────┼───────────────┘
                 │
                 ▼
    ┌──────────────────┐
    │ Evidence Store   │  ← all claims accumulated here
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Evidence         │  → verify/downgrade claims
    │ Verification     │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Decision         │  → final Opportunity Report
    │ Synthesizer      │
    └──────────────────┘
```

## Dimension Separation

These dimensions are kept independent throughout the pipeline:

| Dimension              | Source Agent(s)         |
|------------------------|------------------------|
| Student Fit            | Student Fit Agent       |
| Opportunity Confidence | Company + Risk Agents   |
| Risk Level             | Risk Agent              |
| Evidence Quality       | Evidence Verifier       |
| Recommendation         | Decision Synthesizer    |

A student can be a 95% fit for a HIGH-risk opportunity. These must
never be collapsed into a single unexplained score.

## Current Status

Only the **baseline** (single-prompt approach) is implemented.
The multi-agent architecture will be built iteratively based on
observed baseline failures.
