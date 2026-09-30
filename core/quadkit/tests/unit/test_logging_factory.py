"""Tests for logging/factory module."""

from unittest.mock import Mock

from quadkit.logging.factory import (
    LoggerFactoryImpl,
    _NamedLogger,
    get_logger,
)


class TestNamedLogger:
    """Tests for _NamedLogger class."""

    def test_init(self) -> None:
        """Test _NamedLogger initialization."""
        mock_inner = Mock()
        logger = _NamedLogger(mock_inner, "test.logger")
        assert logger.name == "test.logger"

    def test_delegates_debug(self) -> None:
        """Test debug method delegation."""
        mock_inner = Mock()
        logger = _NamedLogger(mock_inner, "test")
        logger.debug("test message", key="value")
        mock_inner.debug.assert_called_once_with("test message", key="value")

    def test_delegates_info(self) -> None:
        """Test info method delegation."""
        mock_inner = Mock()
        logger = _NamedLogger(mock_inner, "test")
        logger.info("test message")
        mock_inner.info.assert_called_once_with("test message")

    def test_delegates_warning(self) -> None:
        """Test warning method delegation."""
        mock_inner = Mock()
        logger = _NamedLogger(mock_inner, "test")
        logger.warning("test message")
        mock_inner.warning.assert_called_once_with("test message")

    def test_delegates_error(self) -> None:
        """Test error method delegation."""
        mock_inner = Mock()
        logger = _NamedLogger(mock_inner, "test")
        logger.error("test message")
        mock_inner.error.assert_called_once_with("test message")

    def test_delegates_critical(self) -> None:
        """Test critical method delegation."""
        mock_inner = Mock()
        logger = _NamedLogger(mock_inner, "test")
        logger.critical("test message")
        mock_inner.critical.assert_called_once_with("test message")

    def test_delegates_exception(self) -> None:
        """Test exception method delegation."""
        mock_inner = Mock()
        logger = _NamedLogger(mock_inner, "test")
        try:
            raise ValueError("test")
        except ValueError:
            logger.exception("test message")
        mock_inner.exception.assert_called_once_with("test message")

    def test_bind_returns_named_logger(self) -> None:
        """Test bind returns wrapped _NamedLogger."""
        mock_inner = Mock()
        mock_inner.bind.return_value = mock_inner  # returns same object
        logger = _NamedLogger(mock_inner, "test")
        result = logger.bind(key="value")
        assert result is logger

    def test_bind_returns_new_named_logger(self) -> None:
        """Test bind returns new _NamedLogger when result differs."""
        mock_inner = Mock()
        mock_new = Mock()
        mock_inner.bind.return_value = mock_new
        logger = _NamedLogger(mock_inner, "test")
        result = logger.bind(key="value")
        assert isinstance(result, _NamedLogger)
        assert result.name == "test"

    def test_unbind(self) -> None:
        """Test unbind method."""
        mock_inner = Mock()
        logger = _NamedLogger(mock_inner, "test")
        logger.unbind("key")
        mock_inner.unbind.assert_called_once_with("key")

    def test_getattr_delegation(self) -> None:
        """Test __getattr__ delegates to inner."""
        mock_inner = Mock()
        mock_inner.some_method = Mock(return_value="result")
        logger = _NamedLogger(mock_inner, "test")
        result = logger.some_method()
        assert result == "result"

    def test_dir_includes_name(self) -> None:
        """Test __dir__ includes 'name'."""
        mock_inner = Mock()
        logger = _NamedLogger(mock_inner, "test")
        d = dir(logger)
        assert "name" in d


class TestGetLogger:
    """Tests for get_logger function."""

    def test_default_name(self) -> None:
        """Test get_logger with None returns quadkit."""
        logger = get_logger(None)
        assert logger.name == "quadkit"

    def test_no_prefix_already_prefixed(self) -> None:
        """Test get_logger doesn't double prefix quadkit."""
        logger = get_logger("quadkit.module")
        assert logger.name == "quadkit.module"

    def test_auto_prefix(self) -> None:
        """Test get_logger adds prefix."""
        logger = get_logger("mymodule")
        assert logger.name == "quadkit.mymodule"

    def test_logger_has_name_attribute(self) -> None:
        """Test logger has name attribute."""
        logger = get_logger("test")
        assert hasattr(logger, "name")


class TestLoggerFactoryImpl:
    """Tests for LoggerFactoryImpl class."""

    def test_init_without_config(self) -> None:
        """Test initialization without config."""
        factory = LoggerFactoryImpl()
        assert factory._config is None

    def test_init_with_config(self) -> None:
        """Test initialization with config."""
        config = Mock()
        factory = LoggerFactoryImpl(config)
        assert factory._config is config

    def test_get_logger_returns_logger(self) -> None:
        """Test get_logger returns a logger."""
        factory = LoggerFactoryImpl()
        logger = factory.get_logger("test")
        assert logger is not None
        assert hasattr(logger, "name")

    def test_get_logger_does_not_hijack_the_service_field(self) -> None:
        """The DI factory must not relabel the envelope's ``service``.

        It used to ``bind(service=name)``, and ``_service_processor`` yields
        to a bound value — so a logger resolved by the wellness module
        rendered ``service=wellness`` instead of the application name every
        log pipeline routes on.  The logger name travels in
        ``_logger_name``.
        """
        factory = LoggerFactoryImpl()
        logger = factory.get_logger("test")
        assert logger.name == "quadkit.test"
        context = getattr(logger._inner, "_context", {})
        assert "service" not in context
        assert context.get("_logger_name") == "quadkit.test"


class TestNamedLoggerChaining:
    """Tests for _NamedLogger chaining methods."""

    def test_new_method_wrapped(self) -> None:
        """Test 'new' method returns _NamedLogger."""
        mock_inner = Mock()
        mock_new_logger = Mock()
        mock_inner.new.return_value = mock_new_logger
        logger = _NamedLogger(mock_inner, "test")
        result = logger.new()
        assert isinstance(result, _NamedLogger)
        assert result.name == "test"

    def test_new_method_returns_same(self) -> None:
        """Test 'new' method returns self when inner returns same."""
        mock_inner = Mock()
        mock_inner.new.return_value = mock_inner
        logger = _NamedLogger(mock_inner, "test")
        result = logger.new()
        assert result is logger

    def test_clone_method_wrapped(self) -> None:
        """Test 'clone' method returns _NamedLogger."""
        mock_inner = Mock()
        mock_cloned = Mock()
        mock_inner.clone.return_value = mock_cloned
        logger = _NamedLogger(mock_inner, "test")
        result = logger.clone()
        assert isinstance(result, _NamedLogger)
        assert result.name == "test"

    def test_clone_method_returns_same(self) -> None:
        """Test 'clone' method returns self when inner returns same."""
        mock_inner = Mock()
        mock_inner.clone.return_value = mock_inner
        logger = _NamedLogger(mock_inner, "test")
        result = logger.clone()
        assert result is logger


class TestGetLoggerEdgeCases:
    """Additional edge case tests for get_logger."""

    def test_logger_with_empty_string_name(self) -> None:
        """Test get_logger with empty string adds prefix."""
        logger = get_logger("")
        assert logger.name == "quadkit."

    def test_logger_with_dot_prefix(self) -> None:
        """Test get_logger with . prefix adds quadkit."""
        logger = get_logger(".something")
        assert logger.name == "quadkit..something"

    def test_get_logger_no_name_returns_quadkit(self) -> None:
        """Test get_logger with no args returns quadkit."""
        logger = get_logger()
        assert logger.name == "quadkit"


class TestLoggerFactoryImplEdgeCases:
    """Additional edge cases for LoggerFactoryImpl."""

    def test_get_logger_with_none(self) -> None:
        """Test get_logger with None returns root logger."""
        factory = LoggerFactoryImpl()
        logger = factory.get_logger(None)
        assert logger.name == "quadkit"

    def test_reserved_event_field_is_preserved_not_raised(self) -> None:
        """``event=`` is structlog's message parameter, not a free field.

        ``logger.warning("event_emit_failed", event=cls.__name__)`` raised
        ``TypeError`` from inside the ``except`` block that was reporting a
        failure — shipped twice in this workspace.  The field is moved to
        ``event_field`` instead; the gate
        (``dev/checks/reserved_log_fields.py``) fails the call site.
        """
        inner = Mock()
        logger = _NamedLogger(inner, "quadkit.test")

        # reserved-log-field: the behaviour under test is the remap itself
        logger.info("task_finished", event="TaskCompleted")

        inner.info.assert_called_once_with("task_finished", event_field="TaskCompleted")

    def test_reserved_event_field_never_overwrites_an_existing_key(self) -> None:
        """A caller who already uses ``event_field`` keeps both values."""
        inner = Mock()
        logger = _NamedLogger(inner, "quadkit.test")

        # reserved-log-field: the behaviour under test is the remap itself
        logger.error("failed", event="A", event_field="B")

        inner.error.assert_called_once_with("failed", event_field="B", event_field_="A")

    def test_message_parameter_is_positional_only(self) -> None:
        """``msg`` is a field name like any other.

        The wrapper names its first parameter ``msg``; without ``/`` it
        would invent a reserved word structlog itself does not have.
        """
        inner = Mock()
        logger = _NamedLogger(inner, "quadkit.test")

        logger.info("mail_sent", msg="body")

        inner.info.assert_called_once_with("mail_sent", msg="body")

    def test_bind_deconflicts_too(self) -> None:
        """``bind(event=...)`` silently lost the value to the message key."""
        inner = Mock()
        inner.bind.return_value = Mock()
        logger = _NamedLogger(inner, "quadkit.test")

        logger.bind(event="Created")

        inner.bind.assert_called_once_with(event_field="Created")
