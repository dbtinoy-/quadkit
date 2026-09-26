"""JSON API controllers (logic lives here; pages serve assets).

Convention: controllers expose the domain over HTTP.  They receive
the ``OrdersApi`` facade via constructor injection and delegate all
business logic to it.  Error-to-HTTP mapping is registered at module
level via ``@error_status`` decorators.
"""

from __future__ import annotations

from orders.controllers.api import OrdersApiController

__all__ = ["OrdersApiController"]
