"""Order console assets + static-serving routes.

Convention: the UI package contains the page controller (pages.py),
HTML views (views/), and static assets (static/).  All dynamic
behavior comes from the API controller — the page controller only
serves files.
"""

from __future__ import annotations
