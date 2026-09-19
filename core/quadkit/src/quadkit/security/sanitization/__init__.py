"""Input sanitization package."""

from __future__ import annotations

from quadkit.security.config import InputSanitizerConfig
from quadkit.security.sanitization.sanitizer import InputSanitizer

__all__ = ["InputSanitizer", "InputSanitizerConfig"]
