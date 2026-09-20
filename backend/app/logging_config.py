"""
Production hardening: structured application logging.

Before this, the only trail of what the server did was uvicorn's default
access log -- fine for "a request happened," useless for "why did this
request fail" or "what was in flight when this crashed." This gives every
request a start/end log line and routes unhandled exceptions to a real
traceback in the log instead of silently vanishing into a generic 500.
"""
import logging
import sys

_configured = False


def configure_logging() -> logging.Logger:
    global _configured
    logger = logging.getLogger("sih26099")
    if _configured:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _configured = True
    return logger


logger = configure_logging()
