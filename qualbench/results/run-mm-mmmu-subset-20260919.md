# qualbench multimodal (vision) run: MMMU subset, 2026-09-19

- Server: `http://192.168.0.88:8000` (RTX 4090, 24.5 GiB, remote)
- Model: `qwen3.6-35b-a3b` (Qwen3.6-35B-A3B-FP8, vision tower active)
- Suite: `mmmu-subset` -- **60 items**, MMMU *validation* split, stratified
  across 4 visual domains (charts 16, photos 16, diagrams 16,
  screen-captures 12), seed `20260919`
- Harness: `qualbench/fixtures/multimodal/check.py`, images sent as base64
  data URLs, `temperature=0`, `reasoning_effort=low`
- **Headline: 48/60 = 80.0%**, reproduced at **47/60 = 78.3%** on a
  same-config repeat (`--max-tokens 16384`)

## The number only makes sense together with the token budget

This suite was brought up in stages, and each stage produced a different
headline because the token budget -- not the model -- was changing:

| run | `max_tokens` | accuracy | truncated | genuine wrong answers | accuracy over answered |
|---|---|---|---|---|---|
| 1 | 1024->2048 | 35/60 = **58.3%** | 21 | 4 | 89.7% |
| 2 | 4096 | 40/60 = **66.7%** | 12 | 8 | 83.3% |
| 3 | **16384** | 48/60 = **80.0%** | 4 | 8 | 85.7% |
| 4 | **16384** (repeat) | 47/60 = **78.3%** | 3 | 10 | 82.5% |

Real MMMU figures need far more reasoning than this model's text tasks:
one item consumed **10,421 completion tokens** and 293s. At the original
budgets the model was being cut off mid-analysis and scored wrong, which
produced a phantom accuracy of 58.3%. Direct evidence, re-running the
items that truncated in *both* runs 1 and 2 at 16384:

| item | tokens used | result at 16384 |
|---|---|---|
| `charts-11-materials` | 9390 | correct |
| `diagrams-05-computer_science` | 10421 | correct |
| `diagrams-07-electronics` | 9427 | correct |
| `diagrams-03-art_theory` | 4353 | genuinely wrong |

Three of four were never reasoning failures. **The wrong-answer count
stayed at 8 from 4096 onwards** -- raising the budget revealed real
capability rather than inflating it.

The four residual truncations at 16384 (`charts-05`, `photos-04`,
`diagrams-06`, `diagrams-08`) each burned 300-500s: those are genuine
reasoning loops and are counted honestly as plumbing failures. The run-4
repeat truncated a *different* set of three (`photos-01`, `photos-13`,
`diagrams-14`) -- all near the budget boundary rather than deterministic
failures, which is why they are excluded from the stability count below.

## Results by visual domain (runs 3 + 4, same config)

| domain | run 3 | run 4 | threshold | verdict |
|---|---|---|---|---|
| screen-captures | 11/12 = 91.7% | 11/12 = 91.7% | 50% | PASS |
| charts | 14/16 = 87.5% | 15/16 = 93.8% | 50% | PASS |
| diagrams | 12/16 = 75.0% | 11/16 = 68.8% | 40% | PASS |
| photos | 11/16 = 68.8% | 10/16 = 62.5% | 60% | PASS |
| **total** | **48/60 = 80.0%** | **47/60 = 78.3%** | | |

Run 3 spread: range 22.9%, stdev 9.2%. Random-chance floor for this item
mix: **26.0%** (4-option multiple choice), so lift over chance is **54.0
points** -- the score carries real signal. Run 4's spread is wider
(31.2%) with the same ordering.

**Photos is the weakest bucket in both runs**, contrary to what the
truncated runs suggested (they pointed at diagrams). That is a genuine
capability signal -- medical/histology imagery, agriculture, geography --
not a budget artifact. It is also borderline: 68.8% and 62.5% against a
60% threshold.

Caveat: many subjects contribute only 1-3 items, so individual
subject-level scores (many 0/1 or 1/1) carry almost no information and
are not reported as findings.

## Run-to-run stability: ~2% flakiness (two clean samples)

Run 4 repeated run 3 at the **identical configuration** (max_tokens
16384, same suite, same seed), which is the only comparison that
measures genuine model variance. Run 3's records predate config
embedding, but the config is provable from the data itself: run 3 has
correct answers that consumed 15,900 completion tokens, impossible under
any smaller budget. The run-config guard still reports it as
unverifiable, because it only reads headers -- erring conservative.

| pair | runs | accuracy spread | measurable items | always correct | always wrong | flipped |
|---|---|---|---|---|---|---|
| same config | 3 + 4 | 80.0% -> 78.3% (**1.7%**) | 53 | 45 | 7 | **1 (1.9%)** |

The single flip (`diagrams-09-history`, C -> A) is the only changed
opinion in two clean full runs. Seven items were excluded from the
count because one run truncated them; they cluster at the 16k-token
boundary (e.g. `diagrams-08-energy_and_power` 13,279 tokens when it
succeeds). This contrasts sharply with the *text* categories on this
same FP8 build, which show ~10-30% nondeterminism on long reasoning
tasks: a vision answer is one option letter, leaving little room for a
reasoning loop to land somewhere different.

Two caveats, both material:

1. The 21.7% accuracy "spread" between runs 1-3 is **not model
   variance** -- those runs used different token budgets. A run-config
   comparison now detects and labels this automatically.
2. Flakiness is measured only on items neither run truncated, so the
   hardest high-token items are the least covered by this claim.

Run 4 also reproduced the domain ordering (charts strongest,
screen-captures next, photos weakest), and all four buckets PASSed
again, though the totals moved: charts 15/16 (93.8%), screen-captures
11/12 (91.7%), diagrams 11/16 (68.8%), photos 10/16 (62.5%) -- exactly
at its 60% threshold. Photos is the bucket to watch: borderline at both
clean budgets.

## What this run does NOT tell you

- **Not comparable to published MMMU scores.** This is a 60-item
  stratified subset scored with our own prompt and answer parser;
  published numbers use the full 900-item validation split and the
  official harness. `public_benchmarks.json` ships with unsourced
  placeholders marked `UNVERIFIED`, and the dashboard refuses to present
  them as fact.
- **Not a full-suite MMMU result.** 900 validation items exist; 60 were
  sampled deliberately to keep runtime sane while covering four visual
  domains with enough items each to be meaningful.
- **Video is untested.** Video-MME annotations are present locally but no
  clips are staged, so video items fail as explicit *staging* errors and
  are excluded from the accuracy numbers rather than scored as failures.

## Three harness/fixture bugs found during bring-up

1. **Truncation mistaken for wrong answers** (fixed): see the budget
   table above.
2. **Hedged multiple-choice answers credited** (fixed): a reply like
   `"Both B and C"` was scored correct because its first character
   matched. Now detected and refused -- this would have inflated
   multiple-choice accuracy.
3. **Ambiguous fixture ground truth** (fixed): synthetic `chart-02` was
   a genuine tie (B and C both +10) but asserted `B`; the model's `C`
   was scored wrong. It was our bug, not the model's. Verified
   end-to-end after the fix: the smoke suite now scores 15/16 = 93.8%
   (the miss is a truncated reasoning loop, not a wrong answer).

A fourth, reporting-side bug was found and fixed after the runs: a
dashboard given several run files labelled them "runs aggregated" while
its tables actually came from the latest run only. It now states which
run supplies the headline and that earlier runs feed the stability
section instead of being averaged in.

## Reproducing

```bash
cd qualbench/fixtures/multimodal
export QUALBENCH_MM_MEDIA_ROOT=/mnt/data/qwen36-mm-eval/media
python3 check.py --all --suite mmmu-subset \
  --url http://192.168.0.88:8000 --model qwen3.6-35b-a3b \
  --timeout 900 --emit-artifacts --records-out results/mmmu.jsonl
python3 variance_report.py results/mmmu.jsonl      # ground-truth analysis
python3 dashboard.py results/mmmu.jsonl -o results/dashboard.md
```

Runtime: ~1.5 h for the 60 items at this budget (several items need
minutes each). Records are flushed incrementally, so an interrupted run
retains completed items. Full runbook incl. Docker:
`fixtures/multimodal/DOCKER.md`.
