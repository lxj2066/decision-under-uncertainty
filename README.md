# Decision Under Uncertainty

**Turn “I think it’s worth it” into reproducible probabilities, expected values, and stop rules.**

Most decision prompts are mathematics theatre: they ask you for a base rate you don’t have, simulate a committee of experts that all agree, multiply correlated evidence as if it were independent, and end with “Go / No-go” without a threshold.

This package is the opposite. It is a seven-step decision framework with a calculator that refuses to invent numbers.

## The ten failure modes it fixes

| # | Failure | Fix |
|---|---|---|
| 1 | Asking users for success definitions and likelihood ratios | Structured elicitation, max 8 questions |
| 2 | No “ask first when information is missing” gate | Hard gate before any calculation |
| 3 | Simulated expert committees and Delphi rounds | Removed; evidence grading instead |
| 4 | No fallback when no base rate exists | `UNKNOWN` + wide prior + sensitivity |
| 5 | Unbounded LRs, correlated evidence multiplied | LR caps, reliability shrinkage, cluster merge |
| 6 | Serial Δp added together | Fault tree + leave-one-out criticality |
| 7 | Undefined cost normalisation and risk penalty | EV / utility / MCDA declared up front |
| 8 | Independent-and-identical attempts, no budget | Defined attempt + correlation ρ + budget cap |
| 9 | No Go/No-go threshold, no stop-loss | Five pre-registered thresholds |
| 10 | Loose modules, no execution order | Fixed seven-step workflow + exit checklist |

## Workflow

1. **Define** the decision, the options (including “do nothing”), the horizon, the success criterion, and the maximum loss.
2. **Base rate** — reference-class forecasting. No data → `UNKNOWN`, never invented.
3. **Evidence** — log-odds Bayesian update with capped likelihood ratios, reliability weighting, and correlated-evidence de-duplication.
4. **Failure chain** — fault tree with leave-one-out criticality; single points of failure.
5. **Options** — expected value, expected utility, risk of ruin, break-even probability, MCDA, sensitivity.
6. **Attempts** — define one attempt, add correlation, cap by budget; expected attempts and expected cost.
7. **Decision** — pre-registered thresholds → `Go` / `No-go` / `Conditional`, plus a stop rule and a review date.

## Calculator

```bash
python scripts/decision_calc.py bayes       spec.json
python scripts/decision_calc.py options     spec.json
python scripts/decision_calc.py attempts    spec.json
python scripts/decision_calc.py kelly       spec.json
python scripts/decision_calc.py faulttree   spec.json
python scripts/decision_calc.py montecarlo  spec.json
python scripts/decision_calc.py journal     spec.json
```

All commands read a JSON spec and print UTF-8 JSON. Monte Carlo uses a fixed seed.

Self-test:

```bash
python tests/selftest.py
```

## Design principles

- **No invented numbers.** Missing input → `UNKNOWN` with a reason.
- **No composite score without declared weights.** Ranking rules are chosen before results are seen.
- **Correlation is explicit.** Same-source evidence is merged; attempts can share outcomes.
- **Sensitivity is mandatory.** A single point estimate is not a conclusion.
- **Every recommendation has a stop rule.**
- **Determinism.** Same input, same output, same seed.

## Install

### Claude Code

```bash
git clone https://github.com/lxj2066/decision-under-uncertainty.git
cp -r decision-under-uncertainty/skills/decision-under-uncertainty ~/.claude/skills/
```

### WorkBuddy / CodeBuddy

Import this repository as an agent package.

## When to use it

- Should I build / launch / invest in this?
- What is the realistic success probability?
- Which of these options should come first?
- How many attempts does my budget buy?
- Where do I stop?

Not for: factual lookups, execution planning after a decision is made, or value judgements.

## Limitations

- Probabilities are only as good as the evidence and base rates you supply.
- The correlation model for attempts is an approximation, not a structural model.
- It does not price assets or give investment advice.
- Small samples make calibration scores noisy.

## License

[PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use requires a separate licence — see [COMMERCIAL.md](COMMERCIAL.md).

Author: 李献杰 Lyon
