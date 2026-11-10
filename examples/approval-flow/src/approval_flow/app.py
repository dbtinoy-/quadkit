"""Convention followed: **Composition root** — one file knows how modules, providers and controllers fit; ``create_app(config=...)`` is the injection seam.

Composition root for the single-niche Approval Flow demo."""

from __future__ import annotations

from approval_flow.controllers.api import ApprovalFlowApiController
from approval_flow.di.provider import ApprovalFlowProvider
from approval_flow.services.flow import build_approval_state_machine
from approval_flow.ui.pages import ApprovalFlowPageController
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule
from quadkit.workflow.module import WorkflowModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the approval flow demo."""
    return [
        WorkflowModule.configure(state_machine=build_approval_state_machine()),
        WebModule.configure(
            controllers=[ApprovalFlowApiController, ApprovalFlowPageController],
        ),
    ]


def build_providers() -> list[Provider]:
    """Build the DI providers for the approval flow demo."""
    return [ApprovalFlowProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the approval flow application."""
    app = Application(name="approval-flow", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
