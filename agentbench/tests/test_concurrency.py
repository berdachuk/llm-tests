"""Concurrency tests.

The server is assumed to be configured with a small, finite
`--max-running-requests` limit (default assumption: 4; override via
$AGENTBENCH_MAX_RUNNING_REQUESTS -- see settings.py) rather than
single-flight, so it can serve a few agent sessions / IDE users at once from
one GPU. These tests verify that concurrent requests:

  * All complete successfully (no request silently dropped or corrupted by
    interleaving with others in the batch).
  * Don't cross-contaminate content between sessions (a real risk with
    shared KV/MoE-offload caches under concurrency bugs).
  * A 5th request beyond the running-request limit queues and eventually
    completes rather than erroring out.

Opt-in via `--run-concurrency` since this deliberately saturates the shared
GPU and will slow down anything else running against it.
"""

from __future__ import annotations

import concurrent.futures as cf

import pytest

from agentbench.client import AgentBenchClient

pytestmark = pytest.mark.concurrency


class TestParallelRequestsDoNotCrossContaminate:
    def test_four_parallel_requests_each_get_their_own_answer(self, agent_url, agent_model, agent_timeout):
        # Each worker gets its own client/session -- concurrency bugs in a
        # shared requests.Session or connection pool are a real, distinct
        # failure mode from server-side interleaving bugs.
        questions = [
            ("What is the capital of France? Answer with just the city name.", "Paris"),
            ("What is the capital of Japan? Answer with just the city name.", "Tokyo"),
            ("What is the capital of Egypt? Answer with just the city name.", "Cairo"),
            ("What is the capital of Brazil? Answer with just the city name.", "Brasília"),
        ]

        def run(q_and_a):
            question, _ = q_and_a
            c = AgentBenchClient(agent_url, agent_model, timeout=agent_timeout)
            return c.chat_completions(
                messages=[{"role": "user", "content": question}],
                max_tokens=60,
                reasoning_effort="none",
            )

        with cf.ThreadPoolExecutor(max_workers=len(questions)) as ex:
            results = list(ex.map(run, questions))

        for (_, expected_city), result in zip(questions, results):
            assert result.content.strip(), (
                f"empty response under concurrency (reasoning_content={result.reasoning_content!r})"
            )
            assert expected_city.split()[0][:4].lower() in result.content.lower(), (
                f"expected {expected_city!r} in response but got {result.content!r} "
                f"-- possible cross-contamination between concurrent requests"
            )

    def test_streaming_requests_do_not_interleave_content(self, agent_url, agent_model, agent_timeout):
        """Streaming is the highest-risk path for cross-contamination: if
        per-request SSE buffers are shared/mixed up, tokens from one
        session's stream can leak into another's."""
        prompts = [
            "Repeat this exact phrase five times: BANANA-ALPHA",
            "Repeat this exact phrase five times: KIWI-BETA",
            "Repeat this exact phrase five times: MANGO-GAMMA",
        ]

        def run(prompt):
            c = AgentBenchClient(agent_url, agent_model, timeout=agent_timeout)
            return prompt, c.chat_completions(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                stream=True,
                reasoning_effort="none",
            )

        with cf.ThreadPoolExecutor(max_workers=len(prompts)) as ex:
            results = list(ex.map(run, prompts))

        for prompt, result in results:
            expected_phrase = prompt.rsplit(": ", 1)[1]
            assert expected_phrase in result.content, (
                f"stream for prompt {prompt!r} did not contain its own phrase "
                f"{expected_phrase!r}; got {result.content!r} -- possible stream cross-talk"
            )


class TestOverCapacityRequestQueuesRatherThanErrors:
    def test_more_requests_than_max_running_still_all_succeed(
        self, agent_url, agent_model, agent_timeout, agent_over_capacity_request_count
    ):
        """Send more concurrent requests than the server's configured
        --max-running-requests ($AGENTBENCH_MAX_RUNNING_REQUESTS). Extras
        must queue behind admission control and eventually complete, not
        error out with 503/429/connection-reset."""
        n = agent_over_capacity_request_count

        def run(i):
            c = AgentBenchClient(agent_url, agent_model, timeout=agent_timeout)
            return c.chat_completions(
                messages=[{"role": "user", "content": f"Reply with exactly: request-{i}-ok"}],
                max_tokens=50,
                reasoning_effort="none",
            )

        with cf.ThreadPoolExecutor(max_workers=n) as ex:
            futures = [ex.submit(run, i) for i in range(n)]
            results = [f.result() for f in futures]

        for i, result in enumerate(results):
            assert f"request-{i}-ok" in result.content, (
                f"request {i} did not complete correctly under over-capacity load: {result.content!r}"
            )
