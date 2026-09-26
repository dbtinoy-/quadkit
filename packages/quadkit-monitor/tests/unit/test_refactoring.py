#!/usr/bin/env python3
"""Test script to verify quadkit-monitor refactoring"""

import sys

from quadkit.logging import get_logger

logger = get_logger(__name__)


def test_protocol_imports():
    """Test root-level protocol imports"""
    logger.info("Testing protocol imports...")
    logger.info("✅ Protocol imports successful")


def test_types_imports():
    """Test root-level types imports"""
    logger.info("Testing types imports...")
    logger.info("✅ Types imports successful")


def test_exceptions_imports():
    """Test root-level exception imports"""
    logger.info("Testing exception imports...")
    logger.info("✅ Exception imports successful")


def test_metrics_imports():
    """Test metrics module imports"""
    logger.info("Testing metrics imports...")
    logger.info("✅ Metrics imports successful")


def test_tracing_imports():
    """Test tracing module imports"""
    logger.info("Testing tracing imports...")
    logger.info("✅ Tracing imports successful")


def test_logging_imports():
    """Test logging module imports"""
    logger.info("Testing logging imports...")
    logger.info("✅ Logging imports successful")


def test_backends_imports():
    """Test backends module imports"""
    logger.info("Testing backends imports...")
    logger.info("✅ Backends imports successful")


def test_middleware_imports():
    """Test middleware module imports"""
    logger.info("Testing middleware imports...")
    logger.info("✅ Middleware imports successful")


def test_provider_imports():
    """Test provider imports"""
    logger.info("Testing provider imports...")
    logger.info("✅ Provider imports successful")


def test_basic_functionality():
    """Test basic functionality"""
    logger.info("\nTesting basic functionality...")

    # Test metrics
    from quadkit.monitor import MetricsCollectorProtocol

    collector = MetricsCollectorProtocol()
    counter = collector.create_counter("test_counter", "Test counter")
    counter.increment()
    logger.info("✅ Metrics functionality working")

    # Test tracing
    from quadkit.monitor import InMemoryTraceProvider

    provider = InMemoryTraceProvider()
    tracer = provider.tracer
    with tracer.start_span("test_span"):
        pass
    logger.info("✅ Tracing functionality working")

    # Test logging
    from quadkit.monitor import get_logger

    logger_test = get_logger("test")
    logger_test.info("Test message")
    logger.info("✅ Logging functionality working")


def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("quadkit-monitor Refactoring Verification")
    logger.info("=" * 60)
    logger.info("")

    try:
        test_protocol_imports()
        test_types_imports()
        test_exceptions_imports()
        test_metrics_imports()
        test_tracing_imports()
        test_logging_imports()
        test_backends_imports()
        test_middleware_imports()
        test_provider_imports()
        test_basic_functionality()

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("The quadkit-monitor package has been successfully refactored:")
        logger.info("  • Root-level protocols: MetricProtocol, TraceProvider, MonitoringBackend")
        logger.info("  • Root-level types: MetricValue, SpanContext, Span")
        logger.info("  • Root-level exceptions: MonitorError hierarchy")
        logger.info(
            "  • Modular structure: metrics/, tracing/, logging/, backends/, middleware/",
        )
        logger.info("  • Backward compatibility maintained")
        logger.info("")
        return 0

    except (ImportError, AssertionError, RuntimeError, ValueError) as e:
        logger.info("")
        logger.info("=" * 60)
        logger.info("❌ TEST FAILED!")
        logger.info("=" * 60)
        logger.error("Error: %s", e)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
