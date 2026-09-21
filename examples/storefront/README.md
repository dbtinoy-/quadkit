# Storefront Demo

> Module name: `storefront` — run with `PYTHONPATH=src uv run python -m storefront`

Demonstrates Quadkit's **multi-module layout** (Pattern 3, "Modular App
Layout" — see `docs/getting-started/project-structure.md`): a single app
split into two bounded-context `@module` packages that talk to each other
only through an exported protocol, with the DI container enforcing the
boundary at boot time.

Every other demo in `examples/` is one flat package with one `Provider`.
This one is a mini e-commerce backend with two independent modules under
`src/storefront/modules/`:

- **`catalog`** — owns product data and stock. Exports
  `ProductCatalogProtocol`; nothing outside the module ever imports the
  concrete `ProductCatalogService`.
- **`orders`** — places orders. Imports `CatalogModule` and depends only
  on `ProductCatalogProtocol` to price lines and reserve stock.

Try deleting `imports=[CatalogModule.configure()]` from
`storefront/modules/orders/__init__.py` and running the app (or the
`test_module.py` visibility tests) — boot fails with
`ModuleVisibilityError` naming the missing import, not a generic
`NameError`. That failure mode is the module system doing its job:
visibility is a compile-time property of the module graph, not a runtime
accident.

## Quadkit concepts used

| Concept | Where in this demo | Your app |
|---------|--------------------|----------|
| Bounded-context modules | `modules/catalog/`, `modules/orders/` | `src/<pkg>/modules/<slug>/` |
| Module boundary + exports | `modules/catalog/__init__.py` | `@module(exports=[...])` |
| Cross-module import | `modules/orders/__init__.py` | `@module(imports=[OtherModule.configure()])` |
| Contracts-only dependency | `modules/orders/services.py` | Depend on the protocol, never the concrete class |
| Visibility enforcement | `modules/orders/provider.py` `boot()` | `ModuleVisibilityError` at container resolve time |
| Controller auto-discovery | `app.py` | `WebModule.configure(discover=[...])` |
| Provider lifecycle | `modules/*/provider.py` | `register()` binds placeholders, `boot()` resolves + `container.bind()` |

## Run it

```bash
cd examples/storefront
PYTHONPATH=src uv run python -m storefront          # start the web console
```

Open `http://localhost:8103` for the storefront console. Browse the seeded
catalog, place an order (stock reserves live against the catalog module),
or click **Run Demo Order** for a one-click walkthrough.

## Layout — read it in this order

| # | File | Lesson |
|---|------|--------|
| 1 | `src/storefront/app.py` | ⭐ Composition root: `MODULES` + `WebModule.configure(discover=[...])` |
| 2 | `src/storefront/modules/catalog/__init__.py` | Producer module: `@module(exports=[ProductCatalogProtocol])` |
| 3 | `src/storefront/modules/catalog/protocols.py` | The only surface `orders` is allowed to depend on |
| 4 | `src/storefront/modules/orders/__init__.py` | Consumer module: `@module(imports=[CatalogModule])` — the load-bearing line |
| 5 | `src/storefront/modules/orders/provider.py` | Cross-module resolution: `container.resolve(ProductCatalogProtocol)` in `boot()` |
| 6 | `src/storefront/modules/orders/services.py` | Business logic depending only on the protocol |
| 7 | `src/storefront/modules/__init__.py` | `MODULES` list wired by the composition root |
| 8 | `tests/test_module.py` | Visibility enforcement: what happens if you remove the import |

```
examples/storefront/
├── src/storefront/
│   ├── app.py                        # ⭐ composition root (start here)
│   ├── main.py                       # entry point / lifecycle
│   ├── modules/
│   │   ├── __init__.py               # MODULES = [CatalogModule, OrdersModule]
│   │   ├── catalog/                  # bounded context: product data + pricing
│   │   │   ├── __init__.py           # @module(exports=[ProductCatalogProtocol])
│   │   │   ├── protocols.py          # ProductCatalogProtocol — the exported contract
│   │   │   ├── domain.py             # Product value type
│   │   │   ├── exceptions.py         # ProductNotFoundError
│   │   │   ├── services.py           # ProductCatalogService (private — never imported elsewhere)
│   │   │   ├── controllers.py        # GET /api/catalog/*
│   │   │   └── provider.py           # CatalogProvider
│   │   └── orders/                   # bounded context: order placement
│   │       ├── __init__.py           # @module(imports=[CatalogModule])
│   │       ├── protocols.py          # OrderServiceProtocol
│   │       ├── domain.py             # Order, OrderLine value types
│   │       ├── exceptions.py         # OrderError hierarchy
│   │       ├── services.py           # OrderService(catalog: ProductCatalogProtocol)
│   │       ├── controllers.py        # /api/orders/*
│   │       └── provider.py           # OrdersProvider — resolves the catalog protocol
│   └── ui/
│       ├── pages.py                  # Static serving routes
│       ├── static/app.js             # Vanilla JS client
│       └── views/storefront.html     # Single-page console
├── application.yaml                  # web config
└── tests/                            # module, provider, and API tests
```

## REST API

```bash
curl localhost:8103/api/catalog/products                 # seeded product list
curl localhost:8103/api/catalog/products/MUG-001          # one product
curl -X POST localhost:8103/api/orders \
  -H 'Content-Type: application/json' \
  -d '{"customer": "Riley", "items": [{"sku": "MUG-001", "qty": 2}]}'
curl localhost:8103/api/orders                            # list placed orders
curl -X POST localhost:8103/api/orders/demo/run           # one-click demo order
```

## Tests

```bash
uv run pytest examples/storefront/tests -q
```

- `test_provider.py` — pure unit tests for `ProductCatalogService` and
  `OrderService`, no DI container.
- `test_api.py` — HTTP round-trip through the real, wired application.
- `test_module.py` — boots the real composition root and asserts
  `orders` resolves `ProductCatalogProtocol`; separately proves the
  module compiler raises `ModuleVisibilityError` if `OrdersModule`'s
  `imports=[CatalogModule.configure()]` is removed.
