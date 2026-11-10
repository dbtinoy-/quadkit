"""Namespace package shim — do not add imports here."""

from __future__ import annotations

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
