from typing import Any

class ModelRepository:
    def __init__(self, model_class: type[Any], provider: Any) -> None: ...

__all__ = ["ModelRepository"]
