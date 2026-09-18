"""Structured logging configuration."""

import logging

import structlog


def configure_logging(*, debug: bool) -> None:
    """Configure structlog for the process.

    Args:
        debug: Emit human-readable output instead of JSON lines.
    """
    renderer: structlog.typing.Processor = (
        structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        cache_logger_on_first_use=True,
    )
