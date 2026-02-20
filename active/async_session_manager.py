"""
Async Session Manager - Singleton httpx.AsyncClient lifecycle.

Provides a single shared httpx.AsyncClient for all HTTP-based clients
(Graph API, Claude API, etc.) to prevent file descriptor leaks on the
long-running M1 Mac process.

Usage:
    from async_session_manager import get_session, close

    session = await get_session()   # creates or returns singleton
    await close()                   # in processor.cleanup()
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Module-level singleton state
_session: Optional[httpx.AsyncClient] = None
_closed: bool = False


async def get_session() -> httpx.AsyncClient:
    """
    Get or create the shared httpx.AsyncClient singleton.

    Returns:
        The shared httpx.AsyncClient instance.

    Raises:
        RuntimeError: If the session has been closed and not reset.
    """
    global _session, _closed

    if _closed:
        raise RuntimeError(
            "Session manager has been closed. Call reset() before "
            "requesting a new session."
        )

    if _session is None:
        _session = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
            follow_redirects=True,
            headers={"User-Agent": "Mode4-MCP-Bot/1.0"},
        )
        logger.info(
            "Shared httpx.AsyncClient created "
            "(max_conn=20, keepalive=10)"
        )

    return _session


async def close() -> None:
    """
    Close the shared session. Idempotent — safe to call multiple times.

    After close(), get_session() will raise RuntimeError until reset().
    """
    global _session, _closed

    if _session is not None:
        await _session.aclose()
        logger.info("Shared httpx.AsyncClient closed")
        _session = None

    _closed = True


async def reset() -> None:
    """
    Reset the session manager after close().

    Allows get_session() to create a fresh client. Used primarily
    in testing.
    """
    global _session, _closed

    if _session is not None:
        await _session.aclose()
        _session = None

    _closed = False
    logger.info("Session manager reset")
