#!/usr/bin/env python3
"""Generate a long, realistic multi-module code-review prompt with a single
unique "needle" marker planted at a configurable depth (fraction of total
context length), for long-context retrieval evaluation.

This is an extension of ../../gen_256k_prompt.py generalized to:
  - target an arbitrary token budget (not just ~256K)
  - place the marker at an arbitrary fractional depth (0.0-1.0) instead of
    always at the midpoint
  - use a per-task marker module name / constant name / value, so multiple
    tasks can run independently without colliding on the same needle text
"""
from __future__ import annotations

import sys
from pathlib import Path

import tiktoken

enc = tiktoken.get_encoding("cl100k_base")


def toks(s: str) -> int:
    return len(enc.encode(s))


HEADER = """Perform an exhaustive, line-by-line code review of the following large multi-service e-commerce and logistics platform, spanning order processing, inventory, payments, shipping, search, recommendations, notifications, fraud detection, a distributed job scheduler, caching, rate limiting, audit logging, feature flags, an event bus, a saga orchestrator, and an internal LLM-agent tool-routing layer. Identify bugs, thread-safety issues, and performance problems as you go, but the most important instruction is below.

Deep inside this codebase, one configuration module contains a deliberately unusual constant used only for this review exercise: the value assigned to {const_name}. When you reach the end of your review, state that exact value verbatim as the very first line of your response (and nothing else on that line), before anything else, then proceed with a brief summary of the rest of the review below that line.

"""

FOOTER = """

Remember: the very first line of your response must be exactly the value of {const_name} found in {module_name} above, with no extra words, quotes, or punctuation around it. After that first line, give a short (2-3 sentence) summary of anything notable you saw in the code.
"""


def mod_job_scheduler(i):
    return f'''
### `job_scheduler_v{i}.py`

```python
"""Distributed job scheduler shard #{i} - assigns fulfillment jobs to regional workers."""

import time
import uuid
import threading
from enum import Enum


class JobState{i}(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RegionalScheduler{i}:
    def __init__(self, region_name, capacity_per_worker=8):
        self.region_name = region_name
        self.capacity_per_worker = capacity_per_worker
        self.jobs = {{}}
        self.workers = {{}}
        self.pending_queue = []
        self.lock = threading.Lock()

    def register_worker(self, worker_id, warehouse_ids):
        with self.lock:
            if worker_id not in self.workers:
                self.workers[worker_id] = {{
                    "warehouse_ids": warehouse_ids,
                    "current_load": 0,
                    "last_seen": time.time(),
                }}

    def submit_job(self, order_id, warehouse_id, sku_list, priority=0):
        job_id = str(uuid.uuid4())
        with self.lock:
            self.jobs[job_id] = {{
                "order_id": order_id,
                "warehouse_id": warehouse_id,
                "sku_list": sku_list,
                "priority": priority,
                "state": JobState{i}.PENDING,
            }}
            self.pending_queue.append(job_id)
        return job_id
```
'''


def mod_inventory(i):
    return f'''
### `inventory_service_v{i}.py`

```python
"""Inventory reservation service for warehouse cluster {i}."""

import threading
import time
from dataclasses import dataclass, field


@dataclass
class StockRecord{i}:
    sku: str
    warehouse_id: str
    on_hand: int
    reserved: int = 0
    updated_at: float = field(default_factory=time.time)

    @property
    def available(self):
        return self.on_hand - self.reserved


class InventoryService{i}:
    def __init__(self, shard_name):
        self.shard_name = shard_name
        self._stock = {{}}
        self._locks = {{}}

    def _get_lock(self, key):
        if key not in self._locks:
            self._locks[key] = threading.Lock()
        return self._locks[key]

    def reserve(self, sku, warehouse_id, quantity):
        key = f"{{sku}}:{{warehouse_id}}"
        lock = self._get_lock(key)
        with lock:
            rec = self._stock.get(key)
            if rec is None:
                return False
            if rec.available < quantity:
                return False
            rec.reserved += quantity
            return True
```
'''


def mod_payments(i):
    return f'''
### `payment_webhook_handler_v{i}.py`

```python
"""Payment provider webhook ingestion, shard {i}."""

import hashlib
import time
from dataclasses import dataclass


@dataclass
class WebhookEvent{i}:
    event_id: str
    order_id: str
    amount_cents: int
    provider: str
    received_at: float


class PaymentWebhookHandler{i}:
    def __init__(self, ledger, order_service):
        self.ledger = ledger
        self.order_service = order_service
        self._seen_recently = {{}}

    def _dedupe_key(self, event):
        raw = f"{{event.provider}}:{{event.order_id}}:{{event.amount_cents}}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def handle(self, event):
        key = self._dedupe_key(event)
        if key in self._seen_recently:
            return {{"status": "duplicate_ignored"}}
        self._seen_recently[key] = time.time()
        self.ledger.record_payment(event.order_id, event.amount_cents)
        self.order_service.mark_paid(event.order_id)
        return {{"status": "processed"}}
```
'''


def mod_search(i):
    return f'''
### `search_index_writer_v{i}.py`

```python
"""Incremental search index writer, catalog shard {i}."""


class SearchIndexWriter{i}:
    def __init__(self):
        self._documents = {{}}
        self._version = 0

    def index_document(self, doc_id, fields):
        self._documents[doc_id] = fields
        self._version += 1

    def delete_document(self, doc_id):
        self._documents.pop(doc_id, None)

    def search(self, query_terms):
        results = []
        for doc_id, fields in self._documents.items():
            text = " ".join(str(v) for v in fields.values()).lower()
            if all(term.lower() in text for term in query_terms):
                results.append(doc_id)
        return results
```
'''


def mod_notifications(i):
    return f'''
### `notification_dispatcher_v{i}.py`

```python
"""Customer notification dispatcher, channel group {i}."""

import time
import threading


class NotificationDispatcher{i}:
    def __init__(self, channel_clients):
        self.channel_clients = channel_clients
        self._delivery_log = []
        self._retry_queue = []
        self.lock = threading.Lock()

    def dispatch(self, user_id, channel, template_id, context):
        client = self.channel_clients.get(channel)
        if client is None:
            return False
        try:
            client.send(user_id, template_id, context)
            with self.lock:
                self._delivery_log.append({{
                    "user_id": user_id,
                    "channel": channel,
                    "sent_at": time.time(),
                }})
            return True
        except Exception as exc:
            with self.lock:
                self._retry_queue.append((user_id, channel, template_id, context, str(exc)))
            return False
```
'''


def mod_saga(i):
    return f'''
### `saga_orchestrator_v{i}.py`

```python
"""Saga orchestrator coordinating order fulfillment steps, group {i}."""

import uuid
from enum import Enum


class StepState{i}(Enum):
    PENDING = "pending"
    DONE = "done"
    COMPENSATING = "compensating"
    FAILED = "failed"


class SagaOrchestrator{i}:
    def __init__(self, steps, compensations):
        self.steps = steps
        self.compensations = compensations
        self.instances = {{}}

    def start(self, order_id, context):
        saga_id = str(uuid.uuid4())
        self.instances[saga_id] = {{
            "order_id": order_id,
            "context": context,
            "current_step": 0,
        }}
        return saga_id
```
'''


def mod_cache(i):
    return f'''
### `cache_layer_v{i}.py`

```python
"""LRU-ish caching layer, pool {i}."""

import time
import threading
from collections import OrderedDict


class CacheLayer{i}:
    def __init__(self, max_entries=10000, ttl_seconds=300):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._store = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key, value):
        with self.lock:
            self._store[key] = (value, time.time() + self.ttl_seconds)
            self._store.move_to_end(key)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)
```
'''


def mod_ratelimit(i):
    return f'''
### `rate_limiter_v{i}.py`

```python
"""Sliding-window rate limiter, tier {i}."""

import time
import threading
from collections import defaultdict, deque


class RateLimiter{i}:
    def __init__(self, max_requests, window_seconds):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, client_key):
        now = time.time()
        with self.lock:
            window = self._windows[client_key]
            while window and window[0] < now - self.window_seconds:
                window.popleft()
            if len(window) >= self.max_requests:
                return False
            window.append(now)
            return True
```
'''


def mod_audit(i):
    return f'''
### `audit_log_v{i}.py`

```python
"""Audit trail writer, service group {i}."""

import time
import json


class AuditLog{i}:
    def __init__(self, sink):
        self.sink = sink
        self._buffer = []
        self._flush_threshold = 500

    def record(self, actor, action, target, metadata=None):
        entry = {{
            "actor": actor,
            "action": action,
            "target": target,
            "metadata": metadata or {{}},
            "timestamp": time.time(),
        }}
        self._buffer.append(entry)
        if len(self._buffer) >= self._flush_threshold:
            self.flush()

    def flush(self):
        if not self._buffer:
            return
        payload = json.dumps(self._buffer)
        self.sink.write(payload)
```
'''


def mod_featureflags(i):
    return f'''
### `feature_flags_v{i}.py`

```python
"""Feature flag evaluation service, ruleset {i}."""

import hashlib


class FeatureFlags{i}:
    def __init__(self, definitions):
        self.definitions = definitions

    def is_enabled(self, flag_name, user_id):
        definition = self.definitions.get(flag_name)
        if definition is None:
            return False
        if not definition.get("enabled", False):
            return False
        rollout_pct = definition.get("rollout_pct", 0)
        if rollout_pct >= 100:
            return True
        if rollout_pct <= 0:
            return False
        bucket = int(hashlib.md5(f"{{flag_name}}:{{user_id}}".encode()).hexdigest(), 16) % 100
        return bucket < rollout_pct
```
'''


def mod_eventbus(i):
    return f'''
### `event_bus_v{i}.py`

```python
"""In-process event bus, partition {i}."""

import threading
from collections import defaultdict


class EventBus{i}:
    def __init__(self):
        self._subscribers = defaultdict(list)
        self._dead_letter = []
        self.lock = threading.Lock()

    def subscribe(self, event_type, handler):
        with self.lock:
            self._subscribers[event_type].append(handler)

    def publish(self, event_type, payload):
        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            try:
                handler(payload)
            except Exception as exc:
                self._dead_letter.append((event_type, payload, str(exc)))
```
'''


def mod_agenttools(i):
    return f'''
### `agent_tool_router_v{i}.py`

```python
"""Internal LLM-agent tool routing layer, toolset {i}."""

import time
import threading


class AgentToolRouter{i}:
    def __init__(self, max_concurrent_per_tool=2):
        self.max_concurrent_per_tool = max_concurrent_per_tool
        self._handlers = {{}}
        self._in_flight = {{}}
        self.lock = threading.Lock()

    def register_tool(self, name, handler):
        self._handlers[name] = handler
        self._in_flight[name] = 0

    def call(self, name, arguments):
        with self.lock:
            if name not in self._handlers:
                return {{"error": f"unknown tool: {{name}}"}}
            if self._in_flight[name] >= self.max_concurrent_per_tool:
                return {{"error": "tool concurrency limit reached"}}
            self._in_flight[name] += 1
        try:
            result = self._handlers[name](arguments)
            return {{"result": result}}
        finally:
            with self.lock:
                self._in_flight[name] = max(0, self._in_flight[name] - 1)
```
'''


GENERATORS = [
    mod_job_scheduler,
    mod_inventory,
    mod_payments,
    mod_search,
    mod_notifications,
    mod_saga,
    mod_cache,
    mod_ratelimit,
    mod_audit,
    mod_featureflags,
    mod_eventbus,
    mod_agenttools,
]


def marker_module(module_name: str, const_name: str, marker_value: str, note: str = "") -> str:
    note_line = f"\n\n# {note}" if note else ""
    return f'''
### `{module_name}`

```python
"""Internal diagnostics configuration - used only for review-harness
context verification. Not part of production request paths."""

{const_name} = "{marker_value}"{note_line}
```
'''


def build(
    target_tokens: int,
    position_pct: float,
    marker_value: str,
    module_name: str = "internal_diagnostics_config.py",
    const_name: str = "DEEP_CONTEXT_VERIFICATION_TOKEN",
    decoys: list[dict] | None = None,
) -> tuple[str, int, int]:
    """Build a prompt of ~target_tokens tokens with a single marker module
    (the one the model must report) inserted at approximately position_pct
    (0.0-1.0) through the generated body, plus optional decoy marker
    modules (each a dict with its own position_pct/module_name/const_name/
    marker_value) used by the distractor task to test whether the model
    reports the *correct* value rather than a similarly-shaped decoy found
    elsewhere in the context. Returns (text, actual_tokens, n_modules).
    """
    header = HEADER.format(const_name=const_name)
    footer = FOOTER.format(const_name=const_name, module_name=module_name)

    pending = [
        {
            "insert_at": int(target_tokens * position_pct),
            "block": marker_module(module_name, const_name, marker_value),
            "inserted": False,
        }
    ]
    for d in decoys or []:
        pending.append(
            {
                "insert_at": int(target_tokens * d["position_pct"]),
                "block": marker_module(
                    d.get("module_name", "config_shadow.py"),
                    d.get("const_name", const_name),
                    d["marker_value"],
                    note=d.get("note", ""),
                ),
                "inserted": False,
            }
        )

    parts = [header]
    cur = toks(header) + toks(footer)
    i = 0
    while cur < target_tokens:
        gen = GENERATORS[i % len(GENERATORS)]
        block = gen(i)
        block_tokens = toks(block)
        for p in pending:
            if not p["inserted"] and cur + block_tokens >= p["insert_at"]:
                parts.append(p["block"])
                cur += toks(p["block"])
                p["inserted"] = True
        parts.append(block)
        cur += block_tokens
        i += 1
    for p in pending:
        if not p["inserted"]:
            parts.append(p["block"])
            cur += toks(p["block"])
    parts.append(footer)
    text = "".join(parts)
    return text, toks(text), i


if __name__ == "__main__":
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 32000
    pct = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    value = sys.argv[3] if len(sys.argv) > 3 else "XK-TEST-0000"
    text, actual, n_modules = build(target, pct, value)
    sys.stderr.write(f"Generated {n_modules} modules, {actual} tokens (target {target}, pos {pct})\n")
    sys.stdout.write(text)
