# Modules

A **module** bundles everything one feature needs — providers,
controllers, exports — into a single registrable unit. Applications are
assembled from modules; they are how the framework knows what exists.

## The idea

```python
app = Application()
app.add_modules([WebModule.configure(controllers=[HelloController])])
```

`WebModule.configure(...)` declares the web feature and its controllers
in one call. `Application.add_modules([...])` attaches modules to the
app; registration only records intent — the container stays empty and
no provider boots until the application
[starts](./lifecycle.md).

When the app starts, providers boot in dependency order (in parallel
where possible), so a module can rely on an earlier-registered module's
services without ordering hacks.

## Configured vs. authored modules

Two shapes cover most cases:

- **Configured framework modules** — `WebModule.configure(...)` above.
  Framework packages ship modules with sane defaults that take
  declarative configuration.
- **Authored application modules** — as an app grows, group its own
  providers (and controllers) into feature modules the same way, keeping
  `create_app()` a list of features rather than a wiring script.

A controller does not need to know the module system: it is a plain
class collected by the module that owns it, constructed at request time
with [dependency injection](./dependency-injection.md).

## One module, one responsibility

The practical rule that keeps assemblies readable:

- A module owns its registrations — other modules *consume* them
  through contracts, never rebind them (the web module owns web config;
  your module must not).
- Features stay movable: add or remove a module line in `add_modules`
  and the app gains or loses the whole feature, routes included.

The [example-hub](https://github.com/dbtinoy-/quadkit/tree/main/examples/example-hub) application shows the
pattern at a real project's scale.

Next: [lifecycle](./lifecycle.md) — the exact start/stop sequence those
modules go through.
