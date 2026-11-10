"""OpenAPI specification generator for quadkit-web

This is a lightweight implementation that inspects controller route metadata
and constructs a minimal OpenAPI 3.0.3 specification including component
schemas for Pydantic response models (when available).
"""

from __future__ import annotations

from copy import deepcopy
import inspect
import math
import re
from typing import Any

from pydantic import BaseModel, TypeAdapter
from pydantic.json_schema import JsonSchemaMode

from quadkit.contracts.web.security_metadata import (
    HttpBearerDocumentation,
)
from quadkit.logging import get_logger
from quadkit.web.docs.security import (
    documented_guard_rejections,
    merge_documented_response,
)
from quadkit.web.docs.type_registry import TypeDocumenterRegistry
from quadkit.web.middleware.auth import AuthenticationMiddlewareDocumentation

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

    # Generated callers must fail closed on older Web implementations that drop
    # explicit request/response operations while still registering the route.
    supports_explicit_operation_v1 = True
    supports_result_error_docs_v1 = True
    supports_response_schema_model_v1 = True

    def __init__(
        self,
        title: str,
        version: str,
        description: str | None = None,
        *,
        authentication_middleware: AuthenticationMiddlewareDocumentation | None = None,
    ) -> None:
        """
        Args:
            title: API title displayed in generated documentation.
            version: API version string (e.g. ``"1.0.0"``).
            description: Optional long-form API description shown in the UI.
        """
        self.authentication_middleware = authentication_middleware
        self.title = title
        self.version = version
        self.description = description or ""
        self.paths: dict[str, Any] = {}
        self.components: dict[str, Any] = {"schemas": {}}
        self._model_schema_refs: dict[
            tuple[type[BaseModel], JsonSchemaMode], list[dict[str, Any]]
        ] = {}
        # One registry per generator: registering a documenter for one
        # application never changes another application's spec.
        self._type_documenters = TypeDocumenterRegistry()

    def _get_schema_for_model(
        self, model: Any, *, mode: JsonSchemaMode = "validation"
    ) -> dict[str, Any]:
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
            items = (
                self._get_schema_for_model(args[0], mode=mode)
                if args
                else {"type": "object"}
            )
            return {"type": "array", "items": items}
        if origin is dict:
            return {"type": "object"}

        # Batch native Pydantic definitions after route discovery. Pydantic owns
        # recursive refs, name collisions and validation/serialization variants.
        # Keep these dicts by reference so their final native refs reach the
        # operation without provisional names appearing in the served spec.
        if isinstance(model, type) and issubclass(model, BaseModel):
            reference: dict[str, Any] = {}
            self._model_schema_refs.setdefault((model, mode), []).append(reference)
            return reference

        # Preserve the existing non-Pydantic DomainModel schema protocol.
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

    def _finalize_model_schemas(self) -> None:
        """Resolve native Pydantic refs without flattening recursive schemas."""
        if not self._model_schema_refs:
            return
        references, document = TypeAdapter.json_schemas(
            [
                (model, mode, TypeAdapter(model))
                for model, mode in self._model_schema_refs
            ],
            ref_template="#/components/schemas/{model}",
        )
        definitions = document.get("$defs", {})
        existing = self.components["schemas"]
        for name, schema in definitions.items():
            if name in existing and existing[name] != schema:
                raise ValueError(f"Conflicting OpenAPI component schema: {name}")
        existing.update(definitions)
        for key, destinations in self._model_schema_refs.items():
            for destination in destinations:
                destination.clear()
                destination.update(deepcopy(references[key]))

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
                    documenter = self._type_documenters.get_documenter(annotation)
                    if documenter:
                        documenter.document(p)

                # Only explicit, finite scalar query defaults are portable JSON
                # documentation. Do not execute factories or expose header/cookie defaults.
                default = meta.get("default", ...)
                if (
                    p_type == "query"
                    and type(default) in (str, int, float, bool)
                    and (not isinstance(default, float) or math.isfinite(default))
                ):
                    p["schema"]["default"] = default

                params.append(p)
            elif p_type == "path":
                # Path params are already extracted from the URL, but we can refine them
                name = meta.get("alias") or meta.get("name")
                if name:
                    for p in params:
                        if p["name"] == name:
                            annotation = meta.get("annotation")
                            if annotation and annotation is not inspect.Parameter.empty:
                                documenter = self._type_documenters.get_documenter(
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
                # Mirror the router (routing/manager.py): absolute handler
                # paths already carrying the prefix must not double-apply it.
                path = (
                    raw_path
                    if prefix and raw_path.startswith(prefix)
                    else prefix.rstrip("/") + raw_path
                )
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

                operation["responses"].setdefault(
                    status_code, {"description": "Success"}
                )
                declared_errors = route.get("result_errors")
                if (
                    declared_errors is not None
                    and route.get("openapi_operation") is None
                ):
                    from quadkit.web.routing.result_bridge import ResultResponseMapper

                    errors = ResultResponseMapper.documented_errors(
                        declared_errors, exclude_statuses=set(operation["responses"])
                    )
                    operation["responses"].update(errors)

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
                            "schema",
                            {"type": "string"},
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
                if (
                    resp_model is None
                    and "content" not in operation["responses"][status_code]
                    and route.get("openapi_operation") is None
                ):
                    # Documentation-only fallback, never handed to the runtime
                    # ObjectMapper. Explicit response contracts stay authoritative.
                    resp_model = route.get("response_schema_model")
                    if resp_model is not None and not (
                        isinstance(resp_model, type)
                        and issubclass(resp_model, BaseModel)
                    ):
                        raise ValueError(
                            "response_schema_model must be a Pydantic model class"
                        )
                if resp_model is not None:
                    schema = self._get_schema_for_model(
                        resp_model, mode="serialization"
                    )
                    # Merge with existing response if already defined via custom_responses
                    if status_code not in operation["responses"]:
                        operation["responses"][status_code] = {"description": "Success"}

                    operation["responses"][status_code]["content"] = {
                        "application/json": {
                            "schema": schema,
                        },
                    }

                # Explicit documentation is trusted composition metadata, not
                # a routing/authentication override. Path/method stay route-owned.
                explicit = route.get("openapi_operation")
                if explicit is not None:
                    allowed = {
                        "operationId",
                        "summary",
                        "description",
                        "tags",
                        "deprecated",
                        "parameters",
                        "requestBody",
                        "responses",
                        "security",
                    }
                    if type(explicit) is not dict or any(
                        type(key) is not str
                        or (key not in allowed and not key.startswith("x-"))
                        for key in explicit
                    ):
                        raise ValueError("Invalid explicit OpenAPI operation metadata")
                    if (
                        not isinstance(explicit.get("responses"), dict)
                        or not explicit["responses"]
                    ):
                        raise ValueError(
                            "Explicit OpenAPI operations require responses"
                        )
                    operation.update(deepcopy(explicit))

                # Authentication decorators declare this through Contracts.
                # Never infer policy from guard class names or other routes.
                bearer = route.get("bearer_documentation")
                if bearer is not None:
                    if (
                        not isinstance(bearer, HttpBearerDocumentation)
                        or not isinstance(bearer.scheme_name, str)
                        or not re.fullmatch(r"[a-zA-Z0-9._-]+", bearer.scheme_name)
                    ):
                        raise ValueError("Invalid HTTP bearer documentation metadata")
                    required: list[dict[str, list[str]]] = [{bearer.scheme_name: []}]
                    if "security" in operation and operation["security"] != required:
                        raise ValueError(
                            "Explicit OpenAPI security contradicts bearer guard documentation"
                        )
                    operation["security"] = required
                    scheme = {"type": "http", "scheme": "bearer"}
                    schemes = self.components.setdefault("securitySchemes", {})
                    if (
                        bearer.scheme_name in schemes
                        and schemes[bearer.scheme_name] != scheme
                    ):
                        raise ValueError(
                            "Conflicting OpenAPI security scheme declaration"
                        )
                    schemes[bearer.scheme_name] = scheme
                    # Rejections are explicit producer claims, not deductions
                    # from bearer security, guard names or configured policies.
                    for code, declared_response in documented_guard_rejections(
                        bearer
                    ).items():
                        if explicit is not None:
                            continue  # Explicit operations own the complete response table.
                        if code in {str(key) for key in (custom_responses or {})}:
                            continue  # Explicit status responses stay authoritative.
                        merge_documented_response(
                            operation["responses"], code, declared_response
                        )

                # This claim comes from successful native integration setup, not
                # bearer metadata or enable_auth alone. Guards cannot describe
                # the outer middleware's different error-only wire response.
                if self.authentication_middleware is not None:
                    if not isinstance(
                        self.authentication_middleware,
                        AuthenticationMiddlewareDocumentation,
                    ):
                        raise ValueError(
                            "Invalid authentication middleware documentation"
                        )
                    for (
                        code,
                        declaration,
                    ) in self.authentication_middleware.responses_for(
                        self._normalize_path(path)
                    ).items():
                        if explicit is not None or code in {
                            str(key) for key in (custom_responses or {})
                        }:
                            continue
                        merge_documented_response(
                            operation["responses"], code, declaration
                        )

                # Add path/method
                path = self._normalize_path(path)
                method = str(method).lower()
                self.paths.setdefault(path, {})[method] = operation

        self._finalize_model_schemas()
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
