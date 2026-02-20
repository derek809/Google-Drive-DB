"""
Async Session Manager - Singleton httpx.AsyncClient lifecycle.

Provides shared httpx.AsyncClient singletons for all HTTP-based clients
(Graph API, Claude API, etc.) to prevent file descriptor leaks on the
long-running M1 Mac process.

Two profiles:
    get_session()      — API calls (30s timeout, 20 connections)
    get_file_session() — File downloads (5min read timeout, 10 connections)

Usage:
    from async_session_manager import get_session, get_file_session, close

    session = await get_session()        # API calls
    file_session = await get_file_session()  # large file downloads
    await close()                        # in processor.cleanup()
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Module-level singleton state
_session: Optional[httpx.AsyncClient] = None
_file_session: Optional[httpx.AsyncClient] = None
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


async def get_file_session() -> httpx.AsyncClient:
    """
    Get or create a session optimized for file downloads.

    Extended read timeout (5 min) for large SharePoint files.
    Separate from the API session to prevent download stalls
    from blocking lightweight Graph API calls.

    Returns:
        Dedicated httpx.AsyncClient for file downloads.

    Raises:
        RuntimeError: If the session manager has been closed.
    """
    global _file_session, _closed

    if _closed:
        raise RuntimeError(
            "Session manager has been closed. Call reset() before "
            "requesting a new session."
        )

    if _file_session is None:
        _file_session = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=30.0, read=300.0),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
            follow_redirects=True,
            headers={"User-Agent": "Mode4-MCP-Bot/1.0"},
        )
        logger.info(
            "File download httpx.AsyncClient created "
            "(read_timeout=300s, max_conn=10)"
        )

    return _file_session


async def close() -> None:
    """
    Close all shared sessions. Idempotent — safe to call multiple times.

    After close(), get_session()/get_file_session() will raise
    RuntimeError until reset().
    """
    global _session, _file_session, _closed

    if _session is not None:
        await _session.aclose()
        logger.info("Shared httpx.AsyncClient closed")
        _session = None

    if _file_session is not None:
        await _file_session.aclose()
        logger.info("File download httpx.AsyncClient closed")
        _file_session = None

    _closed = True


async def reset() -> None:
    """
    Reset the session manager after close().

    Allows get_session()/get_file_session() to create fresh clients.
    Used primarily in testing.
    """
    global _session, _file_session, _closed

    if _session is not None:
        await _session.aclose()
        _session = None

    if _file_session is not None:
        await _file_session.aclose()
        _file_session = None

    _closed = False
    logger.info("Session manager reset")
