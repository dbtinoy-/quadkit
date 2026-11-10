"""Pure rendering of producer-owned security response documentation.

No Auth imports, guard execution, policy lookup or generated code evaluation.
"""

from typing import Any

from quadkit.contracts.web.security_metadata import (
    HttpBearerDocumentation,
    HttpErrorMessageDocumentation,
)


def documented_guard_rejections(metadata: HttpBearerDocumentation) -> dict[str, Any]:
    """Validate and render fresh JSON error/message response declarations."""
    if (
        not isinstance(metadata, HttpBearerDocumentation)
        or type(metadata.rejections) is not tuple
    ):
        raise ValueError("Invalid guard rejection documentation")
    responses: dict[str, Any] = {}
    for rejection in metadata.rejections:
        if (
            not isinstance(rejection, HttpErrorMessageDocumentation)
            or type(rejection.status_code) is not int
            or not 400 <= rejection.status_code <= 599
            or str(rejection.status_code) in responses
            or not isinstance(rejection.error, str)
            or not rejection.error
            or not isinstance(rejection.description, str)
        ):
            raise ValueError("Invalid guard rejection documentation")
        responses[str(rejection.status_code)] = {
            "description": rejection.description,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error": {"type": "string", "enum": [rejection.error]},
                            "message": {"type": "string"},
                        },
                        "required": ["error", "message"],
                    }
                }
            },
        }
    return responses


def merge_documented_response(
    responses: dict[str, Any], code: str, declaration: dict[str, Any]
) -> None:
    """Compose automatic outcomes while retaining pending model-schema identities.

    Explicit operation/status authority must be checked by the caller first.
    Only the outer response/content mappings are copied; native schema finalizers
    still own nested deferred references. Different media remain separate.
    """
    response = dict(responses.get(code, declaration))
    content = dict(response.get("content", {}))
    response["content"] = content
    for media, declared_media in declaration.get("content", {}).items():
        schema = declared_media["schema"]
        existing_schema = content.get(media, {}).get("schema")
        if existing_schema is not None and existing_schema != schema:
            schema = {"anyOf": [existing_schema, schema]}
        content[media] = {"schema": schema}
    responses[code] = response
