# Running the multimodal eval in a Docker container

Step-by-step runbook for evaluating a vision-enabled `Qwen3.6-35B-A3B`
server from a container.

## What runs where

The container is an **eval client only** -- no model, no GPU, no CUDA:

```
 ┌───────────────────────────────┐        HTTP (base64 image payloads)
 │ Docker container              │  ────────────────────────────────────►
 │  check.py / variance_report   │                                  ┌──────────────────────────┐
 │  dashboard.py                 │  ◄────────────────────────────────  FreeToken on 192.168.0.88
 │  reads media from /data/media │        JSON chat completions     │  Qwen3.6-35B-A3B FP8     │
 └───────────────────────────────┘                                  │  vision tower enabled    │
                                                                    └──────────────────────────┘
```

Images are sent **inline as base64 `data:` URLs**, never as `file://`
paths. This is what makes containerisation work at all: the server
resolves `file://` against its own filesystem, so a container-local path
would be meaningless to it. The consequence is that image bytes travel
over the wire on every request, so keep the container on the same LAN as
the server.

## Prerequisites

1. **A vision-enabled server.** The engine must be started *without*
   `--text-model-only` and with `--allowed-local-media-path`. Confirm the
   vision tower actually loaded:

   ```bash
   curl -s http://192.168.0.88:8000/v1/models | python3 -m json.tool | head -20
   grep -i "Multimodal enabled" ~/.local/state/freetoken/logs/serve-*.log
   ```

   You want a line naming the processor and encoders, e.g.
   `Multimodal enabled: QwenVLMMProcessor, encoders ['vision'] on host, serving ['image']`.
   If vision is off, every item fails and the numbers are meaningless.

2. **Staged media.** Media lives outside git. On the dataset host:

   ```
   /mnt/data/qwen36-mm-eval/media/
     smoke/images/*.png        # synthetic smoke set (16 items)
     mmmu/<Subject>/*.png      # extracted MMMU images (60-item subset)
   ```

   If you do not have it yet, generate it from the MMMU snapshot (see
   "Regenerating the MMMU subset" below).

3. **Docker**, and network reachability from the container to the server.

## Build

Build from the **repository root** -- the Dockerfile expects the suite in
its build context:

```bash
cd /path/to/llm-tests
docker build -f qualbench/fixtures/multimodal/Dockerfile -t qualbench-mm .
```

## Step 1 -- smoke test the wiring

Always run the 16-item synthetic suite first. It is fast (~1-3 min), and
its ground truth is exact by construction, so any failure points at the
setup rather than at the model.

```bash
docker run --rm \
  -v /mnt/data/qwen36-mm-eval/media:/data/media:ro \
  -v "$PWD/mm-results:/out" \
  qualbench-mm \
    --all --suite smoke \
    --url http://192.168.0.88:8000 \
    --model qwen3.6-35b-a3b \
    --emit-artifacts \
    --records-out /out/smoke.jsonl
```

Expect one `[PASS]`/`[FAIL]` line per visual domain:

```
[PASS] charts (66.8s)
[PASS] ocr (18.0s)
[PASS] counting (64.3s)
[PASS] spatial (23.9s)
  suite=smoke items=16 accuracy=87.5% strict=87.5% domain-range=50.0%
```

If instead you see `setup error: missing media for item ...`, the volume
mount or `QUALBENCH_MM_MEDIA_ROOT` is wrong -- note that the suite reports
this as a *setup* error and fails the bucket explicitly rather than
scoring it as a wrong answer.

## Step 2 -- run the MMMU subset

60 real MMMU validation items, stratified across charts / photos /
diagrams / screen-captures. This takes considerably longer (real MMMU
figures are large and the questions need real reasoning):

```bash
docker run --rm \
  -v /mnt/data/qwen36-mm-eval/media:/data/media:ro \
  -v "$PWD/mm-results:/out" \
  qualbench-mm \
    --all --suite mmmu-subset \
    --url http://192.168.0.88:8000 \
    --model qwen3.6-35b-a3b \
    --timeout 300 \
    --emit-artifacts \
    --records-out /out/mmmu-run1.jsonl
```

**Expected runtime.** Real MMMU charts and diagrams can consume ~10k
reasoning tokens before the model commits to an answer, which at the
observed ~75 tok/s is 1-3 minutes *per item*. The 60-item subset
therefore takes on the order of 1-2 hours. Progress is printed per item
to **stderr** (stdout is parsed by `run_all.py`, so it must stay clean),
so pipe stderr somewhere visible if you want to watch it:

```bash
docker run ... qualbench-mm --all --suite mmmu-subset ... 2>&1 | tee run.log
```

Useful flags while iterating:

| Flag | Why |
|---|---|
| `--limit 2` | Two items per domain -- fast end-to-end check of a new manifest |
| `charts` (positional) | Run a single domain instead of `--all` |
| `--show-response` | Print the model's raw reply, for debugging extraction |
| `--max-tokens 32768` | Raise if you still see `truncated: finish_reason=length` |

## Step 3 -- variance report (model output vs ground truth)

```bash
docker run --rm \
  -v "$PWD/mm-results:/out" \
  --entrypoint python qualbench-mm \
  variance_report.py /out/mmmu-run1.jsonl --json /out/variance.json
```

This is the tool to read when a bucket is red. It separates the
categories of failure that are routinely conflated:

* **wrong answers** -- actual reasoning errors;
* **truncated generations** -- the model ran out of token budget
  mid-analysis (raise `--max-tokens`); not a reasoning error;
* **media/staging errors** -- your environment, not the model;
* **formatting slack** -- answers that needed normalization or numeric
  tolerance to be credited. A large gap between `accuracy` and
  `strict_accuracy` means the model is right but formats badly, which is a
  very different problem from being wrong.

It also reports accuracy against the **random-chance floor** implied by
the option counts. On multiple-choice sets this matters: a 30% score on
4-option items is not "weak", it is indistinguishable from guessing.

## Step 4 -- run it again, then measure stability

A single run's headline number includes run-to-run noise. Quantify it
before drawing conclusions:

```bash
# second run, same suite
docker run --rm -v /mnt/data/qwen36-mm-eval/media:/data/media:ro \
  -v "$PWD/mm-results:/out" qualbench-mm \
  --all --suite mmmu-subset --url http://192.168.0.88:8000 \
  --records-out /out/mmmu-run2.jsonl

# compare
docker run --rm -v "$PWD/mm-results:/out" \
  --entrypoint python qualbench-mm \
  variance_report.py /out/mmmu-run1.jsonl /out/mmmu-run2.jsonl
```

The report then lists which items *flipped* between runs and the per-run
accuracy spread. Differences smaller than that spread are noise. (The
text categories of this suite have a documented ~10-30% nondeterminism on
this FP8 build even at temperature 0, so this is not a hypothetical
concern.)

## Step 5 -- dashboard

```bash
docker run --rm -v "$PWD/mm-results:/out" \
  --entrypoint python qualbench-mm \
  dashboard.py /out/mmmu-run1.jsonl /out/mmmu-run2.jsonl \
    -o /out/dashboard.md --html /out/dashboard.html
```

Produces per-domain accuracy with the suite's pass thresholds, the domain
spread, stability, failing-item detail, and a comparison against published
benchmark numbers read from `public_benchmarks.json`.

**On that comparison:** the file ships with *unsourced placeholders*, and
the dashboard marks them `UNVERIFIED`. Fill in real figures yourself --
each entry requires a `source` URL and an `as_of` date. And keep the
caveat in mind: this suite scores a 60-item subset with its own prompt and
answer parser, while published MMMU numbers use the full 900-item
validation split and the official harness. The comparison is a sanity
check on whether local vision is roughly where it should be, **not** a
leaderboard claim.

## docker compose

```yaml
services:
  qualbench-mm:
    build:
      context: ../../..
      dockerfile: qualbench/fixtures/multimodal/Dockerfile
    volumes:
      - /mnt/data/qwen36-mm-eval/media:/data/media:ro
      - ./mm-results:/out
    environment:
      QUALBENCH_MM_MEDIA_ROOT: /data/media
    command: >
      --all --suite smoke
      --url http://192.168.0.88:8000
      --model qwen3.6-35b-a3b
      --emit-artifacts
      --records-out /out/smoke.jsonl
```

```bash
docker compose run --rm qualbench-mm
```

## Regenerating the MMMU subset

Run this **on the host holding the MMMU snapshot**, not in the client
container -- it needs `pyarrow` and writes ~19 MB of extracted images:

```bash
python3 prep_mmmu.py \
  --mmmu-root  /mnt/data/qwen36-mm-eval/raw/MMMU-hf \
  --media-root /mnt/data/qwen36-mm-eval/media \
  --out        manifests/mmmu-subset.jsonl
```

Add `--dry-run` to preview the selection without writing. Sampling is
seeded (`--seed`), stratified by visual domain, and round-robins across
MMMU subjects so no single subject dominates a bucket. Only the
`validation` split is used, because it is the only split whose answers are
public and therefore locally gradeable.

The generated **manifest is committed to git** (it is small and defines
exactly what was evaluated); the **images are not** (too large, and
redistributable only from the original dataset).

## Adding video items

Video support is in place but **no video media is staged yet** -- only the
Video-MME annotations are present locally. The plumbing works like this:

* a manifest item carries `"video": "<path>"` and `"domain": "video"`;
* `check.py --video-frames N` samples N frames via `ffmpeg` (midpoints of
  N equal slices, which avoids grabbing a black first frame) and sends
  them as inline images;
* `ffmpeg` is already installed in this image.

Until clips are staged, video items fail with an explicit
`media/staging error`, which the variance report counts separately from
model failures rather than silently depressing accuracy.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| every item fails, model describes nothing | Vision not enabled -- server still has `--text-model-only`. Re-check the serve log. |
| `setup error: missing media for item ...` | Volume mount or `QUALBENCH_MM_MEDIA_ROOT` wrong. The error lists every missing path. |
| `truncated: finish_reason=length` | Reasoning ran past the budget. Default is 16384, measured to be enough for real MMMU charts/diagrams on this model; raise further only if truncations persist. Reported as a truncation, never as a wrong answer. |
| `requested model '...' not advertised` | Model id mismatch; list them with `curl .../v1/models`. |
| `Connection refused` from the container | Server not reachable from the container network. Use the LAN IP, not `127.0.0.1` -- inside a container that is the container itself. |
| accuracy near the chance floor | The variance report prints the floor. At-chance accuracy means no signal, not merely weak performance. |

## Running via the unified qualbench runner

The category is registered as `multimodal` but is **opt-in**: it is
excluded from the default run so it cannot silently alter the 50-task
text-only baseline that every historical result is measured against.
Request it explicitly:

```bash
QUALBENCH_MM_MEDIA_ROOT=/mnt/data/qwen36-mm-eval/media \
QUALBENCH_MM_SUITE=mmmu-subset \
python3 qualbench/harness/run_all.py \
  --url http://192.168.0.88:8000 \
  --model qwen3.6-35b-a3b \
  --tag mm-mmmu \
  --categories multimodal
```
