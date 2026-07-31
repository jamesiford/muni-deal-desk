"""Handler applying conduct policies to drafted text.

Runs the deterministic domain policies. Kept separate from any model-based content
filter so the two controls are independent: a prompt change cannot disable this one.
"""

from __future__ import annotations

from src.application.messages import ReviewForCompliance
from src.domain.contracts.agent_contracts import ComplianceReview
from src.domain.policies.conduct_policies import DEFAULT_POLICIES, TextPolicy


class ReviewForComplianceHandler:
    """Applies each conduct policy and aggregates the findings."""

    def __init__(self, policies: tuple[TextPolicy, ...] = DEFAULT_POLICIES) -> None:
        self._policies = policies

    async def handle(self, message: ReviewForCompliance) -> ComplianceReview:
        """Evaluate text against every policy.

        A failure blocks the draft rather than annotating it, because returning
        non-compliant language alongside a warning invites it being copied.
        """
        findings = [policy.evaluate(message.text) for policy in self._policies]
        return ComplianceReview(
            findings=findings,
            requires_human_review=True,
            blocking=any(not finding.passed for finding in findings),
        )
