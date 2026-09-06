from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from qualbench.harness import run_all


def build_mock_completion(payload: dict) -> dict:
    messages = payload.get("messages") or []
    text_parts: list[str] = []
    for msg in messages:
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            text_parts.append(msg["content"])
    text = "\n".join(text_parts)

    def tool_call(name: str, arguments: dict) -> dict:
        return {
            "id": "call_mock_1",
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(arguments),
            },
        }

    if "weather like in Tokyo" in text:
        message = {
            "role": "assistant",
            "tool_calls": [tool_call("get_weather", {"city": "Tokyo", "unit": "fahrenheit"})],
        }
        finish_reason = "tool_calls"
    elif "production database is completely down" in text:
        message = {
            "role": "assistant",
            "tool_calls": [
                tool_call("create_ticket", {"title": "Prod outage: checkout down", "priority": "urgent"})
            ],
        }
        finish_reason = "tool_calls"
    elif "costs $49.99" in text:
        message = {
            "role": "assistant",
            "tool_calls": [tool_call("apply_discount", {"amount_cents": 4999, "discount_rate": 0.15})],
        }
        finish_reason = "tool_calls"
    elif "Maria Gonzalez" in text and "Rue de Rivoli" in text:
        message = {
            "role": "assistant",
            "tool_calls": [
                tool_call(
                    "create_shipping_label",
                    {
                        "recipient_name": "Maria Gonzalez",
                        "address": {
                            "street": "42 Rue de Rivoli",
                            "city": "Paris",
                            "postal_code": "75004",
                            "country": "France",
                        },
                    },
                )
            ],
        }
        finish_reason = "tool_calls"
    elif "Q3 Planning" in text and "2026-09-10T14:00:00Z" in text:
        message = {
            "role": "assistant",
            "tool_calls": [
                tool_call(
                    "create_calendar_event",
                    {"title": "Q3 Planning", "start_time": "2026-09-10T14:00:00Z"},
                )
            ],
        }
        finish_reason = "tool_calls"
    elif "Please send $50 to my friend Jake" in text:
        message = {
            "role": "assistant",
            "content": "I need Jake's recipient account id before I can call transfer_money.",
        }
        finish_reason = "stop"
    elif "jake.holloway@example.com" in text and "refund me $30" in text:
        message = {
            "role": "assistant",
            "tool_calls": [tool_call("issue_refund", {"customer_id": "CUST-88213", "amount_cents": 3000})],
        }
        finish_reason = "tool_calls"
    elif "meeting MTG-77" in text:
        message = {
            "role": "assistant",
            "tool_calls": [
                tool_call(
                    "invite_to_meeting",
                    {
                        "meeting_id": "MTG-77",
                        "attendee_emails": [
                            "alice@corp.com",
                            "bob@corp.com",
                            "carla@corp.com",
                        ],
                    },
                )
            ],
        }
        finish_reason = "tool_calls"
    else:
        message = {
            "role": "assistant",
            "content": "Unhandled prompt in mock server",
        }
        finish_reason = "stop"

    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 0,
        "model": payload.get("model", "qwen3.6-35b-a3b"),
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
    }


def make_handler(model_id: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return None

        def _send_json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/v1/models":
                self._send_json(404, {"error": "not found"})
                return
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": model_id,
                            "object": "model",
                            "max_model_len": 262144,
                        }
                    ],
                },
            )

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/chat/completions":
                self._send_json(404, {"error": "not found"})
                return
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            payload = json.loads(raw.decode("utf-8"))
            self._send_json(200, build_mock_completion(payload))

    return Handler


def test_run_all_mcp_tools_offline_smoke(tmp_path: Path, monkeypatch) -> None:
    model_id = "qwen3.6-35b-a3b"
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(model_id))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        results_dir = tmp_path / "results"
        monkeypatch.setattr(run_all, "RESULTS", results_dir)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "run_all.py",
                "--tag",
                "ci-offline",
                "--url",
                f"http://127.0.0.1:{server.server_port}",
                "--model",
                model_id,
                "--categories",
                "mcp-tools",
                "--timeout",
                "5",
                "--notes",
                "offline integration smoke",
            ],
        )

        rc = run_all.main()
        assert rc == 0

        report_files = sorted(results_dir.glob("run-ci-offline-*.json"))
        assert len(report_files) == 1
        report = json.loads(report_files[0].read_text())

        assert report["total_pass"] == 8
        assert report["total_tasks"] == 8
        assert report["preflight"]["requested_model_found"] is True

        category = report["categories"][0]
        assert category["category"] == "mcp-tools"
        assert category["n_pass"] == 8
        assert category["n_total"] == 8
        assert category["artifact_count"] == 8
        assert all("artifact" in task for task in category["tasks"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
