"""
Ambiguity Resolution Engine for Mode 4.

Handles the "the one" problem: when multiple tasks/emails/skills match an
ambiguous user reference, this module scores candidates and either auto-selects
the best match, suggests a short-list, or asks for clarification.

Key features:
    - Fuzzy string matching via rapidfuzz (with graceful fallback)
    - Context boosting: recently-mentioned items get a confidence bump
    - Numbered reference system: "#1" maps to session-stored list indices
    - Ordinal/relative reference parsing: "the first one", "the last one"

Integration point:
    Called from ActionExtractor.extract_params() as fallback when deterministic
    patterns fail and the user's reference is ambiguous.
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Attempt to import rapidfuzz; fall back to simple ratio if unavailable
try:
    from rapidfuzz import fuzz, process as rf_process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    logger.info("rapidfuzz not installed – using built-in fuzzy matching")


# ── Lightweight built-in fuzzy ratio (fallback) ─────────────────────────────

def _builtin_ratio(s1: str, s2: str) -> float:
    """Simple sequence-matcher ratio when rapidfuzz is absent."""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio() * 100


def _fuzzy_score(query: str, candidate: str) -> float:
    """Return 0–100 similarity score between *query* and *candidate*."""
    if RAPIDFUZZ_AVAILABLE:
        return fuzz.token_set_ratio(query, candidate)
    return _builtin_ratio(query, candidate)


# ── Constants ────────────────────────────────────────────────────────────────

ORDINAL_MAP = {
    "first": 0, "1st": 0,
    "second": 1, "2nd": 1,
    "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3,
    "fifth": 4, "5th": 4,
    "last": -1,
    "previous": -1,
}

RECENCY_BOOST = 15.0       # points added for items seen in last 30 min
RECENCY_WINDOW = 30 * 60   # seconds

# Thresholds (on a 0–100 scale)
AUTO_SELECT_THRESHOLD = 90
SUGGEST_THRESHOLD = 70


# ── Disambiguation result ────────────────────────────────────────────────────

class DisambiguationResult:
    """Outcome of an ambiguity-resolution attempt."""

    __slots__ = ("resolved", "selected", "candidates", "clarification_question")

    def __init__(
        self,
        resolved: bool = False,
        selected: Optional[Dict[str, Any]] = None,
        candidates: Optional[List[Dict[str, Any]]] = None,
        clarification_question: Optional[str] = None,
    ):
        self.resolved = resolved
        self.selected = selected
        self.candidates = candidates or []
        self.clarification_question = clarification_question


# ── AmbiguityResolver ────────────────────────────────────────────────────────

class AmbiguityResolver:
    """
    Resolves ambiguous references against a list of candidate entities.

    Typical usage::

        resolver = AmbiguityResolver(session_state)
        result = resolver.resolve(
            user_text="I finished the mandate one",
            candidates=active_tasks,
            candidate_key="title",
            user_id=12345,
        )
        if result.resolved:
            # proceed with result.selected
        else:
            # show result.candidates or result.clarification_question
    """

    def __init__(self, session_state=None):
        """
        Args:
            session_state: Optional SessionState instance for numbered-reference
                           storage and recency tracking.
        """
        self.session = session_state

    # ── public API ───────────────────────────────────────────────────────

    def resolve(
        self,
        user_text: str,
        candidates: List[Dict[str, Any]],
        candidate_key: str = "title",
        user_id: Optional[int] = None,
        ref_type: str = "task_list",
    ) -> DisambiguationResult:
        """
        Attempt to resolve *user_text* against *candidates*.

        Tries, in order:
            1. Explicit numbered reference (#N or ordinals)
            2. Fuzzy match with recency boosting
            3. Clarification request

        Args:
            user_text:      Raw text from user.
            candidates:     List of entity dicts to match against.
            candidate_key:  Dict key whose value is matched (e.g. "title", "subject").
            user_id:        Telegram user id (for session lookups).
            ref_type:       Session reference namespace.

        Returns:
            DisambiguationResult
        """
        if not candidates:
            return DisambiguationResult(
                resolved=False,
                clarification_question="I don't see any items to choose from.",
            )

        # 1. Try numbered reference
        numbered = self._try_numbered_reference(user_text, candidates, user_id, ref_type)
        if numbered is not None:
            return DisambiguationResult(resolved=True, selected=numbered)

        # 2. Try ordinal/relative reference
        ordinal = self._try_ordinal_reference(user_text, candidates)
        if ordinal is not None:
            return DisambiguationResult(resolved=True, selected=ordinal)

        # 3. Fuzzy match
        scored = self._score_candidates(user_text, candidates, candidate_key, user_id)

        if not scored:
            return DisambiguationResult(
                resolved=False,
                clarification_question="I couldn't match that to any items. Could you be more specific?",
            )

        top_score, top_item = scored[0]

        if top_score >= AUTO_SELECT_THRESHOLD:
            return DisambiguationResult(resolved=True, selected=top_item)

        if top_score >= SUGGEST_THRESHOLD:
            # Return top 2 as suggestions
            suggestions = [item for _, item in scored[:2]]
            titles = [s.get(candidate_key, "?") for s in suggestions]
            question = "Which one did you mean?\n"
            for i, t in enumerate(titles, 1):
                question += f"  [{i}] {t}\n"
            return DisambiguationResult(
                resolved=False,
                candidates=suggestions,
                clarification_question=question,
            )

        # Low confidence – ask openly
        return DisambiguationResult(
            resolved=False,
            candidates=[item for _, item in scored[:3]],
            clarification_question="I'm not sure which one you mean. Could you give me more details?",
        )

    # ── numbered references (#1, #2 …) ──────────────────────────────────

    def _try_numbered_reference(
        self,
        text: str,
        candidates: List[Dict],
        user_id: Optional[int],
        ref_type: str,
    ) -> Optional[Dict]:
        """Check for '#N', 'number N', 'task N' patterns."""
        m = re.search(r"#(\d+)|(?:number|task|item)\s+(\d+)", text, re.IGNORECASE)
        if not m:
            return None
        idx = int(m.group(1) or m.group(2))

        # Try stored session references first
        if self.session and user_id is not None:
            stored = self.session.get_reference(user_id, ref_type)
            if stored and isinstance(stored, list) and 0 < idx <= len(stored):
                return stored[idx - 1]

        # Fall back to candidates by position or id
        for c in candidates:
            if c.get("id") == idx or c.get("number") == idx:
                return c

        if 0 < idx <= len(candidates):
            return candidates[idx - 1]

        return None

    # ── ordinal references ("the first one", "the last one") ─────────────

    def _try_ordinal_reference(
        self,
        text: str,
        candidates: List[Dict],
    ) -> Optional[Dict]:
        """Parse ordinal/relative words and map to candidate list index."""
        text_lower = text.lower()
        for word, idx in ORDINAL_MAP.items():
            if word in text_lower:
                try:
                    return candidates[idx]
                except IndexError:
                    return None
        return None

    # ── fuzzy scoring with recency boost ─────────────────────────────────

    def _score_candidates(
        self,
        query: str,
        candidates: List[Dict],
        key: str,
        user_id: Optional[int],
    ) -> List[Tuple[float, Dict]]:
        """Return candidates sorted by descending fuzzy score."""
        now = time.time()
        scored: List[Tuple[float, Dict]] = []

        for c in candidates:
            title = str(c.get(key, ""))
            score = _fuzzy_score(query, title)

            # Recency boost
            ts = c.get("updated_at") or c.get("created_at") or c.get("timestamp")
            if ts:
                try:
                    if isinstance(ts, (int, float)):
                        age = now - ts
                    else:
                        from datetime import datetime
                        age = now - datetime.fromisoformat(str(ts)).timestamp()
                    if age < RECENCY_WINDOW:
                        score += RECENCY_BOOST
                except (ValueError, TypeError, OSError):
                    pass

            scored.append((min(score, 100.0), c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    # ── store references for later retrieval ─────────────────────────────

    def store_displayed_list(
        self,
        user_id: int,
        ref_type: str,
        items: List[Dict],
    ):
        """Persist a displayed list so '#N' can resolve later."""
        if self.session:
            self.session.store_reference(user_id, ref_type, items)
