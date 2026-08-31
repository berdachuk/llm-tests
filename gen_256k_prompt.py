#!/usr/bin/env python3
"""Generate a large multi-module code-review prompt targeting ~256K tokens
(cl100k_base tokenizer, matching statistical_llm_tester.py's tokenizer)."""
import sys
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

def toks(s):
    return len(enc.encode(s))

HEADER = """Perform an exhaustive, line-by-line code review of the following large multi-service e-commerce and logistics platform, spanning order processing, inventory, payments, shipping, search, recommendations, notifications, fraud detection, a distributed job scheduler, caching, rate limiting, audit logging, feature flags, an event bus, a saga orchestrator, and an internal LLM-agent tool-routing layer. Identify every bug, thread-safety issue, performance problem, and API design flaw you can find across all modules, then provide a prioritized list of the ten most severe issues at the end of your response, followed by a bullet-point changelog explaining the top fixes and why they matter most.

Treat this as a real production incident review: assume this codebase currently powers a platform processing several million orders per day across hundreds of regional warehouses, and has recently started exhibiting intermittent duplicate order fulfillment, inventory counts drifting negative under high concurrency, payment webhooks being processed twice, search index staleness after bulk catalog updates, and a slow memory leak in the notification dispatcher. Your review must explain plausible root causes for these symptoms, grounded in specific lines of the code below, not generic advice.

Deep inside this codebase, one configuration module contains a deliberately unusual constant used only for this review exercise: the value assigned to DEEP_CONTEXT_VERIFICATION_TOKEN. When you reach the end of your review, state that exact token value verbatim as the very first line of your response, before anything else, then proceed with the rest of the review below that line.

"""

MARKER_MODULE_NAME = "internal_diagnostics_config.py"
MARKER_VALUE = "XK-7734-QRTZ-9182-CODINGCTX"

FOOTER = """

CORRECTED IMPLEMENTATION REQUIREMENTS:

Provide your consolidated findings covering:
- Every race condition across the order, inventory, and payment-webhook modules that could cause duplicate fulfillment or double-charging, with the exact lines involved
- Every unbounded in-memory collection across the notification, audit-log, and event-bus modules that could explain a slow multi-day memory leak
- Whether the search-index writer's incremental update path can miss documents during a concurrent bulk catalog import, and why
- Whether the inventory reservation logic can go negative under concurrent reservations from multiple warehouses fulfilling the same SKU
- Whether the payment webhook handler is idempotent against provider retries, and if not, the exact missing guard
- A short usage example wiring the OrderService, InventoryService, PaymentWebhookHandler, SearchIndexWriter, and SagaOrchestrator together correctly
- At least one concurrency stress-test sketch that would have caught the inventory-negative-count bug

Remember: the very first line of your response must be the exact value of DEEP_CONTEXT_VERIFICATION_TOKEN found in internal_diagnostics_config.py above.
"""

# A pool of domain module templates. Each is a function that returns
# a distinct, realistic-looking Python module as a string given an index.
def mod_job_scheduler(i):
    return f'''
### `job_scheduler_v{i}.py`

```python
"""Distributed job scheduler shard #{i} - assigns fulfillment jobs to regional workers."""

import time
import uuid
import threading
from enum import Enum
from collections import defaultdict


class JobState{i}(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FulfillmentJob{i}:
    def __init__(self, order_id, warehouse_id, sku_list, priority=0):
        self.id = str(uuid.uuid4())
        self.order_id = order_id
        self.warehouse_id = warehouse_id
        self.sku_list = sku_list
        self.priority = priority
        self.state = JobState{i}.PENDING
        self.attempts = 0
        self.max_attempts = 3
        self.assigned_worker = None
        self.created_at = time.time()
        self.updated_at = time.time()
        self.history = []

    def transition(self, new_state):
        self.history.append((self.state, new_state, time.time()))
        self.state = new_state
        self.updated_at = time.time()


class RegionalScheduler{i}:
    """Assigns fulfillment jobs to warehouse workers within region {i}."""

    def __init__(self, region_name, capacity_per_worker=8):
        self.region_name = region_name
        self.capacity_per_worker = capacity_per_worker
        self.jobs = {{}}
        self.workers = {{}}
        self.pending_queue = []
        self.lock = threading.Lock()
        self._completed_log = []  # retained for audit; never trimmed

    def register_worker(self, worker_id, warehouse_ids):
        with self.lock:
            if worker_id not in self.workers:
                self.workers[worker_id] = {{
                    "warehouse_ids": warehouse_ids,
                    "current_load": 0,
                    "last_seen": time.time(),
                }}

    def submit_job(self, order_id, warehouse_id, sku_list, priority=0):
        job = FulfillmentJob{i}(order_id, warehouse_id, sku_list, priority)
        with self.lock:
            self.jobs[job.id] = job
            self.pending_queue.append(job.id)
        return job.id

    def assign_next_batch(self):
        assigned = []
        # NOTE: reads pending_queue without holding the lock across the
        # whole loop body, only per-item -- a job can be picked twice if
        # this method is invoked concurrently from two scheduler ticks.
        for job_id in list(self.pending_queue):
            job = self.jobs.get(job_id)
            if job is None or job.state != JobState{i}.PENDING:
                continue
            candidate = self._pick_worker(job.warehouse_id)
            if candidate is None:
                continue
            with self.lock:
                job.assigned_worker = candidate
                job.transition(JobState{i}.ASSIGNED)
                self.workers[candidate]["current_load"] += 1
                if job_id in self.pending_queue:
                    self.pending_queue.remove(job_id)
            assigned.append(job_id)
        return assigned

    def _pick_worker(self, warehouse_id):
        best = None
        best_load = None
        for worker_id, info in self.workers.items():
            if warehouse_id not in info["warehouse_ids"]:
                continue
            if info["current_load"] >= self.capacity_per_worker:
                continue
            if best_load is None or info["current_load"] < best_load:
                best = worker_id
                best_load = info["current_load"]
        return best

    def mark_completed(self, job_id, result=None):
        job = self.jobs.get(job_id)
        if job is None:
            return False
        job.transition(JobState{i}.COMPLETED)
        self._completed_log.append(job)  # unbounded growth over time
        if job.assigned_worker in self.workers:
            self.workers[job.assigned_worker]["current_load"] = max(
                0, self.workers[job.assigned_worker]["current_load"] - 1
            )
        return True
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
from typing import Dict, List


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
    """Tracks stock levels and reservations for a shard of SKUs."""

    def __init__(self, shard_name):
        self.shard_name = shard_name
        self._stock: Dict[str, StockRecord{i}] = {{}}
        self._locks: Dict[str, threading.Lock] = {{}}

    def _get_lock(self, key):
        # Lazily created per-SKU lock, but the dict itself isn't
        # protected, so two threads creating a lock for the same new
        # SKU simultaneously can end up using two different lock
        # objects, defeating mutual exclusion entirely.
        if key not in self._locks:
            self._locks[key] = threading.Lock()
        return self._locks[key]

    def upsert_stock(self, sku, warehouse_id, on_hand):
        key = f"{{sku}}:{{warehouse_id}}"
        rec = self._stock.get(key)
        if rec is None:
            self._stock[key] = StockRecord{i}(sku, warehouse_id, on_hand)
        else:
            rec.on_hand = on_hand
            rec.updated_at = time.time()

    def reserve(self, sku, warehouse_id, quantity):
        key = f"{{sku}}:{{warehouse_id}}"
        lock = self._get_lock(key)
        with lock:
            rec = self._stock.get(key)
            if rec is None:
                return False
            # Check-then-act on `available`, but `available` is a computed
            # property re-read from `on_hand`/`reserved` fields that could
            # be mutated by upsert_stock() from another thread not holding
            # this same per-key lock (upsert_stock takes no lock at all).
            if rec.available < quantity:
                return False
            rec.reserved += quantity
            return True

    def release(self, sku, warehouse_id, quantity):
        key = f"{{sku}}:{{warehouse_id}}"
        lock = self._get_lock(key)
        with lock:
            rec = self._stock.get(key)
            if rec is None:
                return False
            rec.reserved = max(0, rec.reserved - quantity)
            return True

    def commit_fulfillment(self, sku, warehouse_id, quantity):
        key = f"{{sku}}:{{warehouse_id}}"
        lock = self._get_lock(key)
        with lock:
            rec = self._stock.get(key)
            if rec is None:
                return False
            rec.on_hand -= quantity
            rec.reserved = max(0, rec.reserved - quantity)
            return True

    def bulk_snapshot(self) -> List[StockRecord{i}]:
        # Iterates the dict without a global lock while other threads may
        # be inserting new keys via upsert_stock -- RuntimeError under
        # concurrent mutation is possible during a bulk catalog import.
        return list(self._stock.values())
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
    """Processes payment-confirmed webhooks from an external provider."""

    def __init__(self, ledger, order_service):
        self.ledger = ledger
        self.order_service = order_service
        self._seen_recently = {{}}  # event_id -> timestamp, never pruned
        self._retention_seconds = 3600

    def _dedupe_key(self, event: WebhookEvent{i}):
        raw = f"{{event.provider}}:{{event.order_id}}:{{event.amount_cents}}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def handle(self, event: WebhookEvent{i}):
        key = self._dedupe_key(event)
        # Idempotency check races: two webhook deliveries for the same
        # event arriving concurrently can both pass this check before
        # either has recorded `key` in `_seen_recently`.
        if key in self._seen_recently:
            return {{"status": "duplicate_ignored"}}
        self._seen_recently[key] = time.time()
        self.ledger.record_payment(event.order_id, event.amount_cents)
        self.order_service.mark_paid(event.order_id)
        return {{"status": "processed"}}

    def prune_seen(self):
        # Exists but is never called anywhere in the service's main loop,
        # so `_seen_recently` grows without bound in a long-running process.
        cutoff = time.time() - self._retention_seconds
        stale = [k for k, t in self._seen_recently.items() if t < cutoff]
        for k in stale:
            del self._seen_recently[k]
```
'''

def mod_search(i):
    return f'''
### `search_index_writer_v{i}.py`

```python
"""Incremental search index writer, catalog shard {i}."""

import threading
import time


class SearchIndexWriter{i}:
    def __init__(self):
        self._documents = {{}}
        self._pending_deletes = set()
        self._version = 0
        self._bulk_import_in_progress = False

    def index_document(self, doc_id, fields):
        # If a bulk import is in progress, this incremental update writes
        # directly into `_documents`, but `begin_bulk_import` below
        # replaces `_documents` wholesale on completion, silently
        # dropping any documents indexed here mid-import.
        self._documents[doc_id] = fields
        self._version += 1

    def delete_document(self, doc_id):
        self._pending_deletes.add(doc_id)
        self._documents.pop(doc_id, None)

    def begin_bulk_import(self, all_documents: dict):
        self._bulk_import_in_progress = True
        self._staging = dict(all_documents)

    def commit_bulk_import(self):
        # Wholesale replacement: any `index_document()` calls that landed
        # in `self._documents` between `begin_bulk_import` and this commit
        # are lost, since `_staging` was snapshotted at `begin_bulk_import`
        # time and does not include them.
        self._documents = self._staging
        self._bulk_import_in_progress = False
        self._version += 1

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
        self._delivery_log = []  # append-only, never trimmed or rotated
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
                    "template_id": template_id,
                    "sent_at": time.time(),
                    "context_snapshot": dict(context),
                }})
            return True
        except Exception as exc:
            with self.lock:
                self._retry_queue.append((user_id, channel, template_id, context, str(exc)))
            return False

    def process_retries(self, max_batch=50):
        with self.lock:
            batch = self._retry_queue[:max_batch]
            self._retry_queue = self._retry_queue[max_batch:]
        for user_id, channel, template_id, context, _ in batch:
            self.dispatch(user_id, channel, template_id, context)
```
'''

def mod_saga(i):
    return f'''
### `saga_orchestrator_v{i}.py`

```python
"""Saga orchestrator coordinating order fulfillment steps, group {i}."""

import time
import uuid
from enum import Enum


class StepState{i}(Enum):
    PENDING = "pending"
    DONE = "done"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


class SagaOrchestrator{i}:
    """Runs a sequence of steps with compensation on failure."""

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
            "state": [StepState{i}.PENDING] * len(self.steps),
            "started_at": time.time(),
        }}
        return saga_id

    def advance(self, saga_id):
        inst = self.instances.get(saga_id)
        if inst is None:
            return None
        idx = inst["current_step"]
        if idx >= len(self.steps):
            return "completed"
        try:
            self.steps[idx](inst["context"])
            inst["state"][idx] = StepState{i}.DONE
            inst["current_step"] += 1
            return "advanced"
        except Exception:
            inst["state"][idx] = StepState{i}.FAILED
            self._compensate(saga_id)
            return "compensating"

    def _compensate(self, saga_id):
        inst = self.instances.get(saga_id)
        if inst is None:
            return
        # Compensations run in forward order instead of reverse order,
        # which can compensate a step that depends on state a later
        # (already-failed) step never actually established.
        for idx in range(inst["current_step"] + 1):
            if inst["state"][idx] == StepState{i}.DONE:
                try:
                    self.compensations[idx](inst["context"])
                    inst["state"][idx] = StepState{i}.COMPENSATED
                except Exception:
                    pass
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
        self.hits = 0
        self.misses = 0

    def get(self, key):
        with self.lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                self.misses += 1
                return None
            self._store.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key, value):
        with self.lock:
            self._store[key] = (value, time.time() + self.ttl_seconds)
            self._store.move_to_end(key)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)

    def invalidate_prefix(self, prefix):
        # O(n) scan holding the lock the whole time; under high
        # cardinality this can stall every other cache operation for the
        # duration of a full-table invalidation.
        with self.lock:
            stale = [k for k in self._store if str(k).startswith(prefix)]
            for k in stale:
                del self._store[k]
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

    def reset(self, client_key):
        with self.lock:
            self._windows.pop(client_key, None)
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
        self._buffer = []  # flushed periodically but retained after flush too
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
        # Bug: buffer is copied to sink but never cleared, so every
        # subsequent flush re-writes the entire history so far, and
        # memory usage grows without bound as `_buffer` is never reset.
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
        self.definitions = definitions  # {{flag_name: {{"rollout_pct": int, "enabled": bool}}}}

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

    def update_rollout(self, flag_name, new_pct):
        if flag_name in self.definitions:
            self.definitions[flag_name]["rollout_pct"] = new_pct
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
        self._dead_letter = []  # unbounded
        self.lock = threading.Lock()

    def subscribe(self, event_type, handler):
        with self.lock:
            self._subscribers[event_type].append(handler)

    def publish(self, event_type, payload):
        # Copies the handler list without the lock, so a concurrent
        # subscribe() during iteration can be missed for this publish,
        # but more importantly handlers are invoked synchronously and a
        # slow handler blocks every other publisher on this bus instance.
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
    """Dispatches tool-call requests from an LLM agent loop to registered
    handler callables, with a simple per-tool concurrency cap."""

    def __init__(self, max_concurrent_per_tool=2):
        self.max_concurrent_per_tool = max_concurrent_per_tool
        self._handlers = {{}}
        self._in_flight = {{}}
        self.lock = threading.Lock()
        self._call_log = []  # retained forever for later replay/debugging

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
            self._call_log.append({{
                "tool": name,
                "arguments": arguments,
                "result_summary": str(result)[:200],
                "ts": time.time(),
            }})
            return {{"result": result}}
        finally:
            with self.lock:
                self._in_flight[name] = max(0, self._in_flight[name] - 1)
```
'''

MARKER_MODULE = f'''
### `{MARKER_MODULE_NAME}`

```python
"""Internal diagnostics configuration - used only for review-harness
context verification. Not part of production request paths."""

DEEP_CONTEXT_VERIFICATION_TOKEN = "{MARKER_VALUE}"

DIAGNOSTIC_FLAGS = {{
    "enable_verbose_tracing": False,
    "enable_slow_query_log": True,
    "context_verification_marker": DEEP_CONTEXT_VERIFICATION_TOKEN,
}}
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

def build(target_tokens):
    parts = [HEADER]
    cur = toks(HEADER) + toks(FOOTER)
    i = 0
    marker_inserted = False
    marker_insert_at = target_tokens // 2  # insert marker near the middle
    while cur < target_tokens:
        gen = GENERATORS[i % len(GENERATORS)]
        block = gen(i)
        block_tokens = toks(block)
        if not marker_inserted and cur + block_tokens >= marker_insert_at:
            marker_block = MARKER_MODULE
            parts.append(marker_block)
            cur += toks(marker_block)
            marker_inserted = True
        parts.append(block)
        cur += block_tokens
        i += 1
    parts.append(FOOTER)
    text = "".join(parts)
    return text, toks(text), i

if __name__ == "__main__":
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 256000
    text, actual, n_modules = build(target)
    sys.stderr.write(f"Generated {n_modules} modules, {actual} tokens (target {target})\n")
    sys.stdout.write(text)
