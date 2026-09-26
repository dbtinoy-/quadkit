"""Content type detection utilities for Quadkit Storage.

Functions here detect MIME types from file paths (via extension) or raw byte
data (via ``python-magic``).  The byte-data path degrades gracefully when
``python-magic`` / ``libmagic`` is unavailable, emitting a single
:class:`ImportWarning` so operators know they can install the optional
dependency to get accurate byte-level MIME detection.
"""

from __future__ import annotations

import mimetypes
import warnings


def get_content_type(file_path: str) -> str:
    """Detect the MIME type for *file_path* using its extension.

    Args:
        file_path: Path or filename whose extension drives MIME detection.

    Returns:
        MIME type string, e.g. ``"image/png"``.  Falls back to
        ``"application/octet-stream"`` when the extension is unknown.
    """
    content_type, _ = mimetypes.guess_type(file_path)
    return content_type or "application/octet-stream"


def get_content_type_from_data(data: bytes) -> str:
    """Detect the MIME type from raw byte *data* using ``python-magic``.

    Requires the optional ``python-magic`` package (which in turn requires the
    system ``libmagic`` shared library).  When unavailable the function falls
    back to ``"application/octet-stream"`` and emits a single
    :class:`ImportWarning` to indicate that more accurate detection is possible.

    Args:
        data: Raw bytes to inspect (the first few kilobytes are sufficient).

    Returns:
        MIME type string detected from the byte signature, or
        ``"application/octet-stream"`` when ``python-magic`` is not installed.
    """
    try:
        import magic

        return magic.from_buffer(data, mime=True)
    except ImportError:
        warnings.warn(
            "python-magic is not installed; falling back to "
            "'application/octet-stream' for byte-level MIME detection.  "
            "Install it with: pip install python-magic",
            ImportWarning,
            stacklevel=2,
        )
        return "application/octet-stream"
