"""ProjectionProtocol manager for managing projection lifecycle.

The projection manager handles:
- ProjectionProtocol registration
- Event distribution
- Rebuild coordination
- Checkpoint management
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from quadkit.events.exceptions import (
    ProjectionBuildError,
    ProjectionNotFoundError,
    ProjectionRebuildError,
)
from quadkit.events.projections.base import (
    ProjectionCheckpoint,
    ProjectionProtocol,
    ProjectionStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.events.messages.event import Event
    from quadkit.events.stores.base import EventStoreProtocol

from quadkit.logging import get_logger

logger = get_logger(__name__)


class ProjectionManager:
    """Manages projection lifecycle and event distribution.

    The manager:
    - Registers and tracks projections
    - Distributes events to projections
    - Coordinates rebuilds from event history
    - Manages checkpoints

    Example:
        ```python
        manager = ProjectionManager(event_store)

        # Register projections
        manager.register(OrderSummaryProjection())
        manager.register(InventoryProjection())

        # Process an event (distributes to all relevant projections)
        await manager.process(order_created_event)

        # Rebuild a projection
        await manager.rebuild("order_summary")
        ```
    """

    def __init__(
        self,
        event_store: EventStoreProtocol | None = None,
        checkpoint_store: Any | None = None,
    ):
        """Initialize the projection manager.

        Args:
            event_store: Event store for rebuilds
            checkpoint_store: Storage for checkpoints (dict or CheckpointStore)
        """
        self._event_store = event_store
        self._checkpoint_store = checkpoint_store
        self._checkpoints: dict[str, ProjectionCheckpoint] = {}
        if isinstance(checkpoint_store, dict):
            self._checkpoints = checkpoint_store
        self._projections: dict[str, ProjectionProtocol] = {}
        self._sorted_names: list[str] = []

    def register(self, projection: ProjectionProtocol) -> None:
        """Register a projection."""
        # Restore checkpoint if exists in local dict
        if projection.name in self._checkpoints:
            projection.restore_checkpoint(self._checkpoints[projection.name])

        self._projections[projection.name] = projection
        self._update_graph()

    def _update_graph(self) -> None:
        """Perform topological sort of projections based on depends_on."""
        from collections import deque

        # Build adjacency list
        adj: dict[str, list[str]] = {name: [] for name in self._projections}
        in_degree: dict[str, int] = dict.fromkeys(self._projections, 0)

        for name, proj in self._projections.items():
            for dep in proj.depends_on:
                if dep in adj:
                    adj[dep].append(name)
                    in_degree[name] += 1
                else:
                    # External dependency — we can't sort it but we'll track it in process
                    pass

        # Kahn's algorithm
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        self._sorted_names = []

        while queue:
            u = queue.popleft()
            self._sorted_names.append(u)
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        # Append any remaining (cycles or unsortable) — in-degree won't be 0
        for name in self._projections:
            if name not in self._sorted_names:
                self._sorted_names.append(name)

    def unregister(self, name: str) -> bool:
        """Unregister a projection.

        Args:
            name: ProjectionProtocol name

        Returns:
            True if projection was unregistered
        """
        if name in self._projections:
            del self._projections[name]
            return True
        return False

    def get(self, name: str) -> ProjectionProtocol | None:
        """Get a projection by name.

        Args:
            name: ProjectionProtocol name

        Returns:
            ProjectionProtocol if found
        """
        return self._projections.get(name)

    def get_all(self) -> list[ProjectionProtocol]:
        """Get all registered projections."""
        return list(self._projections.values())

    async def process(self, event: Event, position: int | None = None) -> list[str]:
        """Process an event through all relevant projections in dependency order."""
        processed: list[str] = []
        errors: list[tuple[str, Exception]] = []

        for name in self._sorted_names:
            projection = self._projections[name]

            # Skip paused or errored projections
            if projection.status in (ProjectionStatus.PAUSED, ProjectionStatus.ERROR):
                continue

            # Check if projection handles this event
            if not projection.can_handle(event):
                # Still advance position if we are skipping
                if position is not None:
                    projection.advance(position)
                    await self._save_checkpoint(projection)
                continue

            # MF-07: Check external dependencies if CheckpointStore is available
            if self._checkpoint_store and hasattr(
                self._checkpoint_store, "get_checkpoint"
            ):
                dependencies_satisfied = True
                for dep in projection.depends_on:
                    if dep not in self._projections:
                        dep_pos = await self._checkpoint_store.get_checkpoint(dep) or 0
                        if position is not None and dep_pos < position:
                            # Dependency not yet caught up
                            logger.debug(
                                "ProjectionProtocol %s waiting for dependency %s to reach %d",
                                name,
                                dep,
                                position,
                            )
                            dependencies_satisfied = False
                            break

                if not dependencies_satisfied:
                    # Logic choice: skip for now (it will be retried in a catch-up or next bus push)
                    # Or we could raise/block, but skipping is safer for non-blocking IO.
                    continue

            try:
                await projection.apply(event)

                # Update checkpoint
                if position is not None:
                    projection.advance(position)
                    await self._save_checkpoint(projection)

                processed.append(name)

            except (
                RuntimeError,
                ValueError,
                TypeError,
                AttributeError,
                OSError,
            ) as e:
                projection.set_error(str(e))
                errors.append((name, e))

        # Raise if any errors (after processing all projections)
        if errors and len(errors) == 1:
            name, error = errors[0]
            raise ProjectionBuildError(
                f"Projection {name!r} failed on {type(event).__name__}: {error}",
            )

        return processed

    async def _save_checkpoint(self, projection: ProjectionProtocol) -> None:
        """Save projection checkpoint to local cache and/or CheckpointStore."""
        checkpoint = projection.checkpoint
        self._checkpoints[projection.name] = checkpoint

        if self._checkpoint_store and hasattr(
            self._checkpoint_store, "save_checkpoint"
        ):
            await self._checkpoint_store.save_checkpoint(
                projection.name,
                checkpoint.position,
            )

    async def process_batch(
        self,
        events: list[tuple[Event, int]],
        parallel: bool = False,
    ) -> dict[str, int]:
        """Process a batch of events.

        Args:
            events: List of (event, position) tuples
            parallel: Whether to process projections in parallel

        Returns:
            Dict of projection name to count of events processed
        """
        # `parallel` is a reserved API parameter for future use; keep it to
        # preserve the public signature but mark as used to satisfy linters.
        _ = parallel

        counts: dict[str, int] = {}

        for event, position in events:
            processed = await self.process(event, position)
            for name in processed:
                counts[name] = counts.get(name, 0) + 1

        return counts

    async def rebuild(
        self,
        name: str,
        from_position: int = 0,
        batch_size: int = 100,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> int:
        """Rebuild a projection from event history.

        M-22: Checkpoint is saved after EVERY event so a crash mid-rebuild
        can be resumed via ``resume_rebuild()`` from the last checkpoint.

        Args:
            name: ProjectionProtocol name.
            from_position: Starting position (0 for full rebuild).
            batch_size: Events to process per batch.
            on_progress: Optional callback invoked after each event is applied.
                Receives ``(events_processed, current_position)`` so callers
                can log progress or update a UI indicator.  The callback is
                called synchronously in the event loop — keep it lightweight.

        Returns:
            Number of events processed

        Raises:
            ProjectionNotFoundError: If projection not found
            ProjectionRebuildError: If rebuild fails
        """
        projection = self._projections.get(name)
        if not projection:
            raise ProjectionNotFoundError(name)

        if not self._event_store:
            raise ProjectionRebuildError(
                f"Rebuild failed for {name!r}: No event store configured"
            )

        # Set rebuilding status
        projection.set_rebuilding()

        try:
            # Reset projection state if full rebuild
            if from_position == 0:
                await projection.reset()
                projection.checkpoint.position = 0

            count = 0
            async for event in self._event_store.stream_all(  # type: ignore[attr-defined]
                from_position=from_position,
                batch_size=batch_size,
            ):
                if projection.can_handle(event):
                    # M-05: Idempotent skip — skip events already applied
                    event_position = getattr(event, "sequence_number", None) or 0
                    if event_position and event_position <= projection.position:
                        continue  # already processed; skip for idempotency

                    await projection.apply(event)
                    count += 1

                # M-22: Advance position and save checkpoint after EACH event
                position = getattr(event, "sequence_number", None)
                if position:
                    projection.advance(position)
                    await self._save_checkpoint(projection)  # per-event checkpoint
                    if on_progress is not None:
                        on_progress(count, position)

            # Restore status
            projection.resume()

            return count

        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            with contextlib.suppress(OSError, ValueError, TypeError):
                logger.exception("Rebuild failed for %s", name)
            projection.set_error(str(e))
            raise ProjectionRebuildError(f"Rebuild failed for {name!r}: {e}") from e

    async def resume_rebuild(self, name: str, batch_size: int = 100) -> int:
        """Resume a rebuild from the projection's last checkpoint (M-22).

        If the rebuild crashed mid-way, this continues from the last saved
        position rather than restarting from zero.

        Args:
            name: ProjectionProtocol name
            batch_size: Events per batch

        Returns:
            Number of additional events processed
        """
        projection = self._projections.get(name)
        if not projection:
            raise ProjectionNotFoundError(name)

        last_position = projection.position
        logger.info("Resuming rebuild for %s from position %d", name, last_position)
        return await self.rebuild(
            name, from_position=last_position, batch_size=batch_size
        )

    async def rebuild_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        parallel: bool = False,
    ) -> dict[str, int]:
        """Rebuild all projections.

        M-22: ``parallel=True`` rebuilds independent projections concurrently.

        Args:
            from_position: Starting position
            batch_size: Batch size
            parallel: Rebuild projections concurrently (default: sequential)

        Returns:
            Dict of projection name to events processed
        """
        import asyncio

        results: dict[str, int] = {}

        if parallel:
            tasks = {
                name: asyncio.create_task(
                    self.rebuild(name, from_position, batch_size),
                )
                for name in self._projections
            }
            for name, task in tasks.items():
                try:
                    results[name] = await task
                except (ProjectionRebuildError, ProjectionNotFoundError, RuntimeError):
                    with contextlib.suppress(OSError, ValueError, TypeError):
                        logger.exception("Parallel rebuild for %s failed", name)
                    results[name] = -1
        else:
            for name in self._projections:
                try:
                    count = await self.rebuild(name, from_position, batch_size)
                    results[name] = count
                except (ProjectionRebuildError, ProjectionNotFoundError, RuntimeError):
                    with contextlib.suppress(OSError, ValueError, TypeError):
                        logger.exception("Rebuild for %s failed", name)
                    results[name] = -1

        return results

    async def reset_all(self) -> None:
        """Reset all registered projections (M-16)."""
        for projection in self._projections.values():
            await projection.reset()
            projection.checkpoint.position = 0
            await self._save_checkpoint(projection)

    def pause(self, name: str) -> bool:
        """Pause a projection.

        Args:
            name: ProjectionProtocol name

        Returns:
            True if projection was paused
        """
        projection = self._projections.get(name)
        if projection:
            projection.pause()
            return True
        return False

    def resume(self, name: str) -> bool:
        """Resume a projection.

        Args:
            name: ProjectionProtocol name

        Returns:
            True if projection was resumed
        """
        projection = self._projections.get(name)
        if projection:
            projection.resume()
            return True
        return False

    def get_status(self, name: str) -> dict | None:
        """Get projection status.

        Args:
            name: ProjectionProtocol name

        Returns:
            Status dict or None
        """
        projection = self._projections.get(name)
        if not projection:
            return None

        return {
            "name": projection.name,
            "status": projection.status.value,
            "position": projection.position,
            "handles": [t.__name__ for t in projection.handles],
            "error": projection.error,
        }


__all__ = ["ProjectionManager"]
