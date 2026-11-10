# Notification Center

For a **signed-account, durable publish-to-inbox flow**, use the separate
[trusted publication mode](TRUSTED-PUBLICATION.md). The original console below
remains an in-memory API showcase, not an authenticated account boundary.

A focused, browser-first example of **Quadkit's mailer + inbox stack**
from `quadkit-notification`. It combines `MailerModule` (email delivery)
with `InboxProvider`/`InboxService` (per-user inbox persistence) and
`WebModule` — no external mail provider (SMTP/SendGrid) or database is
required.

## What to try

1. Look at the seeded inbox: three sample messages written through the
   real `InboxService.send()` call on boot for `demo-user`.
2. Send an email from the form — it goes through the real
   `MailerProtocol.send()` call, which resolves to `ConsoleMailer` in this
   demo, so the message is logged to the server console instead of
   leaving the box.
3. Check the health panel — it reports the mailer backend's own
   `health_check()` result plus how many emails the demo has sent.
4. Switch the inbox's user ID and send a message to a different user to
   see per-user isolation in the real `InboxStoreProtocol`.
5. Mark a message read, mark everything read in one call, delete a single
   message, or clear the whole inbox — all real `InboxService` writes.

## Quadkit surface

- `MailerModule.configure()` and the `MailerProtocol` it registers
  (`ConsoleMailer` via `console_fallback`, configured entirely from
  `application.yaml`)
- `MailerProtocol.send()` — deliver an `EmailMessage`, returning a
  `MessageDeliveryReceipt`
- `MailerProtocol.health_check()` — readiness reporting for the mailer
  backend
- `InboxProvider` and the `InboxService` it registers (`InMemoryInboxStore`
  backend, configured directly in `app.py`)
- `InboxService.send()` / `get_inbox()` / `mark_read()` / `mark_all_read()`
  / `delete()` / `count_unread()` / `clear_all()` — real per-user inbox CRUD
- `WebModule` controllers with a standalone server entry point

## Run

```bash
cd examples/notification-center
PYTHONPATH=src uv run python -m notification_center
```

The hub embeds this console at `/examples/notification-center/`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/notifications/health` | Report readiness of the underlying mailer backend |
| POST | `/api/notifications` | Send an email from `{to, subject, body}` |
| GET | `/api/notifications/sent` | List every email the demo has sent this run |
| POST | `/api/notifications/inbox` | Create an inbox notification from `{user_id, title, body}` |
| GET | `/api/notifications/inbox` | List inbox messages for `user_id` (`unread_only` optional) |
| GET | `/api/notifications/inbox/unread-count` | Return the unread message count for `user_id` |
| POST | `/api/notifications/inbox/read-all` | Mark every unread message for `user_id` as read |
| POST | `/api/notifications/inbox/message/{message_id}/read` | Mark a single message as read |
| DELETE | `/api/notifications/inbox/message/{message_id}` | Delete a single message |
| DELETE | `/api/notifications/inbox` | Delete every message for `user_id` |

## Quadkit Concepts

| Concept | How it's used |
|---------|---------------|
| Provider Pattern | `NotificationCenterProvider` resolves the `MailerProtocol` and `InboxService` that `MailerModule`/`InboxProvider` registered, then wires the browser-facing service |
| Dependency Injection | `NotificationCenterApiController` receives `NotificationCenterService` via constructor; the service receives the real mailer and inbox objects |
| Zero-Config Module | `MailerModule.configure()` takes no arguments — `console_fallback` binds a real `ConsoleMailer` from the typed `mailer` yaml section |
| Sibling Providers, No Bundling Module | `InboxProvider` is added directly alongside `MailerModule` because `quadkit-notification` has no combined module bundling mailer and inbox together, mirroring how `examples/audit-trail` adds `DatabaseModule`/`AuditModule` |
| Per-User Isolation | Every inbox call is scoped by `user_id`; `mark_read()`/`delete()` are guarded by ownership |
| Health Checks | `NotificationCenterProvider.health_check()` delegates to the service, which reports the mailer backend's own `health_check()` result |
| Result Pattern | `send_email()` returns `Result[dict, MailerError]`; validation failures raise `ValueError`, mapped to a `ValidationError` |
| RFC-9457 Problem Details | A missing recipient/subject/title maps to a 422 `application/problem+json` body via `ValidationError` |
| Web Controllers | `NotificationCenterApiController` extends `Controller` with `@get`/`@post`/`@delete` route decorators under the `/api/notifications` prefix |
| Route Collision Avoidance | `/inbox/message/{message_id}` (not a bare `/inbox/{message_id}`) so the dynamic route never shadows `/inbox/read-all` or `/inbox/unread-count` |
| Client-Tracked Sent Log | `MailerProtocol` has no "list sent messages" method, so the demo tracks what it has sent client-side — the same pattern `graph-explorer` and `search-console` use for their own unlistable collections |
