# Workflow — Approval Flow

A focused, browser-first example of **Quadkit WorkflowModule**. It models a
purchase request with an interactive state machine and a separate approval
policy preview. It uses only the workflow domain module plus `WebModule`.

## What to try

1. Submit the seeded purchase request.
2. Approve or reject at the manager and finance gates.
3. Reject a request and use **Retry approval**, or approve it and use
   **Rollback / compensate**.
4. Run the `ApprovalChain` preview with either gate unchecked.
5. Inspect the append-only transition history and optimistic version counter.

## Quadkit surface

- `WorkflowModule.configure()` and provider lifecycle
- `StateMachine`, `State`, and `Transition`
- `ApprovalChain`, `ApprovalStep`, `ApprovalPolicy`, and `ApprovalStatus`
- deterministic approval/rejection, retry, rollback, and transition history
- `WebModule` controllers with a standalone server entry point

## Run

```bash
cd examples/approval-flow
PYTHONPATH=src uv run python -m approval_flow
```

The hub embeds this console at `/examples/approval-flow/`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/workflow` | Current request, state, steps, and history |
| POST | `/api/workflow/request` | Create/reset a request |
| POST | `/api/workflow/transition` | Trigger an allowed state transition |
| POST | `/api/workflow/policy` | Run an ApprovalChain policy preview |
| POST | `/api/workflow/retry` | Retry a rejected flow |
| POST | `/api/workflow/rollback` | Compensate an approved flow |

## Quadkit Concepts

| Concept | How it's used |
|---------|---------------|
| Provider Pattern | `ApprovalFlowProvider` registers services and wires the controller in DI |
| Dependency Injection | `ApprovalFlowApiController` receives `ApprovalFlowService` via constructor |
| State Machine | `StateMachine` + `State` + `Transition` drive approval flow (draft → manager_review → finance_review → approved/rejected) |
| Approval Chain | `ApprovalChain` with `ApprovalStep` gates runs a multi-step policy preview independently of the state machine |
| Module Pattern | `WorkflowModule` and `WebModule` compose the application with declared exports |
| Web Controllers | `Controller` with `@get`/`@post` decorators exposes the demo API |
| Health Checks | `ApprovalFlowProvider.health_check()` reports readiness status |
