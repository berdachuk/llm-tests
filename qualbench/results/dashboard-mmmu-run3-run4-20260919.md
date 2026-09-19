# Multimodal accuracy dashboard

- Generated: 2026-09-19T16:04:01.673934+00:00
- Suite: `mmmu-subset`
- Model: `qwen3.6-35b-a3b`
- Server: `http://127.0.0.1:8000`
- Runs supplied: 2
  - `mmmu-run3.jsonl` (60 items)
  - `mmmu-run4.jsonl` (60 items) (headline/tables below)
  - per-item tables use the **last run only**; earlier runs are used for the stability section, not averaged in

## Headline

- **Accuracy: 47/60 = 78.3%**
- Accuracy over items the model actually answered: 82.5% (57 answered)
- Strict (exact-match) accuracy: 78.3%
- Formatting slack (credit needing normalization/tolerance): 0.0%
- Random-chance floor for this item mix: 26.0% -> lift **52.3%**

Error decomposition -- wrong answers are separated from plumbing failures, because a truncated generation or a missing image is not a reasoning error:

| Outcome | Count |
|---|---|
| correct | 47 |
| wrong answer | 10 |
| no extractable answer | 0 |
| truncated generation (token budget) | 3 |

## Accuracy by visual domain

`threshold` is the regression bar this suite enforces per domain (see `thresholds.json`); it is a guard against drift, not a claim about the model's ceiling.

| Domain | Correct | Accuracy | | Threshold | Verdict |
|---|---|---|---|---|---|
| charts | 15/16 | 93.8% | `###################.` | 50.0% | PASS |
| screen-captures | 11/12 | 91.7% | `##################..` | 50.0% | PASS |
| diagrams | 11/16 | 68.8% | `##############......` | 40.0% | PASS |
| photos | 10/16 | 62.5% | `############........` | 60.0% | PASS |

Domain spread: range **31.2%**, stdev 13.7% (best `charts`, worst `photos`). A wide spread means the headline number hides a modality the model is materially worse at.

## Accuracy by MMMU subject

| Group | Correct | Accuracy |
|---|---|---|
| Accounting | 3/3 | 100.0% |
| Architecture_and_Engineering | 2/2 | 100.0% |
| Art | 2/2 | 100.0% |
| Biology | 3/3 | 100.0% |
| Chemistry | 1/1 | 100.0% |
| Clinical_Medicine | 2/2 | 100.0% |
| Computer_Science | 2/2 | 100.0% |
| Diagnostics_and_Laboratory_Medicine | 1/1 | 100.0% |
| Economics | 1/1 | 100.0% |
| Electronics | 1/1 | 100.0% |
| Energy_and_Power | 1/1 | 100.0% |
| Literature | 4/4 | 100.0% |
| Marketing | 1/1 | 100.0% |
| Materials | 1/1 | 100.0% |
| Math | 1/1 | 100.0% |
| Physics | 1/1 | 100.0% |
| Psychology | 4/4 | 100.0% |
| Public_Health | 1/1 | 100.0% |
| Manage | 4/5 | 80.0% |
| Design | 2/3 | 66.7% |
| Pharmacy | 2/3 | 66.7% |
| History | 3/5 | 60.0% |
| Sociology | 3/5 | 60.0% |
| Art_Theory | 1/2 | 50.0% |
| Agriculture | 0/1 | 0.0% |
| Basic_Medical_Science | 0/1 | 0.0% |
| Geography | 0/1 | 0.0% |
| Mechanical_Engineering | 0/1 | 0.0% |
| Music | 0/1 | 0.0% |

## Run-to-run stability

- Runs compared: 2
- Repeated items: 60 (45 always correct, 7 always wrong, 1 flipped)
- Per-run accuracy: 80.0%, 78.3% -> spread **1.7%**. Differences smaller than this are noise, not signal.

| Flaky item | Domain | Correct/attempts | Answers seen |
|---|---|---|---|
| diagrams-09-history | diagrams | 1/2 | 'C', 'A' |

## Comparison against published benchmark numbers

Reference benchmark: **MMMU (validation)**.

> Caveat, and it is a big one: this suite scores a stratified **subset** with its own prompt and answer parser, while published numbers use the full official split and harness. The two are not the same measurement. Read this table as a sanity check on whether local vision is working at roughly the expected level, not as a leaderboard comparison.

| Model | Accuracy | Comparability | Source | As of |
|---|---|---|---|---|
| **this run** (`qwen3.6-35b-a3b`) | **78.3%** | local subset, n=60 | this suite | 2026-09-19 |
| PLACEHOLDER -- fill in a comparable open VLM | n/a | different-subset | **UNVERIFIED placeholder** | n/a |

1 reference row(s) are unsourced placeholders and must not be cited. Fill in `public_benchmarks.json` with sourced figures (each needs `source` and `as_of`).

## Failing items (13)

| Item | Domain | Expected | Got | Reason |
|---|---|---|---|---|
| charts-16-sociology | charts | `C` | `B` | expected option C, got 'B' |
| photos-01-agriculture | photos (truncated) | `B` | `` | truncated: finish_reason=length (content: 'The user wants me to identify the cause of the corky outgrowths on the ash tr |
| photos-04-basic_medical_science | photos | `B` | `A` | expected option B, got 'A' |
| photos-09-geography | photos | `D` | `A` | expected option D, got 'A' |
| photos-12-manage | photos | `C` | `A` | expected option C, got 'A' |
| photos-13-mechanical_engineering | photos (truncated) | `B` | `` | truncated: finish_reason=length (content: 'The user wants me to identify the incorrect thread labeling method from the p |
| photos-16-sociology | photos | `B` | `A` | expected option B, got 'A' |
| screen-captures-04-history | screen-captures | `D` | `C` | expected option D, got 'C' |
| diagrams-03-art_theory | diagrams | `A` | `D` | expected option A, got 'D' |
| diagrams-06-design | diagrams | `C` | `D` | expected option C, got 'D' |
| diagrams-09-history | diagrams | `C` | `A` | expected option C, got 'A' |
| diagrams-13-music | diagrams | `B` | `D` | expected option B, got 'D' |
| diagrams-14-pharmacy | diagrams (truncated) | `B` | `` | truncated: finish_reason=length (content: 'The user wants me to identify the chemical structure shown in the image.\n\n1 |
