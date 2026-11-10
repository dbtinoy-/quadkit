# quadkit-workflow

Workflow orchestration for the Quadkit Framework (pipelines, bulk ops, sagas, graph engine)

---

## Overview

quadkit-workflow provides workflow orchestration, state machines, and saga pattern for modeling complex, long-running business processes. It supports durable persistence of transition history, optimistic locking, multi-level approval chains, distributed transaction coordination with automatic rollback, and a graph engine for traversing directed graphs. All services are wired via `WorkflowProvider`, which registers workflow protocols with the DI container.

---


> Full documentation: [docs.quadkit.dev](https://docs.quadkit.dev)
## Install

```bash
uv add quadkit-workflow
```

## Quick Start

```python
from quadkit import Application
from quadkit.di.module import Module, module

# Import the module from the package
from quadkit.workflow import WorkflowModule


@module(imports=[WorkflowModule.configure()])
class AppModule(Module):
    pass


async with Application.boot(modules=[AppModule]) as app:
    # use app.container to resolve services
    ...
```

## Configuration

> **Zero-config usage:** Call `WorkflowModule.configure()` with no arguments to use defaults.

### Option 1 — YAML file

```yaml
# application.yaml
workflow:
  batch_size: 10
  max_concurrency: 5
  timeout: 300.0
  retry_attempts: 3
  enable_progress_tracking: true
  pipeline_timeout: 60.0
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_WORKFLOW__ENABLED=true
# Environment variables for each field
```

### Option 3 — Python

```python
from quadkit.workflow.config import BulkOperationConfig
from quadkit.workflow import WorkflowModule

config = BulkOperationConfig(batch_size=10, max_concurrency=5, retry_attempts=3)
WorkflowModule.configure(config=config)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `batch_size` | `10` | `QK_WORKFLOW__BATCH_SIZE` | Items processed per batch during bulk operations |
| `max_concurrency` | `5` | `QK_WORKFLOW__MAX_CONCURRENCY` | Maximum parallel operations in a bulk run |
| `timeout` | `300.0` | `QK_WORKFLOW__TIMEOUT` | Operation timeout in seconds |
| `retry_attempts` | `3` | `QK_WORKFLOW__RETRY_ATTEMPTS` | Automatic retry count on step failure |
| `retry_delay` | `1.0` | `QK_WORKFLOW__RETRY_DELAY` | Seconds to wait between retry attempts |
| `enable_progress_tracking` | `true` | `QK_WORKFLOW__ENABLE_PROGRESS_TRACKING` | Track and report bulk operation progress |
| `pipeline_timeout` | `60.0` | `QK_WORKFLOW__PIPELINE_TIMEOUT` | Default pipeline execution timeout in seconds |

Content-addressed checkpointing is configured via a standalone `ContentCheckpointConfig` passed to `WorkflowModule.configure(..., content_checkpoint_config=...)` — it is **not** a field of `BulkOperationConfig` and is not read from environment variables.

| Field | Default | Description |
|-------|---------|-------------|
| `enabled` | `true` | Enable content-addressed checkpointing |
| `inline_threshold_bytes` | `1048576` | Max bytes to store inline before blob offload |
| `default_ttl_seconds` | `86400` | Default TTL for cache-backed checkpoint stores |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `WorkflowModule.configure(config, saga_store)` | Configure with explicit BulkOperationConfig |
| `WorkflowModule.configure(config, saga_store, content_checkpoint_store)` | Configure with content-addressed checkpoint store |
| `WorkflowModule.stub()` | Minimal config for testing |

## Key Features

- **State machine** — Declarative states and transitions with entry/exit hooks
- **Durable persistence** — Transition history persisted to DB via `StatePersistenceProtocol`
- **Optimistic locking** — Prevents concurrent transition conflicts
- **State recovery** — Rebuild machine state from persisted history on restart
- **Approval chains** — Multi-level approval flows with role and threshold rules
- **Sagas** — Distributed transaction coordination with automatic rollback
- **Content-addressed sagas** — Idempotent stage caching keyed by `sha256(stage_id, tenant_id, inputs, handler_version, config)`; skips already-completed work on resume
- **Pipeline checkpointing** — Content-addressed checkpoint stores (`InMemory`, `Cache`, `Database`) for durable saga resume
- **Pipelines** — Step-based sequential pipelines with error handling
- **Bulk operations** — Apply an operation to many entities in a supervised batch
- **Guard conditions** — Transition guards as `async def can_confirm(self) -> bool`
- **Event hooks** — `on_enter_*`, `on_exit_*`, `on_transition` lifecycle callbacks

## Testing

```python
async with Application.boot(modules=[WorkflowModule.stub()]) as app:
    # your test code
    ...
```

## Key Source Files

| File | What it contains |
|------|----------------|
| `src/quadkit/workflow/module.py` | `WorkflowModule` class with factory methods |
| `src/quadkit/workflow/di/provider.py` | `WorkflowProvider` — wires workflow protocols into DI container |
| `src/quadkit/workflow/config.py` | `BulkOperationConfig`, `ContentCheckpointConfig`, and `GraphConfig` |
| `src/quadkit/workflow/state/` | State machine implementation with transitions and hooks |
| `src/quadkit/workflow/saga/` | Saga pattern implementation with compensating transactions and content-addressed caching |
| `src/quadkit/workflow/pipeline/` | Pipeline executor for chaining steps |
| `src/quadkit/workflow/approval/` | Approval chain and levels |
| `src/quadkit/workflow/checkpoint/` | Content-addressed checkpoint stores (in-memory, cache, database) |