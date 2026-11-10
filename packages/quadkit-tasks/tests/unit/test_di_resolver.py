"""Tests for DI container dependency resolution for task handlers."""

from __future__ import annotations

from typing import Annotated, Any

import pytest

from quadkit.di.markers import Named


class _FakeContainer:
    def __init__(self, services: dict[type, Any] | None = None):
        self.services = services or {}
        self.resolved: list[type] = []

    async def resolve(self, service_type: type) -> Any:
        self.resolved.append(service_type)
        if service_type in self.services:
            return self.services[service_type]
        raise LookupError(f"no service for {service_type}")


class _Repo:
    pass


class _Svc:
    pass


class TestResolveDependencies:
    """DI dependency resolution for task handlers."""

    @pytest.mark.asyncio
    async def test_no_container_returns_provided_as_is(self) -> None:  # noqa: D102
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        async def handler(x: int, repo: _Repo) -> None:
            pass

        args, kwargs = await resolve_handler_dependencies(handler, (5,), {}, None)
        assert args == [5]
        assert kwargs == {}

    @pytest.mark.asyncio
    async def test_resolves_missing_annotated_param(self) -> None:  # noqa: D102
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        repo = _Repo()
        container = _FakeContainer({_Repo: repo})

        async def handler(x: int, repo: _Repo) -> None:
            pass

        args, kwargs = await resolve_handler_dependencies(handler, (5,), {}, container)
        assert args == [5]
        assert kwargs == {"repo": repo}
        assert container.resolved == [_Repo]

    @pytest.mark.asyncio
    async def test_provided_kwargs_not_resolved_again(self) -> None:  # noqa: D102
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        repo = _Repo()
        svc = _Svc()
        container = _FakeContainer({_Repo: repo, _Svc: svc})

        async def handler(repo: _Repo, other: _Svc) -> None:
            pass

        args, kwargs = await resolve_handler_dependencies(
            handler, (), {"repo": repo}, container
        )
        assert not args
        assert kwargs["repo"] is repo
        # provided param not re-resolved; missing one still resolved
        assert _Repo not in container.resolved
        assert kwargs["other"] is svc

    @pytest.mark.asyncio
    async def test_unresolvable_param_dropped_silently(self) -> None:  # noqa: D102
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        container = _FakeContainer({})

        async def handler(repo: _Repo) -> None:
            pass

        args, kwargs = await resolve_handler_dependencies(handler, (), {}, container)
        assert args == []
        assert kwargs == {}

    @pytest.mark.asyncio
    async def test_unannotated_param_skipped(self) -> None:  # noqa: D102
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        container = _FakeContainer({})

        def handler(x, repo) -> None:  # noqa: ANN001, ANN001
            pass

        args, kwargs = await resolve_handler_dependencies(handler, (1,), {}, container)
        assert args == [1]
        assert kwargs == {}

    @pytest.mark.asyncio
    async def test_var_positional_and_keyword_skipped(self) -> None:  # noqa: D102
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        svc = _Svc()
        container = _FakeContainer({_Svc: svc})

        async def handler(*args: Any, repo: _Svc, **kwargs: Any) -> None:
            pass

        args, kwargs = await resolve_handler_dependencies(handler, (), {}, container)
        assert args == []
        assert kwargs == {"repo": svc}

    @pytest.mark.asyncio
    async def test_container_none_with_kwargs(self) -> None:  # noqa: D102
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        async def handler(repo: _Repo) -> None:
            pass

        args, kwargs = await resolve_handler_dependencies(
            handler, (), {"repo": _Repo()}, None
        )
        assert args == []
        assert kwargs == {"repo": kwargs["repo"]}

    @pytest.mark.asyncio
    async def test_decorated_handler_unwrapped(self) -> None:  # noqa: D102
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        repo = _Repo()
        container = _FakeContainer({_Repo: repo})

        async def original(x: int, repo: _Repo) -> None:
            pass

        wrapper = lambda: None  # noqa: E731
        wrapper._func = original

        args, kwargs = await resolve_handler_dependencies(wrapper, (7,), {}, container)
        assert args == [7]
        assert kwargs == {"repo": repo}

    @pytest.mark.asyncio
    async def test_string_forward_reference_resolved(self) -> None:  # noqa: D102
        import typing

        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        repo = _Repo()
        container = _FakeContainer({_Repo: repo})

        async def handler(x: int, repo: typing.Any) -> None:
            pass

        # string annotation that resolves via get_type_hints
        args, kwargs = await resolve_handler_dependencies(handler, (1,), {}, container)
        # typing.Any is not a container service — must not crash
        assert args == [1]
        assert "x" not in kwargs

    @pytest.mark.asyncio
    async def test_bound_method_handler(self) -> None:  # noqa: D102
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        repo = _Repo()
        container = _FakeContainer({_Repo: repo})

        class _Worker:
            def job(self, repo: _Repo) -> None:
                pass

        args, kwargs = await resolve_handler_dependencies(
            _Worker().job, (), {}, container
        )
        assert not args
        assert kwargs == {"repo": repo}

    @pytest.mark.asyncio
    async def test_partial_positional_mapping(self) -> None:  # noqa: D102
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        svc = _Svc()
        container = _FakeContainer({_Svc: svc})

        async def handler(a: int, b: str, svc: _Svc) -> None:
            pass

        args, kwargs = await resolve_handler_dependencies(handler, (1,), {}, container)
        # 'a' provided positionally; 'b' unannotated-free (str is not a service)
        # and unresolvable; 'svc' resolved
        assert args == [1]
        assert kwargs.get("svc") is svc


class _RecordingLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def _record(self, level: str, msg: str, *args: Any, **kwargs: Any) -> None:
        rendered = (msg % args) if args else msg
        if kwargs:
            rendered = f"{rendered} {kwargs!r}"
        self.calls.append((level, rendered))

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._record("debug", msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._record("info", msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._record("warning", msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._record("error", msg, *args, **kwargs)


class TestUnresolvableForwardReference:
    """A TYPE_CHECKING-only annotation is warned about without private details."""

    @pytest.mark.asyncio
    async def test_type_checking_only_annotation_warns_and_names_the_param(
        self,
    ) -> None:
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        async def handler(channel: "OnlyUnderTypeChecking") -> None:  # noqa: F821, UP037
            pass

        log = _RecordingLogger()
        container = _FakeContainer({_Svc: _Svc()})
        _, kwargs = await resolve_handler_dependencies(
            handler, (), {}, container, logger_instance=log
        )

        assert "channel" not in kwargs
        warnings = [m for level, m in log.calls if level == "warning"]
        assert warnings, "the swallowed NameError must surface as a warning"
        text = " ".join(warnings)
        assert "task_dependency_annotation_unresolvable" in text
        assert "NameError" in text
        assert "OnlyUnderTypeChecking" not in text


class TestResolverIsQuietInSteadyState:
    """A healthy job must not produce five info lines per execution.

    Found by reading a production log: every scheduled tick printed the
    handler signature, its parameter count, one "attempting" line per
    parameter and one "could not resolve" line for every optional job
    argument such as ``since: str | None = None`` — a line the container
    could never have satisfied.
    """

    @pytest.mark.asyncio
    async def test_a_healthy_handler_logs_nothing_above_debug(self) -> None:
        """Verify a healthy handler emits no log entries above debug."""
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        async def handler(
            account_id: int, repo: _Repo, *, since: str | None = None
        ) -> None:
            pass

        log = _RecordingLogger()
        container = _FakeContainer({_Repo: _Repo()})
        _, kwargs = await resolve_handler_dependencies(
            handler, (7,), {}, container, logger_instance=log
        )

        assert isinstance(kwargs["repo"], _Repo)
        assert "since" not in kwargs, (
            "a job argument with a default is the job's, not the container's"
        )
        assert all(level == "debug" for level, _ in log.calls), log.calls
        assert not any(
            t is not _Repo and t == (str | None) for t in container.resolved
        ), "str | None was never asked of the container"

    @pytest.mark.asyncio
    async def test_required_service_resolution_error_logs_type_only(self) -> None:
        """Do not echo container exception text in dependency warnings."""
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        sentinel = "PRIVATE_CONTAINER_ERROR_SENTINEL /srv/private/tenant-42"

        class _FailingContainer:
            async def resolve(self, service_type: type) -> Any:
                assert service_type is _Repo
                raise LookupError(sentinel)

        async def handler(repo: _Repo) -> None:
            pass

        log = _RecordingLogger()
        _, kwargs = await resolve_handler_dependencies(
            handler, (), {}, _FakeContainer(), logger_instance=log
        )

        assert "repo" not in kwargs
        warnings = [m for level, m in log.calls if level == "warning"]
        assert (
            warnings
            and "task_dependency_unresolved" in warnings[0]
            and "param=repo" in warnings[0]
        )


class TestAnnotatedNamedAndLockManagerBindings:
    """DR-30: Preserve Annotated[..., Named(...)] metadata & LockManagerProtocol DI binding."""

    @pytest.mark.asyncio
    async def test_preserves_annotated_named_qualifier(self) -> None:
        """Preserve Annotated[..., Named(...)] metadata so named registrations resolve."""
        from quadkit.di import Container
        from quadkit.tasks.execution._di_resolver import resolve_handler_dependencies

        primary_repo = _Repo()
        maps_repo = _Repo()
        container = Container()
        container.singleton(_Repo, instance=primary_repo)
        container.singleton(_Repo, instance=maps_repo, name="maps")

        async def handler(
            db: Annotated[_Repo, Named("maps")],
            default_db: _Repo,
        ) -> None:
            pass

        _, kwargs = await resolve_handler_dependencies(handler, (), {}, container)
        assert kwargs["db"] is maps_repo
        assert kwargs["default_db"] is primary_repo

    @pytest.mark.asyncio
    async def test_registers_lock_manager_protocol_alongside_concrete_class(
        self,
    ) -> None:
        """Register LockManagerProtocol singleton alongside concrete LockManager."""
        from quadkit.contracts.core.lock import LockManagerProtocol
        from quadkit.di import Container
        from quadkit.tasks.concurrency.locking import LockManager
        from quadkit.tasks.di.provider import TaskProvider

        container = Container()
        provider = TaskProvider()
        await provider.register(container)

        resolved_proto = await container.resolve(LockManagerProtocol)
        resolved_concrete = await container.resolve(LockManager)
        assert isinstance(resolved_concrete, LockManager)
        assert resolved_proto is resolved_concrete
