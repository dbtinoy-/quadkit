# quadkit-storage

Unified blob storage abstraction for Quadkit Framework — S3, GCS, Azure Blob, and local filesystem

---

## Overview

quadkit-storage provides a unified `BlobStore` interface over Amazon S3, Google Cloud Storage, Azure Blob Storage, Cloudflare R2, and local disk — with signed URLs, streaming uploads, content-type negotiation, and server-side encryption. All services are wired via `StorageProvider`, which registers the blob store protocol with the DI container.

---


> Full documentation: [docs.quadkit.dev](https://docs.quadkit.dev)
## Install

```bash
uv add quadkit-storage
# Optional extras
uv add "quadkit-storage[s3]"     # Amazon S3 (aiobotocore)
uv add "quadkit-storage[gcp]"    # Google Cloud Storage
uv add "quadkit-storage[azure]"  # Azure Blob Storage
```

## Quick Start

```python
from quadkit import Application
from quadkit.di.module import Module, module

# Import the module from the package
from quadkit.storage import StorageModule
from quadkit.storage.config import StorageConfig, StorageLocalConfig


@module(
    imports=[
        StorageModule.configure(
            StorageConfig(drivers={"local": StorageLocalConfig(root_dir="./storage")})
        )
    ]
)
class AppModule(Module):
    pass


async with Application.boot(modules=[AppModule]) as app:
    # use app.container to resolve services
    ...
```

## Configuration

> **Zero-config usage:** Call `StorageModule.configure()` with no arguments to use defaults.

### Option 1 — YAML file

```yaml
# application.yaml
storage:
  default_driver: "s3"
  drivers:
    s3:
      bucket: "my-app-uploads"
      region: "us-east-1"
      access_key: "${AWS_ACCESS_KEY_ID}"
      secret_key: "${AWS_SECRET_ACCESS_KEY}"
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_STORAGE__ENABLED=true
# Environment variables for each field
```

### Option 3 — Python

```python
from quadkit.storage.config import StorageConfig
from quadkit.storage import StorageModule

config = StorageConfig(default_driver="s3", ...)
StorageModule.configure(config)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `default_driver` | `"local"` | `QK_STORAGE__DEFAULT_DRIVER` | Active driver: `s3`, `gcs`, `azure`, `r2`, `local`, `memory` |
| `drivers.s3.bucket` | — | `QK_STORAGE__DRIVERS__S3__BUCKET` | S3 bucket name |
| `drivers.s3.region` | `"us-east-1"` | `QK_STORAGE__DRIVERS__S3__REGION` | AWS region |
| `drivers.s3.access_key` | — | `QK_STORAGE__DRIVERS__S3__ACCESS_KEY` | AWS access key ID |
| `drivers.s3.secret_key` | — | `QK_STORAGE__DRIVERS__S3__SECRET_KEY` | AWS secret access key |
| `drivers.s3.endpoint_url` | `null` | `QK_STORAGE__DRIVERS__S3__ENDPOINT_URL` | Override endpoint (MinIO, LocalStack) |
| `drivers.gcs.bucket` | — | `QK_STORAGE__DRIVERS__GCS__BUCKET` | GCS bucket name |
| `drivers.gcs.credentials_path` | — | `QK_STORAGE__DRIVERS__GCS__CREDENTIALS_PATH` | Path to service account JSON |
| `drivers.azure.account_name` | — | `QK_STORAGE__DRIVERS__AZURE__ACCOUNT_NAME` | Azure storage account name |
| `drivers.azure.container` | — | `QK_STORAGE__DRIVERS__AZURE__CONTAINER` | Azure blob container |
| `drivers.local.root_dir` | — | `QK_STORAGE__DRIVERS__LOCAL__ROOT_DIR` | Root directory for local storage |
| `service.max_file_size_mb` | `100` | `QK_STORAGE__SERVICE__MAX_FILE_SIZE_MB` | Maximum upload size in MB |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `StorageModule.configure(config, enable_encryption)` | Configure with explicit StorageConfig |
| `StorageModule.stub()` | Minimal config for testing |

## Key Features

- **S3** — Multi-part upload, server-side encryption, lifecycle rules
- **GCS** — Resumable uploads, CMEK, uniform bucket-level access
- **Azure** — Block blobs, shared access signatures (SAS), CDN integration
- **R2** — Cloudflare R2 (S3-compatible) support
- **Local driver** — On-disk storage for development and CI
- **Memory driver** — In-process storage for unit tests
- **Signed URLs** — Time-limited GET / PUT pre-signed URLs for direct browser upload
- **Content negotiation** — Automatic MIME type detection from extension and magic bytes
- **Key-value store** — `InMemoryKVStorage` (memory) / `LocalStorage` (file) for small blobs (config, flags)
- **Streaming** — `stream()` yields chunks for arbitrarily large files

## Testing

```python
async with Application.boot(modules=[StorageModule.stub()]) as app:
    # your test code
    ...
```

## Key Source Files

| File | What it contains |
|------|----------------|
| `src/quadkit/storage/module.py` | `StorageModule` class with factory methods |
| `src/quadkit/storage/di/provider.py` | `StorageProvider` — wires storage protocols into DI container |
| `src/quadkit/storage/config.py` | `StorageConfig` and sub-config classes |
| `src/quadkit/storage/backends/` | Driver implementations (`AbstractDriver`, S3, GCS, Azure, R2, local, memory) |
| `src/quadkit/storage/kv/` | KV backends (`InMemoryKVStorage`, `LocalStorage`) |