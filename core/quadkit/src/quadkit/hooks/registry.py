"""HookRegistry — core hook system for framework extensibility."""

from __future__ import annotations

import asyncio
from threading import Lock
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.hooks import HookPriority
from quadkit.hooks.types import HookEntry
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class HookRegistry:
    """Named hook registry for framework extensibility.

    Thread-safe registry for action hooks (fire-and-forget, error-isolated)
    and filter hooks (value-pipeline, error-propagating) with priority ordering.

    Read operations (``has_*``, ``call_action``, ``apply_filter``) are lock-free — they
    snapshot the handler list and iterate the snapshot. Write operations
    (``register_*``, ``unregister_*``) acquire the lock.

    Args:
        name: Registry name used in structured log output. Defaults to
            ``"default"``.

    Example::

        hooks = HookRegistry("app")

        @hooks.action("before_request", priority=HookPriority.EARLY)
        async def log_request(**kwargs: Any) -> None:
            logger.info("incoming", path=kwargs["path"])

        await hooks.call_action("before_request", path="/api/users")
    """

    __slots__ = ("_actions", "_filters", "_lock", "_name")

    def __init__(self, name: str = "default") -> None:
        self._name = name
        self._lock = Lock()
        self._actions: dict[str, list[HookEntry]] = {}
        self._filters: dict[str, list[HookEntry]] = {}

    # -- Registration -------------------------------------------------------

    def register_action(
        self,
        hook_name: str,
        handler: Callable[..., Any],
        priority: int = HookPriority.NORMAL,
        *,
        once: bool = False,
    ) -> None:
        """Register an action handler for the given hook.

        Args:
            hook_name: The hook point name.
            handler: Callable to invoke. Can be sync or async.
            priority: Lower values run first. Defaults to
                ``HookPriority.NORMAL`` (100).
            once: If True, auto-remove handler after first invocation.
        """
        entry = HookEntry(priority=priority, handler=handler, once=once)
        with self._lock:
            entries = self._actions.setdefault(hook_name, [])
            entries.append(entry)
            entries.sort(key=lambda e: e.priority)
        logger.debug(
            "registered_action_hook",
            registry=self._name,
            hook=hook_name,
            handler=getattr(handler, "__qualname__", repr(handler)),
            priority=priority,
            once=once,
        )

    def register_filter(
        self,
        hook_name: str,
        handler: Callable[..., Any],
        priority: int = HookPriority.NORMAL,
        *,
        once: bool = False,
    ) -> None:
        """Register a filter handler for the given hook.

        Filter handlers receive a value as the first positional argument
        and must return the (possibly transformed) value.

        Args:
            hook_name: The hook point name.
            handler: Callable that receives and returns a value.
            priority: Lower values run first. Defaults to
                ``HookPriority.NORMAL`` (100).
            once: If True, auto-remove handler after first invocation.
        """
        entry = HookEntry(priority=priority, handler=handler, once=once)
        with self._lock:
            entries = self._filters.setdefault(hook_name, [])
            entries.append(entry)
            entries.sort(key=lambda e: e.priority)
        logger.debug(
            "registered_filter_hook",
            registry=self._name,
            hook=hook_name,
            handler=getattr(handler, "__qualname__", repr(handler)),
            priority=priority,
            once=once,
        )

    # -- Unregistration -----------------------------------------------------

    def unregister_action(self, hook_name: str, handler: Callable[..., Any]) -> bool:
        """Remove an action handler from a hook.

        Args:
            hook_name: The hook point name.
            handler: The handler to remove (identity comparison).

        Returns:
            True if the handler was found and removed.
        """
        with self._lock:
            entries = self._actions.get(hook_name, [])
            original_len = len(entries)
            self._actions[hook_name] = [e for e in entries if e.handler is not handler]
            return len(self._actions.get(hook_name, [])) < original_len

    def unregister_filter(self, hook_name: str, handler: Callable[..., Any]) -> bool:
        """Remove a filter handler from a hook.

        Args:
            hook_name: The hook point name.
            handler: The handler to remove (identity comparison).

        Returns:
            True if the handler was found and removed.
        """
        with self._lock:
            entries = self._filters.get(hook_name, [])
            original_len = len(entries)
            self._filters[hook_name] = [e for e in entries if e.handler is not handler]
            return len(self._filters.get(hook_name, [])) < original_len

    # -- Execution ----------------------------------------------------------

    async def call_action(self, hook_name: str, **kwargs: Any) -> None:
        """Invoke all action handlers for the named hook.

        Handlers run sequentially in priority order. Errors in individual
        handlers are logged but do not prevent subsequent handlers from running.

        Once-handlers are removed after they fire (even if they raise).

        Args:
            hook_name: The hook point name.
            **kwargs: Arguments passed to each handler.
        """
        entries = list(self._actions.get(hook_name, []))

        if not entries:
            return

        fired_once: list[HookEntry] = []
        for entry in entries:
            try:
                result = entry.handler(**kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001
                logger.exception(
                    "action_hook_error",
                    registry=self._name,
                    hook=hook_name,
                    handler=getattr(entry.handler, "__qualname__", repr(entry.handler)),
                )
            if entry.once:
                fired_once.append(entry)

        if fired_once:
            self._remove_entries(self._actions, hook_name, fired_once)

    async def apply_filter(self, hook_name: str, value: Any, **kwargs: Any) -> Any:
        """Pass a value through all filter handlers for the named hook.

        Each handler receives the value (possibly transformed by prior
        handlers) and must return the new value. Handlers run sequentially
        in priority order.

        Once-handlers are removed after they fire (even if they raise).
        Errors abort the pipeline and re-raise to the caller.

        Args:
            hook_name: The hook point name.
            value: The initial value to filter.
            **kwargs: Additional arguments passed to each handler.

        Returns:
            The final filtered value.
        """
        entries = list(self._filters.get(hook_name, []))

        if not entries:
            return value

        fired_once: list[HookEntry] = []
        for entry in entries:
            try:
                result = entry.handler(value, **kwargs)
                if asyncio.iscoroutine(result):
                    value = await result
                else:
                    value = result
            except Exception:  # noqa: BLE001 — filter hooks must not crash callers
                if entry.once:
                    fired_once.append(entry)
                if fired_once:
                    self._remove_entries(self._filters, hook_name, fired_once)
                logger.exception(
                    "filter_hook_error",
                    registry=self._name,
                    hook=hook_name,
                    handler=getattr(entry.handler, "__qualname__", repr(entry.handler)),
                )
                raise
            if entry.once:
                fired_once.append(entry)

        if fired_once:
            self._remove_entries(self._filters, hook_name, fired_once)
        return value

    # -- Introspection ------------------------------------------------------

    def has_action(self, hook_name: str) -> bool:
        """Check if any action handlers are registered for a hook.

        Args:
            hook_name: The hook point name.

        Returns:
            True if at least one handler is registered.
        """
        return bool(self._actions.get(hook_name))

    def has_filter(self, hook_name: str) -> bool:
        """Check if any filter handlers are registered for a hook.

        Args:
            hook_name: The hook point name.

        Returns:
            True if at least one handler is registered.
        """
        return bool(self._filters.get(hook_name))

    def action_names(self) -> list[str]:
        """List all registered action hook names.

        Returns:
            List of hook names that have at least one action handler.
        """
        return [k for k, v in self._actions.items() if v]

    def filter_names(self) -> list[str]:
        """List all registered filter hook names.

        Returns:
            List of hook names that have at least one filter handler.
        """
        return [k for k, v in self._filters.items() if v]

    def clear(self, hook_name: str | None = None) -> None:
        """Clear all handlers, or handlers for a specific hook.

        Args:
            hook_name: If provided, clear only this hook. Otherwise clear all.
        """
        with self._lock:
            if hook_name is not None:
                self._actions.pop(hook_name, None)
                self._filters.pop(hook_name, None)
            else:
                self._actions.clear()
                self._filters.clear()

    # -- Decorator API ------------------------------------------------------

    def action(
        self,
        hook_name: str,
        *,
        priority: int = HookPriority.NORMAL,
        once: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register an action handler.

        Returns the handler unchanged so it can still be called directly.

        Args:
            hook_name: The hook point name.
            priority: Lower values run first. Defaults to
                ``HookPriority.NORMAL``.
            once: If True, auto-remove handler after first invocation.

        Returns:
            Decorator that registers the handler and returns it unchanged.

        Example::

            @hooks.action("before_request", priority=HookPriority.EARLY)
            async def log_request(**kwargs: Any) -> None:
                logger.info("request", path=kwargs["path"])
        """

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.register_action(hook_name, handler, priority, once=once)
            return handler

        return decorator

    def filter(
        self,
        hook_name: str,
        *,
        priority: int = HookPriority.NORMAL,
        once: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a filter handler.

        Returns the handler unchanged so it can still be called directly.

        Args:
            hook_name: The hook point name.
            priority: Lower values run first. Defaults to
                ``HookPriority.NORMAL``.
            once: If True, auto-remove handler after first invocation.

        Returns:
            Decorator that registers the handler and returns it unchanged.

        Example::

            @hooks.filter("transform_response")
            async def add_headers(value: Any, **kwargs: Any) -> Any:
                value.headers["X-Custom"] = "yes"
                return value
        """

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.register_filter(hook_name, handler, priority, once=once)
            return handler

        return decorator

    # -- Internal helpers ---------------------------------------------------

    def _remove_entries(
        self,
        store: dict[str, list[HookEntry]],
        hook_name: str,
        to_remove: list[HookEntry],
    ) -> None:
        """Remove specific entries from a hook's handler list under lock.

        Uses ``id()`` comparison to identify exact ``HookEntry`` instances
        (each ``register_*`` call creates a unique object).
        """
        remove_ids = {id(e) for e in to_remove}
        with self._lock:
            entries = store.get(hook_name, [])
            store[hook_name] = [e for e in entries if id(e) not in remove_ids]

    def __repr__(self) -> str:
        """Display registry name and per-hook handler counts."""
        action_parts = ", ".join(
            f"{name}({len(handlers)} handlers)"
            for name, handlers in self._actions.items()
            if handlers
        )
        filter_parts = ", ".join(
            f"{name}({len(handlers)} handlers)"
            for name, handlers in self._filters.items()
            if handlers
        )
        sections = []
        if action_parts:
            sections.append(f"actions=[{action_parts}]")
        if filter_parts:
            sections.append(f"filters=[{filter_parts}]")
        return f"HookRegistry({self._name!r}, {', '.join(sections)})"
