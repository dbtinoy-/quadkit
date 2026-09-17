"""OpenAPI enrichment utilities.

Adds security schemes, tags, pagination, and error schemas to OpenAPI spec.
"""

from __future__ import annotations

from typing import Any


class OpenAPIEnricher:
    """Enriches OpenAPI specifications with additional details."""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self._ensure_components()

    def _ensure_components(self) -> None:
        """Ensure components section exists."""
        if "components" not in self.spec:
            self.spec["components"] = {}
        if "schemas" not in self.spec["components"]:
            self.spec["components"]["schemas"] = {}
        if "securitySchemes" not in self.spec["components"]:
            self.spec["components"]["securitySchemes"] = {}

    def add_security_scheme(
        self,
        name: str,
        scheme_type: str,
        *,
        bearer_format: str | None = None,
        flows: dict | None = None,
        api_key_name: str | None = None,
        api_key_in: str | None = None,
    ) -> OpenAPIEnricher:
        """Add a security scheme to the spec."""
        schemes = self.spec["components"]["securitySchemes"]

        if scheme_type == "http":
            schemes[name] = {
                "type": "http",
                "scheme": "bearer",
            }
            if bearer_format:
                schemes[name]["bearerFormat"] = bearer_format
        elif scheme_type == "oauth2":
            schemes[name] = {
                "type": "oauth2",
                "flows": flows or {},
            }
        elif scheme_type == "apiKey":
            schemes[name] = {
                "type": "apiKey",
                "name": api_key_name or name,
                "in": api_key_in or "header",
            }

        return self

    def add_bearer_auth(self, bearer_format: str = "JWT") -> OpenAPIEnricher:
        """Add Bearer authentication (JWT, etc.)."""
        return self.add_security_scheme(
            "BearerAuth",
            "http",
            bearer_format=bearer_format,
        )

    def add_api_key_auth(
        self,
        name: str = "ApiKeyAuth",
        header_name: str = "X-API-Key",
    ) -> OpenAPIEnricher:
        """Add API key authentication."""
        return self.add_security_scheme(
            name,
            "apiKey",
            api_key_name=header_name,
            api_key_in="header",
        )

    def apply_security_to_all_paths(
        self,
        schemes: list[str],
    ) -> OpenAPIEnricher:
        """Apply security schemes to all paths."""
        security = [{"scheme": s} for s in schemes]

        for _path, path_item in self.spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    if "security" not in operation:
                        operation["security"] = security

        return self

    def add_tag(
        self,
        name: str,
        *,
        description: str | None = None,
    ) -> OpenAPIEnricher:
        """Add a tag to the spec."""
        tags = self.spec.setdefault("tags", [])

        # Check if tag already exists
        for tag in tags:
            if tag["name"] == name:
                if description:
                    tag["description"] = description
                return self

        tag = {"name": name}
        if description:
            tag["description"] = description
        tags.append(tag)

        return self

    def add_error_schema(
        self,
        error_type: str,
        status_code: int,
    ) -> OpenAPIEnricher:
        """Add an error response schema."""
        schema = {
            "type": "object",
            "properties": {
                "error": {"type": "string"},
                "message": {"type": "string"},
            },
        }

        # Add to common error schemas
        error_name = f"Error{error_type}"
        self.spec["components"]["schemas"][error_name] = schema

        # Add to each path that uses it
        for _path, path_item in self.spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    responses = operation.get("responses", {})
                    if str(status_code) not in responses:
                        responses[str(status_code)] = {
                            "description": error_type,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": f"#/components/schemas/{error_name}",
                                    },
                                },
                            },
                        }

        return self

    def add_pagination_response(
        self,
        response_name: str,
        item_schema: dict[str, Any],
    ) -> OpenAPIEnricher:
        """Add a paginated response schema."""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": item_schema,
                },
                "meta": {
                    "type": "object",
                    "properties": {
                        "total": {"type": "integer"},
                        "page": {"type": "integer"},
                        "size": {"type": "integer"},
                        "pages": {"type": "integer"},
                        "has_next": {"type": "boolean"},
                        "has_prev": {"type": "boolean"},
                    },
                },
            },
        }

        self.spec["components"]["schemas"][response_name] = schema
        return self

    def add_file_upload_parameter(
        self,
        name: str,
        required: bool = False,
    ) -> dict[str, Any]:
        """Create a file upload parameter schema."""
        return {
            "name": name,
            "in": "formData",
            "description": "File to upload",
            "required": required,
            "type": "file",
        }


def enrich_spec(
    spec: dict[str, Any],
    *,
    add_bearer: bool = True,
    add_api_key: bool = False,
    add_error_responses: bool = True,
) -> dict[str, Any]:
    """Enrich an OpenAPI spec with common additions."""
    enricher = OpenAPIEnricher(spec)

    if add_bearer:
        enricher.add_bearer_auth()

    if add_api_key:
        enricher.add_api_key_auth()

    if add_error_responses:
        enricher.add_error_schema("Validation", 400)
        enricher.add_error_schema("Unauthorized", 401)
        enricher.add_error_schema("Forbidden", 403)
        enricher.add_error_schema("NotFound", 404)
        enricher.add_error_schema("InternalError", 500)

    return spec
