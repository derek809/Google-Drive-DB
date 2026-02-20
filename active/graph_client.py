"""
Microsoft Graph API Client for Hybrid Operations Backend.

MSAL-authenticated async wrapper around httpx for Microsoft Graph API.
Handles token lifecycle, 401 auto-retry, rate limiting with jitter,
and header passthrough for etag-based optimistic concurrency.

Usage:
    from async_session_manager import get_session
    from graph_client import GraphClient

    session = await get_session()
    graph = GraphClient(client_id, tenant_id, client_secret, session)

    items = await graph.get(f"{GRAPH_BASE}/sites/{site}/lists/{list}/items")
    await graph.patch(url, headers={"If-Match": etag}, data=payload)
"""

import asyncio
import atexit
import json
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional, Union

import httpx
import msal

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]


class GraphAPIError(Exception):
    """Raised when a Graph API request fails after retry.

    Attributes:
        status_code: HTTP status code (e.g. 412, 429).
        url: The request URL that failed.
        response: The raw httpx.Response, if available.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
    ):
        self.status_code = status_code
        self.url = url
        self.response: Optional[httpx.Response] = None
        super().__init__(message)


class GraphClient:
    """
    Async Microsoft Graph API client with MSAL authentication.

    Provides get/post/patch/delete methods matching the interface
    expected by SharePointListReader, OneNoteClient, HybridFileFetcher,
    and ProactiveEngine.

    Token lifecycle:
        - acquire_token_silent() checks MSAL in-memory cache first
        - Falls back to acquire_token_for_client() on cache miss
        - 401 responses trigger cache clear + single retry

    Rate limiting:
        - 100ms minimum gap between requests with 0-50ms jitter
        - Prevents 429 throttling on rapid SharePoint list updates
    """

    def __init__(
        self,
        client_id: str,
        tenant_id: str,
        client_secret: str,
        session: httpx.AsyncClient,
        token_cache_path: Optional[str] = None,
    ) -> None:
        """
        Initialize the Graph client.

        Args:
            client_id: Azure AD application (client) ID.
            tenant_id: Azure AD tenant (directory) ID.
            client_secret: Azure AD client secret value.
            session: Shared httpx.AsyncClient from async_session_manager.
            token_cache_path: Optional file path for persistent MSAL token
                cache. When set, tokens survive process restarts and reduce
                Azure AD requests on startup.
        """
        self._session = session
        self._client_id = client_id
        self._tenant_id = tenant_id
        self._client_secret = client_secret
        self._authority = f"https://login.microsoftonline.com/{tenant_id}"

        # Persistent token cache
        self._cache_path = token_cache_path
        self._cache = self._build_persistent_cache()

        self._msal_app = msal.ConfidentialClientApplication(
            client_id,
            authority=self._authority,
            client_credential=client_secret,
            token_cache=self._cache,
        )

        if self._cache_path:
            atexit.register(self._save_cache_sync)

        # Rate limiting state
        self._last_request_time: float = 0.0
        self._min_interval: float = 0.1  # 100ms

        logger.info(
            "GraphClient initialized (tenant=%s..., client=%s..., cache=%s)",
            tenant_id[:8],
            client_id[:8],
            "persistent" if self._cache_path else "in-memory",
        )

    # ── Persistent Token Cache ────────────────────────────────────────

    def _build_persistent_cache(self) -> msal.SerializableTokenCache:
        """Create and hydrate a persistent MSAL token cache from disk."""
        cache = msal.SerializableTokenCache()
        if self._cache_path and os.path.exists(self._cache_path):
            try:
                with open(self._cache_path, "r") as f:
                    cache.deserialize(f.read())
                logger.info("Token cache loaded from %s", self._cache_path)
            except (json.JSONDecodeError, IOError) as exc:
                logger.warning("Corrupt token cache, starting fresh: %s", exc)
        return cache

    def _save_cache_sync(self) -> None:
        """Persist the MSAL token cache to disk if it has changed."""
        if not self._cache_path or not self._cache.has_state_changed:
            return
        try:
            with open(self._cache_path, "w") as f:
                f.write(self._cache.serialize())
            logger.debug("Token cache saved to %s", self._cache_path)
        except IOError as exc:
            logger.warning("Could not save token cache: %s", exc)

    # ── Token Management ─────────────────────────────────────────────

    async def _get_access_token(self) -> str:
        """
        Acquire a valid access token via MSAL.

        Uses acquire_token_silent() first (in-memory cache), then
        falls back to acquire_token_for_client() on cache miss.
        Wrapped in asyncio.to_thread() since MSAL is synchronous.

        Returns:
            Bearer access token string.

        Raises:
            GraphAPIError: If token acquisition fails.
        """

        def _acquire():
            result = self._msal_app.acquire_token_silent(
                GRAPH_SCOPES, account=None
            )
            if result and "access_token" in result:
                return result

            result = self._msal_app.acquire_token_for_client(
                scopes=GRAPH_SCOPES
            )
            return result

        result = await asyncio.to_thread(_acquire)

        if "access_token" not in result:
            error = result.get("error", "unknown")
            error_desc = result.get("error_description", "no description")
            raise GraphAPIError(
                f"MSAL token acquisition failed: {error} — {error_desc}"
            )

        self._save_cache_sync()
        return result["access_token"]

    def _clear_token_cache(self) -> None:
        """Clear MSAL token cache to force re-acquisition."""
        self._cache = msal.SerializableTokenCache()
        self._msal_app = msal.ConfidentialClientApplication(
            self._client_id,
            authority=self._authority,
            client_credential=self._client_secret,
            token_cache=self._cache,
        )
        self._save_cache_sync()
        logger.info("MSAL token cache cleared")

    # ── Rate Limiting ────────────────────────────────────────────────

    async def _throttle(self) -> None:
        """
        Enforce minimum interval between requests with jitter.

        100ms base + random 0-50ms jitter to avoid 429 throttling
        on rapid SharePoint list updates.
        """
        now = time.monotonic()
        elapsed = now - self._last_request_time
        required_gap = self._min_interval + random.uniform(0, 0.05)

        if elapsed < required_gap:
            await asyncio.sleep(required_gap - elapsed)

        self._last_request_time = time.monotonic()

    # ── Public Helpers ─────────────────────────────────────────────────

    async def get_auth_headers(self) -> Dict[str, str]:
        """Return Bearer auth headers for use with external sessions."""
        token = await self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    # ── HTTP Methods ─────────────────────────────────────────────────

    async def get(
        self,
        url: str,
        stream: bool = False,
        headers: Optional[Dict[str, str]] = None,
    ) -> Union[Dict[str, Any], bytes, httpx.Response]:
        """
        GET request to Graph API.

        Args:
            url: Full Graph API URL.
            stream: If True, return raw bytes instead of parsed JSON.
            headers: Additional headers (merged with auth headers).

        Returns:
            Parsed JSON dict, raw bytes, or httpx.Response depending
            on stream flag and Content-Type.
        """
        return await self._request("GET", url, headers=headers, stream=stream)

    async def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Any = None,
    ) -> Union[Dict[str, Any], httpx.Response]:
        """POST request to Graph API."""
        return await self._request("POST", url, headers=headers, data=data)

    async def patch(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Any = None,
    ) -> Union[Dict[str, Any], httpx.Response]:
        """PATCH request to Graph API."""
        return await self._request("PATCH", url, headers=headers, data=data)

    async def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Union[Dict[str, Any], httpx.Response]:
        """DELETE request to Graph API."""
        return await self._request("DELETE", url, headers=headers)

    # ── Core Request Handler ─────────────────────────────────────────

    async def _request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Any = None,
        stream: bool = False,
        _retry: bool = True,
    ) -> Union[Dict[str, Any], bytes, httpx.Response]:
        """
        Execute a Graph API request with auth, throttling, and 401 retry.

        Flow:
        1. Acquire token via MSAL
        2. Throttle (100ms + jitter)
        3. Build headers (merge auth + caller-provided)
        4. Serialize data: dict/list → JSON, str → text, bytes → binary
        5. Execute request
        6. On 401: clear cache, retry once
        7. On 4xx/5xx: raise GraphAPIError with status_code
        8. Parse response based on Content-Type

        Raises:
            GraphAPIError: On non-recoverable HTTP errors. The exception
                has .status_code and .response attributes for callers
                that need to inspect specific error codes (412, 429, etc).
        """
        await self._throttle()
        token = await self._get_access_token()

        # Build request headers
        req_headers: Dict[str, str] = {
            "Authorization": f"Bearer {token}",
        }
        if headers:
            req_headers.update(headers)

        # Build request kwargs
        kwargs: Dict[str, Any] = {"headers": req_headers}

        if data is not None:
            if isinstance(data, (dict, list)):
                if "Content-Type" not in req_headers:
                    req_headers["Content-Type"] = "application/json"
                kwargs["content"] = json.dumps(data).encode("utf-8")
            elif isinstance(data, str):
                kwargs["content"] = data.encode("utf-8")
            elif isinstance(data, bytes):
                kwargs["content"] = data
            else:
                kwargs["content"] = str(data).encode("utf-8")

        # Execute
        logger.debug("%s %s", method, url)
        resp = await self._session.request(method, url, **kwargs)

        # 401 auto-retry: clear MSAL cache and retry once
        if resp.status_code == 401 and _retry:
            logger.warning("401 from %s, clearing token cache and retrying", url)
            self._clear_token_cache()
            return await self._request(
                method,
                url,
                headers=headers,
                data=data,
                stream=stream,
                _retry=False,
            )

        # Error handling — raise with status_code so callers can
        # pattern-match on 412 (concurrency), 429 (throttle), etc.
        if resp.status_code >= 400:
            error_body = resp.text[:500]
            exc = GraphAPIError(
                f"Graph API {method} {url} returned {resp.status_code}: "
                f"{error_body}",
                status_code=resp.status_code,
                url=url,
            )
            exc.response = resp
            raise exc

        # Parse response
        if stream:
            return resp.content  # raw bytes

        content_type = resp.headers.get("content-type", "")

        if "application/json" in content_type:
            return resp.json()

        if "text/html" in content_type or "application/xhtml" in content_type:
            return resp

        # 204 No Content
        if resp.status_code == 204 or not resp.content:
            return {}

        # Default: try JSON, fall back to response object
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError):
            return resp
