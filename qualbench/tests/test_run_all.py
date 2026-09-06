from __future__ import annotations

import subprocess

import pytest

from qualbench.harness import run_all


def test_parse_reason_line() -> None:
    assert run_all.parse_reason_line("    - failed schema validation") == "failed schema validation"
    assert run_all.parse_reason_line("    request failed: timeout") == "request failed: timeout"
    assert run_all.parse_reason_line("not indented") is None


def test_run_category_parses_reasons_and_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = "\n".join(
        [
            "[PASS] 01-alpha (0.4s)",
            "    - first reason",
            "[ARTIFACT] 01-alpha {\"candidate\": \"ok\"}",
            "[FAIL] 02-beta (1.0s)",
            "    second reason",
            "[ARTIFACT] 02-beta {\"error\": \"bad output\"}",
            "diagnostic line",
        ]
    )

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, stdout=stdout, stderr="")

    monkeypatch.setattr(run_all.subprocess, "run", fake_run)

    result = run_all.run_category(
        "mcp-tools",
        run_all.CATEGORIES["mcp-tools"],
        "http://127.0.0.1:8000",
        "qwen3.6-35b-a3b",
        None,
    )

    assert calls
    assert "--emit-artifacts" in calls[0]
    assert result["n_total"] == 2
    assert result["artifact_count"] == 2

    t1 = result["tasks"][0]
    assert t1["id"] == "01-alpha"
    assert t1["reasons"] == ["first reason"]
    assert t1["artifact"] == {"candidate": "ok"}

    t2 = result["tasks"][1]
    assert t2["id"] == "02-beta"
    assert t2["reasons"] == ["second reason"]
    assert t2["artifact"] == {"error": "bad output"}

    assert result["logs"] == ["diagnostic line"]


def test_preflight_server_requires_requested_model(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "data": [
                    {"id": "different-model"},
                ]
            }

    monkeypatch.setattr(run_all.requests, "get", lambda url, timeout: FakeResponse())

    with pytest.raises(RuntimeError, match="requested model"):
        run_all.preflight_server("http://127.0.0.1:8000", "qwen3.6-35b-a3b", 5.0)


def test_render_markdown_includes_task_reasons() -> None:
    report = {
        "tag": "sample",
        "url": "http://127.0.0.1:8000",
        "model": "qwen3.6-35b-a3b",
        "notes": "offline test",
        "selected_categories": ["mcp-tools"],
        "suite_git_commit": "abc123",
        "suite_git_dirty": False,
        "preflight": {
            "requested_model_found": True,
            "selected_model_entry": {"max_model_len": 262144},
        },
        "started_at": "2026-09-05T00:00:00+00:00",
        "finished_at": "2026-09-05T00:01:00+00:00",
        "total_wall_s": 60.0,
        "total_pass": 0,
        "total_tasks": 1,
        "categories": [
            {
                "category": "mcp-tools",
                "n_pass": 0,
                "n_total": 1,
                "wall_s": 60.0,
                "returncode": 1,
                "timed_out": False,
                "tasks": [
                    {
                        "id": "06-missing-info-no-premature-call",
                        "passed": False,
                        "elapsed_s": 2.3,
                        "reasons": ["expected no tool call"],
                    }
                ],
            }
        ],
    }

    markdown = run_all.render_markdown(report)
    assert "expected no tool call" in markdown
    assert "Preflight: requested model present" in markdown
