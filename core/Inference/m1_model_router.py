"""
M1ModelRouter -- litellm-based multi-model router with automatic fallback.

This is the EXECUTION layer that actually calls LLMs.  It complements
brain/llm_router.py (the RECOMMENDATION layer that decides which model
to prefer).

Usage:
    from core.Inference.m1_model_router import M1ModelRouter

    router = M1ModelRouter()
    response = await router.route_completion(
        messages=[{"role": "user", "content": "Draft reply"}],
        preferred_model="primary"
    )
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Ensure project root is on path for config imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from litellm import Router
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logger.warning("litellm not installed. Run: pip install litellm")


class M1ModelRouter:
    """
    Multi-model router using litellm with automatic fallback chain.

    Pulls configuration from core/Infrastructure/m1_config.py:
      - OLLAMA_MODEL, CLAUDE_MODEL, KIMI_MODEL (model identifiers)
      - OLLAMA_TIMEOUT, API_TIMEOUT (per-call timeouts)
      - FALLBACK_CHAIN (ordered provider list: ["claude", "kimi", "ollama"])

    Model names used by the router:
      - "primary"        -> Claude (cloud, high quality)
      - "secondary"      -> Kimi K2.5 (cloud, creative)
      - "local_fallback"  -> Ollama (local, fast, free)
    """

    def __init__(self, config_override: Optional[Dict] = None):
        # Load config from m1_config.py with safe fallbacks
        try:
            from core.Infrastructure.m1_config import (
                OLLAMA_MODEL, CLAUDE_MODEL, KIMI_MODEL,
                OLLAMA_HOST, NVIDIA_API_KEY, ANTHROPIC_API_KEY,
                KIMI_BASE_URL, OLLAMA_TIMEOUT, API_TIMEOUT,
                FALLBACK_CHAIN,
            )
        except ImportError:
            OLLAMA_MODEL = "llama3.2"
            CLAUDE_MODEL = "claude-3-haiku-20240307"
            KIMI_MODEL = "moonshotai/kimi-k2.5"
            OLLAMA_HOST = "http://localhost:11434"
            NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
            ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
            KIMI_BASE_URL = "https://integrate.api.nvidia.com/v1"
            OLLAMA_TIMEOUT = 10
            API_TIMEOUT = 30
            FALLBACK_CHAIN = ["claude", "kimi", "ollama"]

        # Allow runtime overrides
        if config_override:
            OLLAMA_MODEL = config_override.get("ollama_model", OLLAMA_MODEL)
            CLAUDE_MODEL = config_override.get("claude_model", CLAUDE_MODEL)
            KIMI_MODEL = config_override.get("kimi_model", KIMI_MODEL)

        self.ollama_model = OLLAMA_MODEL
        self.claude_model = CLAUDE_MODEL
        self.kimi_model = KIMI_MODEL
        self.ollama_timeout = OLLAMA_TIMEOUT
        self.api_timeout = API_TIMEOUT

        # Map provider keys from FALLBACK_CHAIN to router model names
        self._chain_map = {
            "claude": "primary",
            "kimi": "secondary",
            "ollama": "local_fallback",
        }
        self._fallback_chain = FALLBACK_CHAIN
        self._router = None

        if not LITELLM_AVAILABLE:
            logger.warning("M1ModelRouter disabled: litellm not installed")
            return

        # Build litellm model list
        model_list = [
            {
                "model_name": "primary",
                "litellm_params": {
                    "model": f"anthropic/{self.claude_model}",
                    "api_key": ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY", ""),
                    "timeout": self.api_timeout,
                    "max_retries": 1,
                },
            },
            {
                "model_name": "secondary",
                "litellm_params": {
                    "model": f"openrouter/moonshotai/{self.kimi_model.split('/')[-1]}"
                             if "/" in self.kimi_model
                             else f"openrouter/{self.kimi_model}",
                    "api_key": NVIDIA_API_KEY or os.getenv("NVIDIA_API_KEY", ""),
                    "api_base": KIMI_BASE_URL,
                    "timeout": self.api_timeout + 5,
                    "max_retries": 2,
                },
            },
            {
                "model_name": "local_fallback",
                "litellm_params": {
                    "model": f"ollama/{self.ollama_model}",
                    "api_base": OLLAMA_HOST,
                    "timeout": self.ollama_timeout,
                },
            },
        ]

        # Build fallback chain from config
        fallbacks = []
        for i in range(len(FALLBACK_CHAIN) - 1):
            from_key = self._chain_map.get(FALLBACK_CHAIN[i])
            to_key = self._chain_map.get(FALLBACK_CHAIN[i + 1])
            if from_key and to_key:
                fallbacks.append({from_key: [to_key]})

        try:
            self._router = Router(
                model_list=model_list,
                fallbacks=fallbacks,
                num_retries=1,
                cooldown_time=30,
            )
            logger.info(
                "M1ModelRouter initialized: %s -> %s -> %s",
                FALLBACK_CHAIN[0] if FALLBACK_CHAIN else "none",
                FALLBACK_CHAIN[1] if len(FALLBACK_CHAIN) > 1 else "none",
                FALLBACK_CHAIN[2] if len(FALLBACK_CHAIN) > 2 else "none",
            )
        except Exception as e:
            logger.error("Failed to initialize litellm Router: %s", e)

    # ── Async completion ─────────────────────────────────────────────────

    async def route_completion(
        self,
        messages: List[Dict[str, str]],
        preferred_model: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Route a completion request through the fallback chain.

        Args:
            messages: Chat messages in OpenAI format
            preferred_model: Router model name ("primary", "secondary", "local_fallback")
                            or a provider key ("claude", "kimi", "ollama").
                            Defaults to first in FALLBACK_CHAIN.
            **kwargs: Additional litellm parameters (temperature, max_tokens, etc.)

        Returns:
            Dict with 'content', 'model_used', 'success', and optionally 'usage'.
        """
        if not self._router:
            return {
                "content": "",
                "model_used": "none",
                "success": False,
                "error": "litellm Router not initialized",
            }

        # Resolve provider key to router model name
        model = preferred_model
        if model in self._chain_map:
            model = self._chain_map[model]
        if model is None:
            first_provider = self._fallback_chain[0] if self._fallback_chain else "claude"
            model = self._chain_map.get(first_provider, "primary")

        try:
            response = await self._router.acompletion(
                model=model,
                messages=messages,
                **kwargs,
            )
            return {
                "content": response.choices[0].message.content,
                "model_used": getattr(response, "model", model),
                "success": True,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
            }
        except Exception as e:
            logger.error("M1ModelRouter completion failed: %s", e)
            return {
                "content": "",
                "model_used": model,
                "success": False,
                "error": str(e),
            }

    # ── Complexity-based routing ─────────────────────────────────────────

    async def route_by_complexity(
        self,
        messages: List[Dict[str, str]],
        complexity_score: float = 0.5,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Smart routing based on task complexity.

        Args:
            messages: Chat messages
            complexity_score: 0.0 (trivial) to 1.0 (very complex)
            **kwargs: Additional litellm parameters

        Returns:
            Completion result dict
        """
        if complexity_score < 0.3:
            model = "local_fallback"
        elif complexity_score > 0.8:
            model = "primary"
        else:
            model = "primary"  # Default to best quality, fallback handles errors

        return await self.route_completion(messages, preferred_model=model, **kwargs)

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """Check if the router is initialized and ready."""
        return self._router is not None

    @property
    def model_info(self) -> Dict[str, str]:
        """Return configured model identifiers."""
        return {
            "primary": f"anthropic/{self.claude_model}",
            "secondary": self.kimi_model,
            "local_fallback": f"ollama/{self.ollama_model}",
        }
