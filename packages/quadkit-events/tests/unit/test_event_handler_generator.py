from __future__ import annotations

from pathlib import Path
import py_compile
import tempfile

from quadkit.events.cli.generators.event_handler import EventHandlerGenerator


class TestEventHandlerGenerator:
    def setup_method(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())

    def test_generates_handler_file(self) -> None:
        gen = EventHandlerGenerator(output_dir=str(self.tmp_dir))
        result = gen.generate("OrderPlaced")
        assert result.files_created == [self.tmp_dir / "order_placed_handler.py"]
        assert (self.tmp_dir / "order_placed_handler.py").exists()

    def test_generated_file_is_valid_python(self) -> None:
        gen = EventHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("OrderShipped")
        py_compile.compile(self.tmp_dir / "order_shipped_handler.py", doraise=True)

    def test_generated_content_follows_demo_on_event_convention(self) -> None:
        gen = EventHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("OrderPlaced")
        content = (self.tmp_dir / "order_placed_handler.py").read_text()
        assert "class OrderPlacedHandler:" in content
        assert "async def on_order_placed(self, event: Any) -> None:" in content
        assert "event_bus.subscribe" in content

    def test_dry_run_creates_no_files_on_disk(self) -> None:
        gen = EventHandlerGenerator(output_dir=str(self.tmp_dir))
        result = gen.generate("Widget", dry_run=True)
        assert result.files_created == [self.tmp_dir / "widget_handler.py"]
        assert not (self.tmp_dir / "widget_handler.py").exists()

    def test_files_skipped_on_existing_without_force(self) -> None:
        gen = EventHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("Item")
        result = gen.generate("Item")
        assert result.files_skipped == [self.tmp_dir / "item_handler.py"]
        assert result.files_created == []

    def test_force_overwrites_existing_file(self) -> None:
        gen = EventHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("Item")
        result = gen.generate("Item", force=True)
        assert result.files_overwritten == [self.tmp_dir / "item_handler.py"]


class TestEventHandlerSubscription:
    """EVT-2: the subscription is a separate input from the handler name.

    The framework convention is ``on_<event_type>`` — the method and the
    ``event_name`` log attribute describe the *event*, so a handler named
    after its own job must be told which event it handles. These tests read
    the generated module rather than only its text where the claim allows it.
    """

    def setup_method(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())

    def test_event_option_names_the_subscription_not_the_handler(self) -> None:
        gen = EventHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("SendConfirmation", event="order_created")
        content = (self.tmp_dir / "send_confirmation_handler.py").read_text()

        assert "class SendConfirmationHandler:" in content
        assert 'event_name = "order_created"' in content
        assert "async def on_order_created(self, event: Any) -> None:" in content
        assert "on_send_confirmation" not in content
        assert "handler.on_order_created" in content

    def test_without_event_the_handler_name_is_still_the_subscription(self) -> None:
        """The standalone case keeps working: one word, used twice."""
        gen = EventHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("OrderShipped")
        content = (self.tmp_dir / "order_shipped_handler.py").read_text()

        assert 'event_name = "order_shipped"' in content
        assert "async def on_order_shipped(self, event: Any) -> None:" in content

    def test_an_event_given_in_camel_case_is_snake_cased(self) -> None:
        gen = EventHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("Notify", event="OrderCreated")
        content = (self.tmp_dir / "notify_handler.py").read_text()

        assert 'event_name = "order_created"' in content
        assert "async def on_order_created(self, event: Any) -> None:" in content

    def test_the_event_named_handler_is_importable_and_dispatches(self) -> None:
        import asyncio
        import importlib.util
        import sys

        gen = EventHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("SendConfirmation", event="order_created")
        path = self.tmp_dir / "send_confirmation_handler.py"

        spec = importlib.util.spec_from_file_location("event_handler_under_test", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)

            handler = module.SendConfirmationHandler()
            assert handler.event_name == "order_created"
            # The method the bus is subscribed to is the one that exists.
            asyncio.run(handler.on_order_created(object()))
        finally:
            sys.modules.pop(spec.name, None)
