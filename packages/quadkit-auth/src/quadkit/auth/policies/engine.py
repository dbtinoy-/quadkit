"""Policy Engine for ABAC evaluation."""

from __future__ import annotations

import re
import threading
from typing import TYPE_CHECKING, Literal, Protocol

from quadkit.auth.policies.evaluator import ConditionEvaluator
from quadkit.auth.policies.types import (
    AuthorizationDecision,
    AuthorizationRequest,
    DecisionOutcome,
    Policy,
    PolicyEffect,
)
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.auth.policy import PolicyStoreProtocol

logger = get_logger(__name__)


# =============================================================================
# Pattern Matcher Registry
# =============================================================================


class PatternMatcher(Protocol):
    """Protocol for pattern matchers."""

    def can_match(self, pattern: str) -> bool:
        """Check if this matcher can handle the given pattern."""
        ...

    def matches(self, pattern: str, target: str) -> bool:
        """Check if the target matches the pattern."""
        ...


class ExactPatternMatcher:
    """Matches exact string patterns without wildcards."""

    def can_match(self, pattern: str) -> bool:
        return "*" not in pattern

    def matches(self, pattern: str, target: str) -> bool:
        return pattern == target


class WildcardPatternMatcher:
    """Matches wildcard patterns using regex."""

    def can_match(self, pattern: str) -> bool:
        return "*" in pattern

    def matches(self, pattern: str, target: str) -> bool:
        regex = "^" + pattern.replace("*", ".*") + "$"
        return bool(re.match(regex, target))


class GlobPatternMatcher:
    """Matches glob-style patterns (e.g., 'user.*' matches 'user.read')."""

    def can_match(self, pattern: str) -> bool:
        return "." in pattern and "*" in pattern

    def matches(self, pattern: str, target: str) -> bool:
        # Convert glob pattern to regex
        regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
        regex = f"^{regex_pattern}$"
        return bool(re.match(regex, target))


class PatternMatcherRegistry:
    """Registry for pattern matchers.

    Provides extensible pattern matching for policy evaluation.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._matchers: list[PatternMatcher] = []

    @classmethod
    def _default_entries(cls) -> dict[str, PatternMatcher]:
        """Declare the standard pattern matchers (exact, wildcard)."""
        return {
            "exact": ExactPatternMatcher(),
            "wildcard": WildcardPatternMatcher(),
        }

    @classmethod
    def with_defaults(cls) -> PatternMatcherRegistry:
        """Create a registry pre-loaded with the standard pattern matchers."""
        instance = cls()
        instance._matchers = list(cls._default_entries().values())
        return instance

    def register_matcher(self, matcher: PatternMatcher) -> None:
        """Register a custom pattern matcher."""
        with self._lock:
            self._matchers.insert(0, matcher)

    def matches(self, pattern: str, target: str) -> bool:
        """Check if the target matches the pattern using registered matchers."""
        with self._lock:
            matchers = list(self._matchers)
        for matcher in matchers:
            if matcher.can_match(pattern):
                return matcher.matches(pattern, target)
        return False


class PolicyEngine:
    """Evaluates authorization requests against a collection of policies.

    Three evaluation strategies are supported, selected at construction time via
    the ``strategy`` parameter:

    * ``"deny_first"`` *(default)* — the first **DENY** match short-circuits
      evaluation and the request is immediately rejected.  Any subsequent
      ALLOW policies are never reached.  This is the most secure default and
      the one mandated by most enterprise security frameworks.

    * ``"allow_first"`` — the first **ALLOW** match short-circuits evaluation
      and the request is immediately granted.  Useful for additive permission
      models where policies are non-conflicting.

    * ``"unanimous"`` — every matching policy must be an ALLOW; a single DENY
      (or INDETERMINATE, i.e. no matching ALLOW) causes the request to be
      denied.  Suitable for high-security contexts where all gates must pass.
    """

    def __init__(
        self,
        policies: list[Policy] | None = None,
        *,
        store: PolicyStoreProtocol | None = None,
        strategy: Literal["deny_first", "allow_first", "unanimous"] = "deny_first",
    ) -> None:
        """Initialise the policy engine with a static list and/or a store.

        Args:
            policies: Optional list of in-memory policies.  Sorted by
                priority (descending) so that the highest-priority policy
                wins on conflict.
            store: Optional :class:`~quadkit.contracts.auth.policy.PolicyStoreProtocol`
                used to load/persist policies asynchronously.  When provided,
                call :meth:`load_from_store` during application boot to merge
                the stored policies with any static ones.
            strategy: Evaluation strategy controlling short-circuit behaviour.

                * ``"deny_first"`` — first DENY wins (most secure, default).
                * ``"allow_first"`` — first ALLOW wins (additive model).
                * ``"unanimous"`` — all matching policies must be ALLOW.
        """
        self.policies: list[Policy] = sorted(
            policies or [],
            key=lambda p: p.priority,
            reverse=True,
        )
        self._store: PolicyStoreProtocol | None = store
        self._strategy: Literal["deny_first", "allow_first", "unanimous"] = strategy
        self.evaluator = ConditionEvaluator()
        self._pattern_matchers = PatternMatcherRegistry.with_defaults()
        # Resource-pattern index for O(1) candidate lookup in evaluate().
        # Keys are exact resource patterns; the special key "" covers catch-all
        # policies (empty resources list).  Wildcard-containing patterns are
        # stored separately in _wildcard_resource_policies so they are always
        # checked via pattern matching.
        self._resource_index: dict[str, list[Policy]] = {}
        self._wildcard_resource_policies: list[Policy] = []
        self._rebuild_resource_index()

    def __repr__(self) -> str:
        """Return developer-friendly string representation."""
        return f"PolicyEngine(policies={len(self.policies)})"

    def _rebuild_resource_index(self) -> None:
        """Rebuild the resource-pattern index from ``self.policies``.

        Exact resource patterns are indexed for O(1) lookup.  Wildcard
        patterns (containing ``*``) are gathered in
        ``_wildcard_resource_policies`` so they are always evaluated via
        the full pattern-match path.  Catch-all policies (empty
        ``resources`` list) are stored under the ``""`` key.
        """
        index: dict[str, list[Policy]] = {}
        wildcard: list[Policy] = []
        for policy in self.policies:
            if not policy.resources:
                index.setdefault("", []).append(policy)
            else:
                has_wildcard = False
                for pattern in policy.resources:
                    if "*" in pattern:
                        has_wildcard = True
                    else:
                        index.setdefault(pattern, []).append(policy)
                if has_wildcard:
                    wildcard.append(policy)
        self._resource_index = index
        self._wildcard_resource_policies = wildcard

    async def load_from_store(self) -> None:
        """Load policies from the configured :class:`PolicyStoreProtocol`.

        Fetches all policies from the store and merges them with any
        statically registered policies, re-sorting the combined list by
        priority.  A no-op if no store was provided at construction time.

        Raises:
            RuntimeError: If no store was provided when this method is called.
        """
        if self._store is None:
            return
        stored = await self._store.load_policies()
        merged = {**{p.name: p for p in self.policies}, **{p.name: p for p in stored}}
        self.policies = sorted(merged.values(), key=lambda p: p.priority, reverse=True)
        self._rebuild_resource_index()
        logger.info("policy_engine.loaded_from_store", count=len(stored))

    async def save_policy(self, policy: Policy) -> None:
        """Persist a policy to the store and add it to the in-memory list.

        Args:
            policy: The policy to persist.

        Raises:
            RuntimeError: If no store was configured.
        """
        if self._store is None:
            msg = "Cannot persist policy: PolicyEngine has no store configured"
            raise RuntimeError(msg)
        await self._store.save_policy(policy)
        # Merge into in-memory list (replace any existing policy with same name)
        self.policies = sorted(
            [p for p in self.policies if p.name != policy.name] + [policy],
            key=lambda p: p.priority,
            reverse=True,
        )
        self._rebuild_resource_index()
        logger.info("policy_engine.policy_saved", policy=policy.name)

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        """Evaluate an authorization request against loaded policies.

        Short-circuit behaviour is governed by ``self._strategy``:

        * ``deny_first`` — first DENY match returns immediately.
        * ``allow_first`` — first ALLOW match returns immediately.
        * ``unanimous``  — every matching policy must be ALLOW; a single DENY
          or the absence of any ALLOW yields DENY/INDETERMINATE respectively.
        """
        # Build candidate set using the resource index to avoid a full scan.
        # Priority order is preserved via sorted self.policies insertion order.
        seen: set[str] = set()
        candidates: list[Policy] = []

        # 1. Catch-all policies (empty resources list)
        for p in self._resource_index.get("", []):
            if p.policy_id not in seen:
                seen.add(p.policy_id)
                candidates.append(p)

        # 2. Exact resource-pattern match
        for p in self._resource_index.get(request.resource, []):
            if p.policy_id not in seen:
                seen.add(p.policy_id)
                candidates.append(p)

        # 3. Wildcard resource patterns (must still be pattern-matched below)
        for p in self._wildcard_resource_policies:
            if p.policy_id not in seen:
                seen.add(p.policy_id)
                candidates.append(p)

        # Re-sort the smaller candidate set by priority (descending)
        candidates.sort(key=lambda p: p.priority, reverse=True)

        matched_policies: list[str] = []
        allow_found = False

        for policy in candidates:
            if not self._matches(policy, request):
                continue

            matched_policies.append(policy.policy_id)

            if self._strategy == "deny_first":
                # First DENY wins — most secure default.
                if policy.effect == PolicyEffect.DENY:
                    logger.info("Access DENIED by policy (deny_first): %s", policy.name)
                    return AuthorizationDecision(
                        decision=DecisionOutcome.DENY,
                        reason=f"Denied by policy: {policy.name}",
                        applied_policies=matched_policies,
                    )
                if policy.effect == PolicyEffect.ALLOW:
                    allow_found = True

            elif self._strategy == "allow_first":
                # First ALLOW wins — additive model, stops on first grant.
                if policy.effect == PolicyEffect.ALLOW:
                    logger.info(
                        "Access ALLOWED by policy (allow_first): %s", policy.name
                    )
                    return AuthorizationDecision(
                        decision=DecisionOutcome.ALLOW,
                        reason=f"Allowed by policy: {policy.name}",
                        applied_policies=matched_policies,
                    )
                if policy.effect == PolicyEffect.DENY:
                    allow_found = False  # keep scanning but track deny seen

            else:  # unanimous
                # Every matching policy must be ALLOW; a single DENY short-circuits.
                if policy.effect == PolicyEffect.DENY:
                    logger.info("Access DENIED by policy (unanimous): %s", policy.name)
                    return AuthorizationDecision(
                        decision=DecisionOutcome.DENY,
                        reason=f"Denied by policy: {policy.name}",
                        applied_policies=matched_policies,
                    )
                if policy.effect == PolicyEffect.ALLOW:
                    allow_found = True

        if allow_found:
            return AuthorizationDecision(
                decision=DecisionOutcome.ALLOW,
                applied_policies=matched_policies,
            )

        return AuthorizationDecision(
            decision=DecisionOutcome.INDETERMINATE,
            reason="No matching policies found",
            applied_policies=matched_policies,
        )

    def _matches(self, policy: Policy, request: AuthorizationRequest) -> bool:
        """Check if a policy applies to the given request."""
        # 1. Match Action
        if not self._pattern_match(policy.actions, request.action):
            return False

        # 2. Match Resource
        if not self._pattern_match(policy.resources, request.resource):
            return False

        # 3. Match Principal
        if not self._pattern_match(policy.principals, request.principal):
            return False

        # 4. Evaluate Conditions
        for cond in policy.conditions:
            if not self.evaluator.evaluate(cond, request.context):
                return False

        return True

    def _pattern_match(self, patterns: list[str], target: str) -> bool:
        """Check if target matches any of the patterns using the registry."""
        if not patterns:
            return True  # Empty means matches all

        for pattern in patterns:
            if self._pattern_matchers.matches(pattern, target):
                return True

        return False


__all__ = [
    "ExactPatternMatcher",
    "GlobPatternMatcher",
    "PatternMatcher",
    "PatternMatcherRegistry",
    "PolicyEngine",
    "WildcardPatternMatcher",
    "logger",
]
