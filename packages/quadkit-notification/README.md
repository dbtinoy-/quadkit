# quadkit-notification

SMS, push, and email notification delivery with Named DI multi-backend support for the Quadkit Framework.

---

## Overview

`quadkit-notification` provides a unified notification delivery system with SMS (Twilio), push (FCM, APNS), email (SMTP, SendGrid), and per-user inbox storage. The package is organized into three subpackages: root (SMS/push), `mailer` (email), and `inbox` (in-app notification storage). Root and `mailer` each wire their own module; the inbox is wired by `InboxProvider` (not a module).

---


> Full documentation: [docs.quadkit.dev](https://docs.quadkit.dev)
## Install

```bash
uv add quadkit-notification

# With SendGrid email
uv add "quadkit-notification[sendgrid]"

# With Twilio SMS
uv add "quadkit-notification[twilio]"

# With APNS push
uv add "quadkit-notification[apns]"
```

## Quick Start

```python
from quadkit.di.module import Module, module
from quadkit.notification import NotificationModule
from quadkit.notification.config import (
    FCMDriverConfig,
    MailerConfig,
    NamedMailerConfig,
    NamedPushConfig,
    NamedSMSConfig,
    NotificationConfig,
    SMTPDriverConfig,
    TwilioDriverConfig,
)
from quadkit.notification.mailer import MailerModule


@module(
    imports=[
        NotificationModule.configure(
            NotificationConfig(
                sms_backends=[
                    NamedSMSConfig(
                        name="alerts",
                        primary=True,
                        driver="twilio",
                        twilio=TwilioDriverConfig(
                            account_sid="AC...",
                            auth_token="secret",
                            from_number="+15550000000",
                        ),
                    )
                ],
                push_backends=[
                    NamedPushConfig(
                        name="mobile",
                        primary=True,
                        driver="fcm",
                        fcm=FCMDriverConfig(server_key="fcm-key"),
                    )
                ],
            )
        ),
        MailerModule.configure(
            MailerConfig(
                backends=[
                    NamedMailerConfig(
                        name="transactional",
                        primary=True,
                        driver="smtp",
                        from_email="noreply@example.com",
                        smtp=SMTPDriverConfig(host="smtp.example.com", port=587),
                    )
                ]
            )
        ),
    ]
)
class AppModule(Module):
    pass
```

## Configuration

> **Zero-config usage:** Call any `.configure()` with no arguments to use all defaults.

### Option 1 — YAML file

```yaml
# application.yaml
notification:
  sms_backends: []
  push_backends: []

mailer:
  backends:
    - name: transactional
      primary: true
      driver: smtp
      from_email: "noreply@example.com"
      smtp:
        host: "smtp.example.com"
        port: 587

inbox:
  store_backend: "database"
  retention_days: 30
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_NOTIFICATION__INBOX__STORE_BACKEND=database
```

### Option 3 — Python

```python
from quadkit.notification import NotificationModule
from quadkit.notification.config import (
    MailerConfig,
    NamedMailerConfig,
    NotificationConfig,
    SMTPDriverConfig,
)
from quadkit.notification.mailer import MailerModule

NotificationModule.configure(NotificationConfig())
MailerModule.configure(
    MailerConfig(
        backends=[
            NamedMailerConfig(
                name="transactional",
                primary=True,
                driver="smtp",
                from_email="noreply@example.com",
                smtp=SMTPDriverConfig(host="smtp.example.com", port=587),
            )
        ]
    )
)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `notification.sms_backends` | `[]` | `QK_NOTIFICATION__SMS_BACKENDS` | Named SMS backend configs |
| `notification.push_backends` | `[]` | `QK_NOTIFICATION__PUSH_BACKENDS` | Named push backend configs |
| `mailer.backends[n].driver` | — | `QK_NOTIFICATION__MAILER__BACKENDS__N__DRIVER` | Mailer driver: `smtp`, `sendgrid` |
| `mailer.backends[n].from_email` | — | `QK_NOTIFICATION__MAILER__BACKENDS__N__FROM_EMAIL` | Sender email address |
| `inbox.store_backend` | `"database"` | `QK_NOTIFICATION__INBOX__STORE_BACKEND` | Inbox store: `database` or `memory` |
| `inbox.retention_days` | `30` | `QK_NOTIFICATION__INBOX__RETENTION_DAYS` | Days to retain inbox messages |
| `inbox.max_page_size` | `50` | `QK_NOTIFICATION__INBOX__MAX_PAGE_SIZE` | Max messages returned per page |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `NotificationModule.configure(config)` | Register SMS and push backends; exports `SMSChannelProtocol`, `PushChannelProtocol` |
| `NotificationModule.stub()` | Empty config — no backends configured |
| `MailerModule.configure(config)` | Register named mailer backends; exports `MailerProtocol` |
| `MailerModule.stub(config=None)` | Empty or caller-supplied config for tests |

Inbox support ships as a service (`InboxService`) wired by `InboxProvider` (in `quadkit.notification.di`), not by `NotificationModule` — include `InboxProvider` in your module's `providers` list when you need the inbox.

## Trusted inbox delivery and recovery

`InboxDeliveryChannel.prepare()` resolves and pins a configured real account;
`InboxService.send_once()` and the existing durable worker make replay safe
across SQL restarts, including lost delivery acknowledgements. See the
[composition, recovery and retention contract](docs/INBOX-DELIVERY.md).
No arbitrary-recipient HTTP send route or automatic Playground binding is added.

## Admin Inbox

When running under `the optional provider`, the package registers a notification
contributor (entry point `the optional provider module`) that exposes:

| Endpoint | Description |
|----------|-------------|
| `GET /admin/notifications/inbox` | Current user's persisted inbox as JSON (`unread_count` + `notifications`, used by the topbar bell) |
| `POST /admin/notifications/read/{message_id}` | Mark one message read |
| `POST /admin/notifications/read-all` | Mark all of the user's messages read |
| `GET /admin/notifications` | Inbox management page inside the admin shell |
| `notifications.inbox` | Health check (`admin/health` fragments) |

Real-time updates: `InboxService.send()` fires the `notification.inbox.sent`
action hook (constant `INBOX_SENT_HOOK` in `quadkit-contracts`); the admin
realtime sub-provider forwards it to the SSE hub so open bells update live.

## Key Features

- **SMS delivery** — Twilio backend via `TwilioSMS`
- **Push delivery** — FCM and APNS backends with `send_batch()` support
- **Email delivery** — SMTP (blocking, runs in executor) and SendGrid REST API
- **Retrying mailer** — wraps any `MailerProtocol` with exponential backoff and delivery-store tracking
- **Per-user inbox** — SQL or in-memory backend with `InboxService` (send, get_inbox, mark_read, delete, count_unread)
- **Multi-backend** — SMS and push backends registered by name from `NotificationConfig.sms_backends` / `push_backends`; the primary backend also receives the unnamed bindings

### SQL delivery timestamps

`SqlDeliveryStore` restores UTC on `DeliveryRecord.created_at` and `retry_after`
when reading the native SQL binding's naive-UTC timestamps. Aware driver values
are normalized to UTC too. This is record hydration, not a change to retry
scheduling, leases, transport guarantees or inbox delivery. A delivery outbox
alone does not make a separate application write and notification send atomic.

## Testing

```python
async with Application.boot(
    modules=[NotificationModule.stub(), MailerModule.stub()]
) as app:
    # your test code
    ...
```

## Key Source Files

| File | What it contains |
|------|----------------|
| `src/quadkit/notification/module.py` | `NotificationModule.configure()`, `.stub()` |
| `src/quadkit/notification/config.py` | `NotificationConfig`, `NamedSMSConfig`, `NamedPushConfig`, `MailerConfig`, `NamedMailerConfig`, `SMTPDriverConfig`, `InboxConfig` |
| `src/quadkit/notification/di/provider.py` | `NotificationProvider` |
| `src/quadkit/notification/di/inbox_provider.py` | `InboxProvider` — wires `InboxStoreProtocol` + `InboxService` |
| `src/quadkit/notification/mailer/module.py` | `MailerModule.configure()`, `.stub()` |
| `src/quadkit/notification/mailer/smtp_mailer.py` | SMTP mailer backend (blocking, executor-run) |
| `src/quadkit/notification/mailer/sendgrid_mailer.py` | SendGrid REST API mailer backend |
| `src/quadkit/notification/mailer/retrying_mailer.py` | `RetryingMailer` — inline exponential backoff + delivery tracking, wraps a `MailerProtocol`; applied by `MailerProvider` when `retry_max_attempts > 0` |
| `src/quadkit/notification/mailer/mailable.py` | `Mailable` — message builder |
| `src/quadkit/notification/inbox/service.py` | `InboxService` — send, get_inbox, get_message, mark_read, mark_all_read, delete, count, count_unread, clear_all |
| `src/quadkit/notification/inbox/memory.py` | `InMemoryInboxStore` |
| `src/quadkit/notification/inbox/database.py` | `DatabaseInboxStore` (`notification_inbox_messages`) |
| `src/quadkit/notification/delivery/stores.py` | `DeliveryStoreProtocol` implementations: `SqlDeliveryStore`, `MemoryDeliveryStore` |
| `src/quadkit/notification/delivery/retry.py` | `DeferredRetryMailer` — one initial email attempt, recording/scheduling a failure for the generic worker |
| `src/quadkit/notification/delivery/worker.py` | `flush_retries()` — claims due messages and dispatches any registered channel with capped backoff/dead-lettering |