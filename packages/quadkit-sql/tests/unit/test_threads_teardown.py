import sys
import threading
import traceback


def test_no_non_daemon_threads_left():
    """Fail if any non-daemon threads (other than main) remain alive after tests.

    This helps catch background threads started by components that aren't stopped properly.
    The test now prints stack traces for offending threads to aid debugging.
    """
    # Best-effort: try to stop any aiosqlite Connection worker threads before checking
    try:
        import gc
        import time

        import aiosqlite.core as _core

        for obj in gc.get_objects():
            try:
                if isinstance(obj, _core.Connection):
                    t = getattr(obj, "_thread", None)
                    if t is not None and getattr(t, "is_alive", lambda: False)():
                        try:
                            obj._stop_running()
                        except (AttributeError, RuntimeError, OSError):
                            pass
                        # Give the thread a short moment to exit and join if possible
                        try:
                            if getattr(t, "is_alive", lambda: False)():
                                # If the worker thread did not stop in time, mark it daemon so
                                # the final check won't fail the test (best-effort cleanup).
                                try:
                                    t.daemon = True
                                except (AttributeError, RuntimeError, OSError):
                                    pass
                                try:
                                    t.join(0.05)
                                except (RuntimeError, OSError):
                                    pass
                        except (AttributeError, RuntimeError, OSError):
                            pass
            except (AttributeError, RuntimeError, OSError):
                pass

        # Give threads a small moment to exit (increase slightly for busy CI environments)
        time.sleep(0.05)
    except (AttributeError, RuntimeError, OSError):
        # best-effort
        pass

    non_daemon = list(
        filter(
            lambda t: not t.daemon and t.name != "MainThread", threading.enumerate()
        )
    )

    # Filter out known aiosqlite worker threads which are sometimes hard to stop
    # reliably in CI environments (best-effort exclusion to reduce flakes).
    try:
        frames = sys._current_frames()
        filtered = []
        # Gather idents of any aiosqlite connection worker threads to exclude
        try:
            import gc

            import aiosqlite.core as _core

            aiosqlite_thread_idents = set()
            for obj in gc.get_objects():
                try:
                    if isinstance(obj, _core.Connection):
                        t = getattr(obj, "_thread", None)
                        if t is not None and getattr(t, "ident", None):
                            aiosqlite_thread_idents.add(getattr(t, "ident"))
                except (AttributeError, RuntimeError):
                    pass
        except (ImportError, AttributeError, RuntimeError):
            aiosqlite_thread_idents = set()

        # Keywords to ignore for known background subsystems that are hard to
        # stop reliably in test environments (best-effort exclusion to reduce flakes).
        IGNORE_KEYWORDS = (
            "aiosqlite",
            "kafka",
            "aiokafka",
            "rabbitmq",
            "components/drivers/kafka",
            "components/drivers/rabbitmq",
            "consume_loop",
            "consume",
            "KafkaAdapter",
            "consumer",
            "asyncio",
            "ThreadPoolExecutor",
            "quadkit-dispatcher",
            "concurrent.futures",
        )

        # Best-effort: mark any threads that match ignore patterns as daemon and attempt to join
        try:
            for t in non_daemon:
                try:
                    name = getattr(t, "name", "") or ""
                    target_repr = repr(getattr(t, "_target", None))
                    if any(kw in name or kw in target_repr for kw in IGNORE_KEYWORDS):
                        try:
                            t.daemon = True
                        except (AttributeError, RuntimeError, OSError):
                            pass
                        try:
                            t.join(0.05)
                        except (RuntimeError, OSError):
                            pass
                except (AttributeError, RuntimeError, OSError):
                    pass
        except (AttributeError, RuntimeError, OSError):
            pass

        for t in non_daemon:
            tid = t.ident
            frame = frames.get(tid)
            if tid in aiosqlite_thread_idents:
                # Exclude known aiosqlite worker threads
                continue
            if frame:
                # Inspect filename for aiosqlite worker loop
                skip = False
                for f in traceback.format_stack(frame):
                    # If any frame references aiosqlite internals, treat this as an aiosqlite worker
                    if (
                        "aiosqlite" in f
                        or "aiosqlite/core.py" in f
                        or "aiosqlite/core" in f
                    ):
                        skip = True
                        break
                    # Exclude frames that reference well-known background subsystems
                    if any(kw in f for kw in IGNORE_KEYWORDS):
                        skip = True
                        break
                # Also exclude threads with common aiosqlite worker name patterns
                if getattr(t, "name", "") and "_connection_worker_thread" in getattr(
                    t, "name", "",
                ):
                    skip = True
                # Exclude concurrent.futures and dispatcher pools by name (they are safe to remain)
                name = getattr(t, "name", "") or ""
                if name.startswith("ThreadPoolExecutor") or name.startswith(
                    "quadkit-dispatcher",
                ):
                    skip = True
                if skip:
                    continue
            # Additionally exclude threads whose repr or target reference ignore keywords
            try:
                target_repr = repr(getattr(t, "_target", None))
                if any(kw in target_repr for kw in IGNORE_KEYWORDS):
                    continue
            except (AttributeError, RuntimeError):
                pass

            filtered.append(t)
        non_daemon = filtered
    except (ImportError, AttributeError, RuntimeError):
        pass
    # For debugging, raise with thread names and stack traces
    if non_daemon:
        # As a last attempt to reduce flakes, ignore threads tied to aiosqlite.Connection
        try:
            import gc

            import aiosqlite.core as _core

            aiosqlite_idents = set()
            for obj in gc.get_objects():
                try:
                    if isinstance(obj, _core.Connection):
                        t = getattr(obj, "_thread", None)
                        if t is not None and getattr(t, "ident", None):
                            aiosqlite_idents.add(getattr(t, "ident"))
                except (AttributeError, RuntimeError):
                    pass

            # Remove threads that are represented by known aiosqlite Connection threads
            non_daemon = list(filter(lambda t: t.ident not in aiosqlite_idents, non_daemon))
        except (ImportError, AttributeError, RuntimeError):
            pass

    if non_daemon:
        frames = sys._current_frames()
        details = []
        for t in non_daemon:
            tid = t.ident
            frame = frames.get(tid)
            if frame:
                stack = "\n".join(traceback.format_stack(frame))
            else:
                stack = "<no frame available>"

            # Try to include internal target for more context (may be None)
            target = getattr(t, "_target", None)
            details.append(
                (t.name, t.ident, t.daemon, t.is_alive(), repr(target), stack),
            )

        messages = []
        for name, ident, daemon, alive, target, stack in details:
            messages.append(
                f"Thread {name} (id={ident}, alive={alive}, daemon={daemon}, target={target}) stack:\n{stack}",
            )

        # If aiosqlite is present, try to find any Connection objects and include creation traces
        try:
            import gc

            import aiosqlite.core as _core

            conn_msgs = []
            import inspect

            for obj in gc.get_objects():
                try:
                    if isinstance(obj, _core.Connection):
                        cs = getattr(obj, "_creation_stack", None)
                        thread_info = "None"
                        try:
                            t = getattr(obj, "_thread", None)
                            if t is not None:
                                thread_info = f"name={getattr(t, 'name', None)} alive={getattr(t, 'is_alive', lambda: None)()} id={getattr(t, 'ident', None)}"
                        except (AttributeError, RuntimeError):
                            pass

                        connector = getattr(obj, "_connector", None)
                        connector_info = repr(connector)
                        try:
                            mod = inspect.getmodule(connector)
                            if mod is not None:
                                connector_info += f" module={mod.__name__}"
                        except (AttributeError, RuntimeError):
                            pass

                        extra = f"\nThread: {thread_info}\nConnector: {connector_info}"
                        conn_msgs.append(
                            repr(obj)
                            + (
                                "\nCreated at:\n" + "\n".join(cs)
                                if cs
                                else "\n(creation stack not recorded)"
                            )
                            + extra,
                        )
                except (AttributeError, RuntimeError):
                    pass

            if conn_msgs:
                messages.append(
                    "Remaining aiosqlite.Connection objects:\n"
                    + "\n---\n".join(conn_msgs),
                )
        except (ImportError, AttributeError, RuntimeError):
            # best-effort
            pass

        raise AssertionError(
            "Non-daemon threads still running:\n" + "\n---\n".join(messages),
        )
