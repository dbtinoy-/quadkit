"""OpenAPI specification generator for quadkit-web

This is a lightweight implementation that inspects controller route metadata
and constructs a minimal OpenAPI 3.0.3 specification including component
schemas for Pydantic response models (when available).
"""

from __future__ import annotations

import inspect
import re
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)


class OpenAPIGenerator:
    """Lightweight OpenAPI 3.0.3 specification generator.

    Inspects controller route metadata collected by the routing layer and
    produces a minimal OpenAPI spec dict that can be served as JSON at
    ``/openapi.json`` or rendered via Swagger/Redoc UI.

    Supports Pydantic response models (``$ref`` component schemas), built-in
    Python types (inline schemas), and ``list[Model]`` generic aliases.

    Register through the :class:`~quadkit.web.di.provider.WebProvider` so
    the spec is generated lazily from the final route table::

        # Via WebProvider (automatic)
        # The provider calls OpenAPIGenerator(title=config.title, ...) and
        # mounts /openapi.json and /docs routes automatically.

    Args:
        title: API title displayed in generated documentation.
        version: API version string (e.g. ``"1.0.0"``).
        description: Optional long-form API description shown in the UI.
    """

    def __init__(
        self,
        title: str,
        version: str,
        description: str | None = None,
    ) -> None:
        """
        Args:
            title: API title displayed in generated documentation.
            version: API version string (e.g. ``"1.0.0"``).
            description: Optional long-form API description shown in the UI.
        """
        self.title = title
        self.version = version
        self.description = description or ""
        self.paths: dict[str, Any] = {}
        self.components: dict[str, Any] = {"schemas": {}}

    def _get_schema_for_model(self, model: Any) -> dict[str, Any]:
        """Get an OpenAPI schema for a model or type.

        Handles Pydantic models (with components/$ref), built-in types (inline),
        and GenericAliases (like list[Model]).
        """
        if model is None:
            return {"type": "object"}

        # Handle basic built-in types
        if model is str:
            return {"type": "string"}
        if model is int:
            return {"type": "integer"}
        if model is float:
            return {"type": "number"}
        if model is bool:
            return {"type": "boolean"}
        if model is list:
            return {"type": "array", "items": {"type": "object"}}
        if model is dict:
            return {"type": "object"}

        # Handle GenericAlias (list[Breed], dict[str, Any])
        origin = getattr(model, "__origin__", None)
        if origin is list:
            args = getattr(model, "__args__", [])
            items = self._get_schema_for_model(args[0]) if args else {"type": "object"}
            return {"type": "array", "items": items}
        if origin is dict:
            return {"type": "object"}

        # Handle Pydantic models (V2)
        if hasattr(model, "model_json_schema"):
            name = getattr(model, "__name__", "AnonymousModel")
            if name not in self.components["schemas"]:
                try:
                    schema = model.model_json_schema()
                    # If there is a $defs section, merge it into components
                    if "$defs" in schema:
                        defs = schema.pop("$defs")
                        for def_name, def_schema in defs.items():
                            self.components["schemas"][def_name] = def_schema
                    self.components["schemas"][name] = schema
                except (TypeError, ValueError, AttributeError) as e:
                    logger.warning("Failed to generate JSON schema for %s: %s", name, e)
                    self.components["schemas"][name] = {"type": "object"}
            return {"$ref": f"#/components/schemas/{name}"}

        # Fallback for other classes with __name__
        name = getattr(model, "__name__", None)
        if name:
            if name not in self.components["schemas"]:
                self.components["schemas"][name] = {"type": "object"}
            return {"$ref": f"#/components/schemas/{name}"}

        return {"type": "object"}

    def _normalize_path(self, path: Any) -> str:
        """Ensures path is a string and replaces path parameters with OpenAPI format."""
        if not isinstance(path, (str, bytes)):
            path = str(path)
        # Strip Starlette-style type hints from path parameters: {param:type} -> {param}
        return re.sub(r"{([^}:]+):[^}]+}", r"{\1}", path)

    def _extract_path_parameters(self, path: Any) -> list[dict[str, Any]]:
        path = str(path)
        params = []
        for match in re.finditer(r"{([^}]+)}", path):
            name = match.group(1).split(":")[0]
            params.append(
                {
                    "name": name,
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
            )
        return params

    def _extract_operation_parameters(
        self,
        handler: Any,
        path_params: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract parameters from handler metadata and signature."""
        params = list(path_params)

        # 1. From _param_metadata (decorators like @query(func))
        metadata = list(getattr(handler, "_param_metadata", []))

        # 2. From signature defaults (decorators like p: str = header(...))
        try:
            sig = inspect.signature(handler)
            for name, param in sig.parameters.items():
                info = getattr(param.default, "_quadkit_param_info", None)
                if info:
                    # Avoid duplicates if name already in metadata
                    if not any(m.get("name") == name for m in metadata):
                        meta = info.copy()
                        if not meta.get("name"):
                            meta["name"] = name
                        # Try to get annotation from type hints
                        try:
                            from typing import get_type_hints

                            hints = get_type_hints(handler)
                            meta["annotation"] = hints.get(name)
                        except (TypeError, NameError, AttributeError):
                            meta["annotation"] = param.annotation
                        metadata.append(meta)
        except (ValueError, TypeError):
            pass

        for meta in metadata:
            p_type = meta.get("type")
            if p_type in ("query", "header", "cookie", "form"):
                name = meta.get("alias") or meta.get("name")
                if not name:
                    continue

                # Check if already added
                if any(p["name"] == name and p.get("in") == p_type for p in params):
                    continue

                if p_type == "form":
                    p = {
                        "name": name,
                        "in": "form",
                        "required": meta.get("default") is ...,
                        "schema": {"type": "string"},
                    }
                else:
                    p = {
                        "name": name,
                        "in": p_type,
                        "required": meta.get("default") is ...,
                        "schema": {"type": "string"},  # Default to string
                    }

                # Try to refine schema from annotation if available
                annotation = meta.get("annotation")
                if annotation and annotation is not inspect.Parameter.empty:
                    from quadkit.web.docs.type_registry import (
                        _type_documenter_registry,
                    )

                    documenter = _type_documenter_registry.get_documenter(annotation)
                    if documenter:
                        documenter.document(p)

                params.append(p)
            elif p_type == "path":
                # Path params are already extracted from the URL, but we can refine them
                name = meta.get("alias") or meta.get("name")
                if name:
                    for p in params:
                        if p["name"] == name:
                            annotation = meta.get("annotation")
                            if annotation and annotation is not inspect.Parameter.empty:
                                from quadkit.web.docs.type_registry import (
                                    _type_documenter_registry,
                                )

                                documenter = _type_documenter_registry.get_documenter(
                                    annotation,
                                )
                                if documenter:
                                    documenter.document(p)
                            break

        return params

    def generate_spec(self, controllers: list[type]) -> dict[str, Any]:
        """Generate an OpenAPI 3.0.3 specification for the provided controllers."""
        for controller in controllers or []:
            try:
                from typing import cast
                routes = cast("Any", controller).collect_routes()
            except (AttributeError, TypeError) as e:
                logger.warning(
                    "Controller %s collect_routes failed: %s",
                    getattr(controller, "__name__", repr(controller)),
                    e,
                )
                routes = []

            tag = getattr(controller, "__name__", "default")
            prefix = getattr(controller, "prefix", "") or ""

            for route in routes:
                raw_path = route.get("path")
                if raw_path is None:
                    continue

                # Harden path and method against Mocks
                raw_path = str(raw_path)
                # Ensure path starts with / and combines prefix correctly
                path = prefix.rstrip("/") + raw_path
                if not path.startswith("/"):
                    path = "/" + path
                method = str(route.get("method") or "GET").lower()

                handler_name = route.get("handler_name")
                handler = (
                    getattr(controller, handler_name, None) if handler_name else None
                )

                # Extract summary and description from docstring if not provided
                doc_summary = None
                doc_description = None
                if handler and handler.__doc__:
                    doc_lines = handler.__doc__.strip().split("\n")
                    doc_summary = doc_lines[0].strip()
                    if len(doc_lines) > 1:
                        doc_description = "\n".join(doc_lines[1:]).strip()

                summary = route.get("summary") or doc_summary or handler_name
                description = route.get("description") or doc_description or ""

                op_id = route.get("operation_id") or handler_name
                operation: dict[str, Any] = {
                    "operationId": f"{tag}_{op_id}" if op_id else None,
                    "summary": summary,
                    "description": description,
                    "tags": route.get("tags") or [tag],
                    "deprecated": route.get("deprecated", False),
                    "responses": {},
                }

                # Handle path parameters
                raw_path_params = self._extract_path_parameters(path)
                # Separate OpenAPI parameters from form-based body parameters
                all_params = self._extract_operation_parameters(
                    handler,
                    raw_path_params,
                )
                operation["parameters"] = [p for p in all_params if p["in"] != "form"]
                form_params = [p for p in all_params if p["in"] == "form"]

                # Handle responses
                status_code = str(route.get("status_code", 200))
                custom_responses = route.get("responses")

                if custom_responses:
                    for code, resp_data in custom_responses.items():
                        operation["responses"][str(code)] = resp_data
                else:
                    operation["responses"][status_code] = {"description": "Success"}

                # Request body (if a request model is provided or we have form params)
                req_model = route.get("request_model")
                if req_model is not None:
                    schema = self._get_schema_for_model(req_model)
                    operation["requestBody"] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": schema,
                            },
                        },
                    }
                elif form_params:
                    # Collect form params into a schema
                    form_properties = {}
                    required_form_params = []
                    for f_p in form_params:
                        form_properties[f_p["name"]] = f_p.get(
                            "schema", {"type": "string"},
                        )
                        if f_p.get("required"):
                            required_form_params.append(f_p["name"])

                    operation["requestBody"] = {
                        "content": {
                            "application/x-www-form-urlencoded": {
                                "schema": {
                                    "type": "object",
                                    "properties": form_properties,
                                },
                            },
                        },
                    }
                    if required_form_params:
                        operation["requestBody"]["content"][
                            "application/x-www-form-urlencoded"
                        ]["schema"]["required"] = required_form_params

                resp_model = route.get("response_model")
                if resp_model is not None:
                    schema = self._get_schema_for_model(resp_model)
                    # Merge with existing response if already defined via custom_responses
                    if status_code not in operation["responses"]:
                        operation["responses"][status_code] = {"description": "Success"}

                    operation["responses"][status_code]["content"] = {
                        "application/json": {
                            "schema": schema,
                        },
                    }

                # Add path/method
                path = self._normalize_path(path)
                method = str(method).lower()
                self.paths.setdefault(path, {})[method] = operation

        spec: dict[str, Any] = {
            "openapi": "3.0.3",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            "paths": self.paths,
            "components": self.components,
        }
        return spec
