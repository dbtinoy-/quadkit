# Trusted publication -> durable inbox

For the separate **generated Builder composition**, use the
[editorial graph/setup guide](../../apps/playground/docs/gallery/editorial-notifications.md).
This document remains the reference host, not its generated-project proof.

This separate runnable Notification Center mode completes the **local,
application-owned** create -> publish -> search -> notify flow. It uses real SQL
accounts, native signed bearer tokens, one atomic publication/queue transaction,
and the native durable delivery worker. No fixture recipient, public send route,
request-selected destination or pretend successful notification.

It is **not automatic Playground graph/effect generation**. The existing
editorial gallery and its action/auth/effect gates are unchanged. This reference
host demonstrates the application binding without silently promoting that gate.
The original in-memory Notification Center console is unchanged too.

## Run from this source checkout

Use the existing Playground workspace environment to provide the local SQL,
Auth, Notification and Web packages (including Uvicorn), not PyPI placeholders:

```sh
# Repository root; uv resolves these packages from workspace sources.
uv sync --package quadkit-playground --group test
cd examples/notification-center
export PYTHONPATH="$PWD/src"
export QK_PROFILE=trusted
export EDITORIAL_RECIPIENT_EMAIL='editor@example.test'
# Generate once, keep private, and reuse across CLI/server/worker restarts.
export EDITORIAL_TOKEN_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
# Optional; native Quadkit SQL configuration remains the authority.
export QK_SQL__BACKEND__URL="sqlite+aiosqlite:///$PWD/editorial-notifications.db"
```

First enroll a **real persisted account** and explicitly grant it publication
permission using the local operator command:

```sh
uv run --package quadkit-playground --group test python -m notification_center.trusted \
  issue --email editor@example.test --create --publisher
```

The last JSON line contains its native `user_id` and one-hour `access_token`.
Treat the token as a secret. There is no public signup/token-issuance endpoint,
no default account/password, and no account silently created at application
boot. For subsequent tokens omit `--create --publisher`; issuance never changes
an existing account's permissions. Other accounts can be explicitly enrolled
without `--publisher`, then can access only their own inbox.

Start the server:

```sh
uv run --package quadkit-playground --group test python -m notification_center.trusted serve
```

Open `/docs` on port **8086**, click **Authorize** and supply the access token.
The served OpenAPI explicitly declares the enforced bearer scheme. Tokens must
be sent in one Authorization header, not cookies, query strings or request state.
The `trusted` profile sets no-store responses and excludes bearer requests from
CSRF checks; all mutations still authenticate the token and check fresh account
state. Do not weaken these settings to expose this local reference publicly.

In another terminal, reuse the same exported environment and start the worker:

```sh
uv run --package quadkit-playground --group test python -m notification_center.trusted worker
# Or drain currently due deliveries once:
uv run --package quadkit-playground --group test python -m notification_center.trusted flush
```

The worker uses existing native leases/backoff/max-attempt/dead-letter policy.
The one-second poll is scheduling, not a replacement retry policy. Database
failures exit the worker rather than reporting success; the operator/supervisor
owns restart. No in-process background send can race an uncommitted publication.

## HTTP journey

All routes below require a signed token for a currently active SQL account.
Publication routes additionally require the fresh `editorial:publish` permission;
a permission claim in an old token is not sufficient after revocation.

| Request | Result |
| --- | --- |
| `POST /posts` with `{"title":"Release notes"}` | 201, persisted draft and ID |
| `POST /posts/{id}/publish` with `{}` | 202, published row and durable delivery ID; `notification: queued`, **not sent** |
| `GET /posts/search?q=Release` | Bounded literal title search, including drafts; not a public feed or FTS claim |
| `GET /inbox` | Only the authenticated account's inbox, delivered by the separate worker |
| `GET /inbox/{id}` | Owner-only read; foreign/missing IDs both return 404 |
| `POST /inbox/{id}/read` | Owner-scoped write; missing/foreign IDs return the same 204 |
| `DELETE /inbox/{id}` | Owner-scoped delete; replay does not resurrect it |

Only a title of 1-120 characters is accepted on create. Publish accepts no input
fields. Unknown state/recipient/routing fields, ambiguous JSON keys, oversized
bodies and invalid credentials are rejected. There is no `/send`, `/redrive`,
public worker-control or arbitrary-recipient endpoint. Unknown/inactive configured
recipient accounts refuse publication with 503 before the business write.

## Failure and recovery contract

Publication checks the expected draft state and title, then commits its state
change and native queue insert together on the same SQL provider. Failed enqueue
rolls publication back; fix storage and retry that still-draft publication.
Conditional conflicts return 409 and create no second intent.

Once 202 succeeds, notification failure **does not roll publication back**.
Do not retry publication: it correctly returns 409. The worker retries the queued
intent. Recipient ID is pinned before enqueue and resolved again on delivery;
account deletion/reassignment cannot redirect an old intent. Only `post_id` and
published status are copied as business metadata, never arbitrary request details.

Inbox insertion and the native idempotency receipt commit together. A lost
worker acknowledgement is recovered after lease expiry on restart, returning the
same message ID. Delivery hooks remain best effort, not exactly-once transports.

After fixing a terminal delivery failure, explicitly redrive the failed ID:

```sh
uv run --package quadkit-playground --group test python -m notification_center.trusted \
  redrive --delivery-id '<failed-delivery-id>'
```

This operator-only command creates a new queue row preserving the old failed row
and **exact same pinned envelope/effect key**. It does not re-publish, change the
recipient, rotate the deduplication key or modify body/metadata. The normal worker
then delivers it. Read/delete/clear of inbox messages never resets the receipt.

## Verified scope and limits

The tests exercise real native composition and SQLite, signed credentials,
served bearer schema, spoof/foreign-account refusal, account/permission revocation,
queue-insert rollback, failed inbox insertion, lost acknowledgement, fresh
Application/store connections, terminal redrive, and no resurrection after delete.
Separate actual TCP server + CLI worker + full server restart checks also pass.

This is local source CPython3.11 / SQLite evidence, not PostgreSQL, deployment,
released-wheel/PyPI, general Builder composition, owner UX or security certification.
No browser UI automation was run; native Swagger is the manual interface.
Remaining legacy example mypy findings are not claimed fixed by this new mode.

Receipt IDs/digests, queue envelopes and business posts survive inbox deletion.
Operators need an explicit retention/erasure policy; no automatic purge or complete
personal-data-erasure claim. No external email/SMS/push delivery is involved.
