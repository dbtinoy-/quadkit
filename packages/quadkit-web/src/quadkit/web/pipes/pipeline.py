"""PipeProtocol pipeline for running pipes on parameters.

The pipeline runs pipes in order, transforming each parameter value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.web.protocols import ParamMetadata, PipeProtocol


class PipePipeline:
    """Pipeline that runs pipes on handler parameters.

    Processes parameters through registered pipes in order, transforming
    and validating values before they reach the handler.
    """

    def __init__(self, pipes: dict[str, list[PipeProtocol]] | None = None):
        """Initialize the pipe pipeline.

        Args:
            pipes: Optional dict mapping parameter names to lists of pipes.
        """
        self._pipes: dict[str, list[PipeProtocol]] = pipes or {}

    def add_pipe(self, param_name: str, pipe: PipeProtocol) -> None:
        """Add a pipe for a parameter.

        Args:
            param_name: The name of the parameter.
            pipe: The pipe to add.
        """
        if param_name not in self._pipes:
            self._pipes[param_name] = []
        if pipe not in self._pipes[param_name]:
            self._pipes[param_name].append(pipe)

    def remove_pipe(self, param_name: str, pipe: PipeProtocol) -> None:
        """Remove a pipe for a parameter.

        Args:
            param_name: The name of the parameter.
            pipe: The pipe to remove.
        """
        if param_name in self._pipes:
            if pipe in self._pipes[param_name]:
                self._pipes[param_name].remove(pipe)
            if not self._pipes[param_name]:
                del self._pipes[param_name]

    def get_pipes(self, param_name: str) -> list[PipeProtocol]:
        """Get pipes for a parameter.

        Args:
            param_name: The name of the parameter.

        Returns:
            List of pipes for the parameter.
        """
        return list(self._pipes.get(param_name, []))

    async def transform(
        self,
        param_name: str,
        value: Any,
        metadata: ParamMetadata,
    ) -> Any:
        """Transform a parameter value through its pipes.

        Args:
            param_name: The name of the parameter.
            value: The value to transform.
            metadata: Metadata about the parameter.

        Returns:
            Transformed value.
        """
        pipes = self.get_pipes(param_name)

        if not pipes:
            return value

        result = value
        for pipe in pipes:
            result = await pipe.transform(result, metadata)

        return result

    def __len__(self) -> int:
        """Return total number of pipes."""
        return sum(len(p) for p in self._pipes.values())


__all__ = ["PipePipeline"]
