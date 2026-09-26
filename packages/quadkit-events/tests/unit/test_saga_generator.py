from __future__ import annotations

from pathlib import Path
import py_compile
import tempfile

from quadkit.events.cli.generators.saga import SagaGenerator


class TestSagaGenerator:
    def setup_method(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())

    def test_generates_saga_file(self) -> None:
        gen = SagaGenerator(output_dir=str(self.tmp_dir))
        result = gen.generate("OrderFulfillment")
        assert result.files_created == [self.tmp_dir / "order_fulfillment_saga.py"]
        assert (self.tmp_dir / "order_fulfillment_saga.py").exists()

    def test_generated_file_is_valid_python(self) -> None:
        gen = SagaGenerator(output_dir=str(self.tmp_dir))
        gen.generate("PaymentCapture")
        py_compile.compile(self.tmp_dir / "payment_capture_saga.py", doraise=True)

    def test_generated_content_has_saga_class(self) -> None:
        gen = SagaGenerator(output_dir=str(self.tmp_dir))
        gen.generate("PaymentCapture")
        content = (self.tmp_dir / "payment_capture_saga.py").read_text()
        assert "class PaymentCaptureSaga:" in content

    def test_dry_run_creates_no_files_on_disk(self) -> None:
        gen = SagaGenerator(output_dir=str(self.tmp_dir))
        result = gen.generate("Widget", dry_run=True)
        assert result.files_created == [self.tmp_dir / "widget_saga.py"]
        assert not (self.tmp_dir / "widget_saga.py").exists()

    def test_files_skipped_on_existing_without_force(self) -> None:
        gen = SagaGenerator(output_dir=str(self.tmp_dir))
        gen.generate("Item")
        result = gen.generate("Item")
        assert result.files_skipped == [self.tmp_dir / "item_saga.py"]
        assert result.files_created == []

    def test_force_overwrites_existing_file(self) -> None:
        gen = SagaGenerator(output_dir=str(self.tmp_dir))
        gen.generate("Item")
        result = gen.generate("Item", force=True)
        assert result.files_overwritten == [self.tmp_dir / "item_saga.py"]
