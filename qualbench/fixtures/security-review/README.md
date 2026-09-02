# Security / Code-Review fixtures

8 tasks, each presenting a short, realistic code snippet with exactly one
deliberately planted security defect. The model is asked to review the
code and identify security issues. Grading checks whether the model's
free-text response correctly names/describes the specific planted defect
(recall), via deterministic regex matching -- no LLM-judge needed, since
each defect has a small, well-known vocabulary of terms a competent
reviewer would use to describe it.

Each task directory contains:

- `code.txt` -- the vulnerable snippet (language noted in a comment).
- `prompt.txt` -- the exact user message sent along with the code.
- `expected.json` -- grading rules (see below).
- `README.md` -- what's actually wrong, for humans maintaining the suite.

## expected.json format

```json
{
  "required_pattern_groups": [
    ["regex1", "regex2"],   // at least ONE of these must match (case-insensitive) -- e.g. multiple ways to name the same defect
    ["regex3"]              // a second, independent thing that must also be mentioned
  ],
  "min_groups_matched": 2   // how many of the groups above must be satisfied to PASS (defaults to len(groups), i.e. all)
}
```

## Running

```bash
python3 check.py <task-dir> --url http://127.0.0.1:8000 --model qwen3.6-35b-a3b
python3 check.py --all --url http://127.0.0.1:8000 --model qwen3.6-35b-a3b
```
