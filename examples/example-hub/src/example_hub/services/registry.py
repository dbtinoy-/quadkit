"""Catalog of every demo the hub can host and monitor."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_DEMOS_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


@dataclass(frozen=True)
class DemoService:
    """One hostable demo entry.

    Attributes:
        slug: URL-safe identifier; the demo is mounted at ``/examples/<slug>/``.
        name: Display name.
        port: Port used when the demo runs standalone (informational only —
            embedded mode serves everything from the hub's own port).
        kind: ``web`` for live browser consoles.
        group: Top-level grouping — ``standard`` (single-package) or
            ``multi-module`` (multi-package composition).
        blurb: One-line description for the card grid.
        demo_dir: Directory under ``examples/`` containing this demo.
        app_path: Dotted path of the demo's ``app`` module exposing
            ``create_app()`` — the composition root (starter pattern).
        readme_path: Path to the demo's README.md relative to the demos root.
    """

    slug: str
    name: str
    port: int
    kind: str
    group: str
    blurb: str
    demo_dir: str = ""
    app_path: str = ""
    readme_path: str = ""
    check_path: str = "/"
    errors: list[str] = field(default_factory=list)
    capabilities: tuple[str, ...] = ()
    featured: bool = False

    @property
    def is_hostable(self) -> bool:
        """Whether the fleet can boot and embed this entry."""
        return self.kind == "web"

    def read_readme(self) -> str | None:
        """Return the README.md content, or ``None`` if not found."""
        if not self.readme_path:
            return None
        full = _DEMOS_ROOT / self.readme_path
        if full.is_file():
            return full.read_text(encoding="utf-8")
        return None


class ServiceRegistry:
    """Static catalog of all demos; fleet state is tracked by ``Fleet``."""

    def __init__(self) -> None:
        self.services: list[DemoService] = [
            DemoService(
                "realtime-monitor",
                "Realtime Monitor",
                7071,
                "web",
                "standard",
                "SSE replay + WebSocket operator channel",
                "realtime-monitor",
                "ops_console.app",
                "realtime-monitor/README.md",
            ),
            DemoService(
                "resilient-rates",
                "Resilient Rates",
                7073,
                "web",
                "standard",
                "Cache-aside + resilience pipeline with stale fallback",
                "resilient-rates",
                "rates.app",
                "resilient-rates/README.md",
            ),
            DemoService(
                "event-driven-orders",
                "Event-Driven Orders",
                7074,
                "web",
                "standard",
                "CQRS lifecycle with transactional outbox",
                "event-driven-orders",
                "orders.app",
                "event-driven-orders/README.md",
            ),
            DemoService(
                "rag-docs",
                "RAG Docs",
                7075,
                "web",
                "standard",
                "Cited answers over docs — no LLM, BLAKE2b embedder",
                "rag-docs",
                "rag_docs.app",
                "rag-docs/README.md",
            ),
            DemoService(
                "support-agent",
                "Support Agent",
                8082,
                "web",
                "standard",
                "ReAct agent with scripted LLM + tools",
                "support-agent",
                "support_agent.app",
                "support-agent/README.md",
            ),
            DemoService(
                "memory-chat",
                "Memory Chat",
                8083,
                "web",
                "standard",
                "Episodic + semantic memory — zero LLM, template responder",
                "memory-chat",
                "memory_chat.app",
                "memory-chat/README.md",
            ),
            DemoService(
                "ai-guardrails",
                "AI Guardrails",
                8084,
                "web",
                "standard",
                "Guards, budgets, audit — canned replies, no LLM",
                "ai-guardrails",
                "guard_gate.app",
                "ai-guardrails/README.md",
            ),
            DemoService(
                "prompt-lab",
                "Prompt Lab",
                8085,
                "web",
                "standard",
                "Prompt versioning with deterministic A/B — zero LLM",
                "prompt-lab",
                "prompt_lab.app",
                "prompt-lab/README.md",
            ),
            DemoService(
                "feedback-loop",
                "Feedback Loop",
                8086,
                "web",
                "standard",
                "Ratings → regression — no model call, canned Q&A",
                "feedback-loop",
                "feedback_loop.app",
                "feedback-loop/README.md",
            ),
            DemoService(
                "auth-web",
                "Auth Web",
                8081,
                "web",
                "standard",
                "Cookie sessions, JWT claims, lockout",
                "auth-web",
                "auth_web.app",
                "auth-web/README.md",
            ),
            DemoService(
                "auth-rbac",
                "Auth RBAC",
                8090,
                "web",
                "standard",
                "Permission matrix with live authorize()",
                "auth-rbac",
                "rbac_console.app",
                "auth-rbac/README.md",
            ),
            DemoService(
                "auth-apikeys",
                "Auth API Keys",
                8091,
                "web",
                "standard",
                "Scoped machine keys, instant revocation",
                "auth-apikeys",
                "apikey_console.app",
                "auth-apikeys/README.md",
            ),
            DemoService(
                "auth-mfa",
                "Auth MFA",
                8092,
                "web",
                "standard",
                "TOTP challenge flow with backup codes",
                "auth-mfa",
                "mfa_console.app",
                "auth-mfa/README.md",
            ),
            DemoService(
                "llm-router",
                "LLM Router",
                8093,
                "web",
                "standard",
                "Content generation with deterministic routing",
                "llm-router",
                "content_gen.app",
                "llm-router/README.md",
            ),
            DemoService(
                "monitor-stack",
                "Monitor Stack",
                8094,
                "web",
                "standard",
                "Quadkit Monitor health, metrics, and tracing console",
                "monitor-stack",
                "monitorstack.app",
                "monitor-stack/README.md",
            ),
            DemoService(
                "queue-worker",
                "Queue Worker",
                8095,
                "web",
                "standard",
                "Quadkit MessageConsumer for one tasks topic",
                "queue-worker",
                "queueworker.app",
                "queue-worker/README.md",
            ),
            DemoService(
                "rag-pipeline",
                "RAG Pipeline",
                8096,
                "web",
                "standard",
                "Quadkit vector collection, chunking, and retrieval",
                "rag-pipeline",
                "ragdocs.app",
                "rag-pipeline/README.md",
            ),
            DemoService(
                "sql-repository",
                "SQL Repository",
                8097,
                "web",
                "standard",
                "Quadkit DatabaseModule with SQLite task repository",
                "sql-repository",
                "taskapp.app",
                "sql-repository/README.md",
            ),
            DemoService(
                "webhook-relay",
                "Webhook Relay",
                8098,
                "web",
                "standard",
                "Quadkit subscription creation and HMAC verification",
                "webhook-relay",
                "webhookrelay.app",
                "webhook-relay/README.md",
                capabilities=("subscriptions", "HMAC", "webhooks"),
            ),
            DemoService(
                "feature-flags",
                "Release Control Lab",
                8099,
                "web",
                "standard",
                "Feature rollouts, variants, overrides, and audit history",
                "feature-flags",
                "release_control.app",
                "feature-flags/README.md",
                capabilities=("feature flags", "variants", "runtime overrides"),
                featured=True,
            ),
            DemoService(
                "approval-flow",
                "Approval Flow",
                8100,
                "web",
                "standard",
                "State-machine approvals with retry and compensation",
                "approval-flow",
                "approval_flow.app",
                "approval-flow/README.md",
                capabilities=("state machine", "approval gates", "history"),
                featured=True,
            ),
            DemoService(
                "artifact-vault",
                "Artifact Vault",
                8101,
                "web",
                "standard",
                "Browser object storage with metadata and previews",
                "artifact-vault",
                "artifact_vault.app",
                "artifact-vault/README.md",
                capabilities=("blob storage", "metadata", "offline"),
                featured=True,
            ),
            DemoService(
                "event-timeline",
                "Events Timeline Lab",
                8102,
                "web",
                "standard",
                "Publish, inspect, fail, and replay an in-memory event stream",
                "event-timeline",
                "timeline_lab.app",
                "event-timeline/README.md",
                capabilities=("event bus", "event store", "replay", "offline"),
                featured=True,
            ),
            DemoService(
                "graphql-catalog",
                "GraphQL Catalog",
                7076,
                "web",
                "standard",
                "Typed GraphQL query/mutation API over an in-memory catalog",
                "graphql-catalog",
                "catalog.app",
                "graphql-catalog/README.md",
                capabilities=("graphql", "strawberry", "introspection", "offline"),
            ),
            DemoService(
                "storefront",
                "Storefront",
                8103,
                "web",
                "multi-module",
                "Two bounded-context modules composed through an exported protocol",
                "storefront",
                "storefront.app",
                "storefront/README.md",
                capabilities=("modules", "DI visibility", "bounded contexts"),
                featured=True,
            ),
            DemoService(
                "secrets-vault",
                "Secrets Vault",
                8104,
                "web",
                "standard",
                "Versioned secret storage with manual and age-checked rotation",
                "secrets-vault",
                "secrets_vault.app",
                "secrets-vault/README.md",
                capabilities=("rotation", "versioning", "grace period"),
                featured=True,
            ),
            DemoService(
                "graph-explorer",
                "Graph Explorer",
                8105,
                "web",
                "standard",
                "In-memory knowledge graph with node/edge CRUD and BFS traversal",
                "graph-explorer",
                "graph_explorer.app",
                "graph-explorer/README.md",
                capabilities=("nodes & edges", "traversal", "in-memory store"),
                featured=True,
            ),
            DemoService(
                "audit-trail",
                "Audit Trail",
                8106,
                "web",
                "standard",
                "HMAC-checksummed audit log with tamper detection and retention",
                "audit-trail",
                "audit_trail.app",
                "audit-trail/README.md",
                capabilities=("tamper detection", "retention policy", "SQL-backed"),
                featured=True,
            ),
            DemoService(
                "search-console",
                "Search Console",
                8107,
                "web",
                "standard",
                "SQLite FTS5 full-text search with BM25 ranking and faceted queries",
                "search-console",
                "search_console.app",
                "search-console/README.md",
                capabilities=("full-text search", "BM25 ranking", "faceted queries"),
                featured=True,
            ),
            DemoService(
                "notification-center",
                "Notification Center",
                8108,
                "web",
                "standard",
                "Email delivery and per-user inbox over the real mailer and inbox stack",
                "notification-center",
                "notification_center.app",
                "notification-center/README.md",
                capabilities=("email delivery", "per-user inbox", "read tracking"),
                featured=True,
            ),
            DemoService(
                "task-console",
                "Task Console",
                8109,
                "web",
                "standard",
                "Background job console over the real worker pool, scheduler, and dead letter queue",
                "task-console",
                "task_console.app",
                "task-console/README.md",
                capabilities=("worker pool", "scheduler", "dead letter queue"),
                featured=True,
            ),
            DemoService(
                "tenant-console",
                "Tenant Console",
                8112,
                "web",
                "standard",
                "Multi-tenant control room over the real resolver chain, lifecycle service, and config overrides",
                "tenant-console",
                "tenant_console.app",
                "tenant-console/README.md",
                capabilities=(
                    "tenant resolution",
                    "lifecycle CRUD",
                    "per-tenant config",
                ),
                featured=True,
            ),
            DemoService(
                "http-lab",
                "HTTP Lab",
                8110,
                "web",
                "standard",
                "Outbound HTTP operations console over the real client, retry policy, and circuit breaker",
                "http-lab",
                "http_lab.app",
                "http-lab/README.md",
                capabilities=("retry policy", "circuit breaker", "SSRF gate"),
                featured=True,
            ),
            DemoService(
                "nosql-console",
                "NoSQL Console",
                8111,
                "web",
                "standard",
                "Document store operations console over the real repository, query builder, and migration stack",
                "nosql-console",
                "nosql_console.app",
                "nosql-console/README.md",
                capabilities=(
                    "document repository",
                    "query builder",
                    "schema migrations",
                ),
                featured=True,
            ),
            DemoService(
                "saas-platform",
                "SaaS Platform",
                8113,
                "web",
                "multi-module",
                "Three bounded-context modules wrapping tenancy, auth, and feature-flag packages",
                "saas-platform",
                "saas_platform.app",
                "saas-platform/README.md",
                capabilities=(
                    "modules",
                    "DI visibility",
                    "multi-tenant auth",
                    "feature flags",
                ),
                featured=True,
            ),
        ]

    def web_services(self) -> list[DemoService]:
        """Return entries that the fleet can boot and embed."""
        return [s for s in self.services if s.is_hostable]

    def snapshot(
        self,
        mounted: dict[str, bool],
        failures: dict[str, str],
    ) -> list[dict[str, object]]:
        """Compose the status payload consumed by the hub console.

        Args:
            mounted: Slug → whether the demo booted and is mounted.
            failures: Slug → error text for demos that failed to boot.

        Returns:
            One dict per service with a ``status`` of ``up`` or ``down``.
        """
        payload: list[dict[str, object]] = []
        for svc in self.services:
            status = "up" if mounted.get(svc.slug) else "down"
            payload.append(
                {
                    "slug": svc.slug,
                    "name": svc.name,
                    "port": svc.port,
                    "kind": svc.kind,
                    "group": svc.group,
                    "blurb": svc.blurb,
                    "capabilities": list(svc.capabilities),
                    "featured": svc.featured,
                    "status": status,
                    "error": failures.get(svc.slug),
                }
            )
        return payload


__all__ = ["DemoService", "ServiceRegistry"]
