"""Config YAML generator — introspects Pydantic config models.

Generates per-package YAML configuration files with defaults and
field descriptions as inline comments.

Usage::

    python -m quadkit.cli config-gen --all --output-dir config/
    python -m quadkit.cli config-gen --package database --output-dir config/
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, get_args, get_origin

from quadkit.cli.package_names import module_for, provider_available
from quadkit.logging import get_logger

if TYPE_CHECKING:
    import argparse

    from pydantic.fields import FieldInfo

logger = get_logger(__name__)

# Registry: maps YAML section key → (provider feature, config class name).
# Optional entries are materialized only when their provider is installed.
_CONFIG_SPECS: dict[str, tuple[str, str]] = {
    "database": ("sql", "DatabaseConfig"),
    "web": ("web", "WebConfig"),
    "auth": ("auth", "AuthConfig"),
    "cache": ("cache", "CacheConfig"),
    "storage": ("storage", "StorageConfig"),
    "tasks": ("tasks", "TaskConfig"),
    "events": ("events", "EventsConfig"),
    "search": ("search", "SearchConfig"),
    "ai": ("ai", "AIConfig"),
    "monitor": ("monitor", "MonitorConfig"),
    "messaging": ("messaging", "MessagingConfig"),
    "feature_flags": ("features", "FeatureFlagsConfig"),
    "graphql": ("graphql", "GraphQLConfig"),
}
PACKAGE_CONFIGS: dict[str, str] = {
    key: f"{module_for(feature, 'config')}:{class_name}"
    for key, (feature, class_name) in _CONFIG_SPECS.items()
    if feature == "web" or provider_available(feature)
}


def _import_config_class(import_path: str) -> type[Any]:
    """Import a config class from a dotted path like 'quadkit.<provider>.config:ConfigClass'.

    Raises ImportError if the optional domain-model provider is not installed.
    """
    module_path, class_name = import_path.rsplit(":", 1)

    module = importlib.import_module(module_path)
    config_cls: type[Any] = getattr(module, class_name)
    return config_cls


def _get_default_value(field_info: FieldInfo, field_name: str) -> Any:
    """Extract the default value from a Pydantic FieldInfo."""
    if field_info.default is not None and field_info.default is not ...:
        return field_info.default
    if field_info.default_factory is not None:
        try:
            return field_info.default_factory()  # type: ignore[call-arg]
        except Exception:  # noqa: BLE001 — config generation degrades to None
            return None
    return None


def _is_pydantic_model(annotation: Any) -> bool:
    """Check if annotation is a Pydantic DomainModel subclass."""
    try:
        import importlib

        domain_mod = importlib.import_module("quadkit.domain")
        DomainModel = domain_mod.DomainModel

        if isinstance(annotation, type) and issubclass(annotation, DomainModel):
            return True
    except (ImportError, AttributeError, TypeError):
        pass
    return False


def _is_instance_of_domain_model(obj: Any) -> bool:
    """Check if object is an instance of DomainModel."""
    try:
        import importlib

        domain_mod = importlib.import_module("quadkit.domain")
        DomainModel = domain_mod.DomainModel

        return isinstance(obj, DomainModel)
    except (ImportError, AttributeError, TypeError):
        return False


def _model_to_yaml_dict(model_cls: Any) -> dict[str, Any]:
    """Convert a Pydantic model class to a dict of defaults for YAML output."""
    result: dict[str, Any] = {}

    for field_name, field_info in model_cls.model_fields.items():
        # Skip ClassVar fields
        annotation = field_info.annotation
        if get_origin(annotation) is ClassVar:
            continue

        # Handle nested models
        actual_type = annotation
        # Unwrap Optional[X] → X
        origin = get_origin(actual_type)
        if origin is type(None):
            continue
        args = get_args(actual_type)
        if args:
            # Filter out NoneType for Optional
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                actual_type = non_none[0]

        if _is_pydantic_model(actual_type):
            result[field_name] = _model_to_yaml_dict(actual_type)
        else:
            default = _get_default_value(field_info, field_name)
            if default is not None:
                # Convert Pydantic models in defaults to dicts
                if _is_instance_of_domain_model(default):
                    result[field_name] = default.model_dump()
                else:
                    result[field_name] = default
            elif field_info.is_required():
                result[field_name] = f"<REQUIRED:{field_name}>"
            else:
                result[field_name] = None

    return result


def _collect_comments(
    model_cls: Any,
    prefix: str = "",
) -> dict[str, str]:
    """Collect field descriptions as comments keyed by dotted path."""
    comments: dict[str, str] = {}

    for field_name, field_info in model_cls.model_fields.items():
        annotation = field_info.annotation
        if get_origin(annotation) is ClassVar:
            continue

        path = f"{prefix}.{field_name}" if prefix else field_name
        description = field_info.description
        if description:
            comments[path] = description

        # Recurse into sub-models
        actual_type = annotation
        args = get_args(actual_type)
        if args:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                actual_type = non_none[0]
        if _is_pydantic_model(actual_type):
            comments.update(_collect_comments(actual_type, path))

    return comments


def _dict_to_yaml_lines(
    data: dict[str, Any],
    comments: dict[str, str],
    indent: int = 0,
    prefix: str = "",
) -> list[str]:
    """Convert a dict to YAML lines with inline comments."""
    lines: list[str] = []
    pad = "  " * indent

    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        comment = comments.get(path)

        if isinstance(value, dict):
            comment_str = f"  # {comment}" if comment else ""
            lines.append(f"{pad}{key}:{comment_str}")
            lines.extend(
                _dict_to_yaml_lines(value, comments, indent + 1, path),
            )
        elif isinstance(value, list):
            comment_str = f"  # {comment}" if comment else ""
            if not value:
                lines.append(f"{pad}{key}: []{comment_str}")
            else:
                lines.append(f"{pad}{key}:{comment_str}")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{pad}  -")
                        for k, v in item.items():
                            lines.append(f"{pad}    {k}: {_format_yaml_value(v)}")
                    else:
                        lines.append(f"{pad}  - {_format_yaml_value(item)}")
        elif isinstance(value, bool):
            comment_str = f"  # {comment}" if comment else ""
            lines.append(f"{pad}{key}: {str(value).lower()}{comment_str}")
        elif value is None:
            comment_str = f"  # {comment}" if comment else ""
            lines.append(f"{pad}{key}: null{comment_str}")
        else:
            comment_str = f"  # {comment}" if comment else ""
            lines.append(f"{pad}{key}: {_format_yaml_value(value)}{comment_str}")

    return lines


def _format_yaml_value(value: Any) -> str:
    """Format a value for YAML output."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        # Quote strings that contain special YAML chars
        if any(c in value for c in ":{}[]&*?|>!%@`#,'\"") or value == "":
            return f'"{value}"'
        return f'"{value}"'
    if value is None:
        return "null"
    return str(value)


def generate_package_config(
    package_key: str,
    import_path: str,
    with_comments: bool = True,
) -> str:
    """Generate YAML config for a single package.

    Args:
        package_key: The YAML section key (e.g. 'database').
        import_path: Import path like 'quadkit.<provider>.config:ConfigClass'.
        with_comments: Include field descriptions as comments.

    Returns:
        YAML string content.
    """
    try:
        config_cls = _import_config_class(import_path)
    except ImportError as e:
        if module_for("domain") in str(e) or "DomainModel" in str(e):
            error_msg = (
                "The optional domain-model provider is required for config "
                "generation; install the provider before retrying."
            )
            return f"# Error: {error_msg}\n# Original error: {e}\n{package_key}: {{}}\n"
        return f"# Failed to import {import_path}: {e}\n{package_key}: {{}}\n"
    except AttributeError as e:
        return f"# Failed to import {import_path}: {e}\n{package_key}: {{}}\n"

    defaults = _model_to_yaml_dict(config_cls)
    comments = _collect_comments(config_cls) if with_comments else {}

    # Wrap under the package key
    wrapped = {package_key: defaults}
    wrapped_comments = {f"{package_key}.{k}": v for k, v in comments.items()}

    header = f"# {package_key} — Generated from {config_cls.__name__}\n"
    header += "# Edit values below, then remove this comment.\n\n"

    lines = _dict_to_yaml_lines(wrapped, wrapped_comments)
    return header + "\n".join(lines) + "\n"


def run_config_gen(args: argparse.Namespace) -> None:
    """Execute the config-gen command."""
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.package:
        import_path = PACKAGE_CONFIGS.get(args.package)
        if import_path is None:
            return
        packages: dict[str, str] = {args.package: import_path}
    elif args.generate_all:
        packages = PACKAGE_CONFIGS
    else:
        return

    generated = 0
    for key, import_path in sorted(packages.items()):
        filename = f"{key}.yaml"
        filepath = output_dir / filename

        if filepath.exists() and not args.overwrite:
            continue

        yaml_content = generate_package_config(
            key,
            import_path,
            with_comments=args.with_comments,
        )

        filepath.write_text(yaml_content, encoding="utf-8")
        generated += 1


__all__ = ["PACKAGE_CONFIGS", "generate_package_config", "run_config_gen"]
