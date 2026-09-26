# Storage — Artifact Vault

A focused, browser-first example of **Quadkit StorageModule**. It uses only
the storage domain module plus `WebModule`, with the package's deterministic
in-memory blob driver and no cloud credentials.

## What to try

1. Upload a text, Markdown, or JSON artifact.
2. Inspect object metadata, including size, content type, owner, and ETag.
3. Preview and delete objects from the browser.
4. Open **Access** to see the active driver's public URL and its honest
   presigned-URL capability.

## Quadkit surface

- `StorageModule.configure()` and `StorageProvider` lifecycle
- DI-injected `BlobStoreProtocol`
- `UploadOptions` metadata and content-type handling
- upload, list, info, download, delete, URL, and health operations
- `WebModule` controllers with a standalone server entry point

The memory driver intentionally reports that presigned URLs are unavailable;
use a cloud driver for real signed access. The rest of the object API is the
same, which makes the demo safe to run offline.

## Run

```bash
cd examples/artifact-vault
PYTHONPATH=src uv run python -m artifact_vault
```

The hub embeds this console at `/examples/artifact-vault/`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/artifacts` | List object metadata |
| POST | `/api/artifacts/upload` | Upload an artifact |
| GET | `/api/artifacts/content/{name}` | Download and preview text |
| GET | `/api/artifacts/access/{name}` | Show URL and signed access support |
| DELETE | `/api/artifacts/{name}` | Delete an object |
| GET | `/api/artifacts/health` | Check the active storage backend |

## Quadkit Concepts

| Concept | How it's used |
|---------|---------------|
| Provider Pattern | `ArtifactVaultProvider` registers config and controller in DI during `register()`, resolves the blob store and binds the service in `boot()` |
| Dependency Injection | `ArtifactVaultApiController` receives `ArtifactVaultService` via constructor; `ArtifactVaultService` receives `BlobStoreProtocol` and config |
| Service Adapter | `ArtifactVaultService` wraps `BlobStoreProtocol` with domain-specific upload/list/content/delete/health operations |
| Health Checks | Provider exposes `health_check()` returning `HealthCheckResult`; controller exposes `/api/artifacts/health` |
| Seed Data | Demo boots with a `docs/welcome.txt` artifact for immediate browser interaction |
| Web Controllers | `ArtifactVaultApiController` uses `@get`/`@post`/`@delete` decorators to define REST endpoints under `/api/artifacts` |
