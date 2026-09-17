# Multi-tenant Notes

Tenant resolution from the `X-Tenant-Id` header with strict data
isolation: every store operation is keyed by tenant, so cross-tenant
reads are impossible by construction rather than by convention.

**Demonstrates:** header-based tenant resolution, a DI-bound partitioned
store, `400/404/409` semantics, a custom error registered on the
`ResultResponseMapper` (missing header → 400), and isolation tests (the
cross-tenant fetch is the behavior under test).

## Layout

```
src/multi_tenant_notes/
├── app.py             # composition root
├── main.py            # serve() with try/finally app.stop()
├── config.py          # MultiTenantNotesConfig (max_notes_per_tenant)
├── controllers/api.py # NotesController + require_tenant → Result
├── services/notes.py  # NotesStore (tenant-keyed) + MissingTenantError
└── di/provider.py     # binds store + controller
```

## Run

```bash
pip install quadkit[web]
PYTHONPATH=src python -m multi_tenant_notes
curl -X POST localhost:8125/notes -H 'X-Tenant-Id: acme' \
  -H 'content-type: application/json' -d '{"text": "hello"}'
curl localhost:8125/notes -H 'X-Tenant-Id: acme'
```

Tenants are unlimited by default; set
`multi_tenant_notes.max_notes_per_tenant` and the cap answers 409.

## Test

```bash
PYTHONPATH=src pytest tests/
```
