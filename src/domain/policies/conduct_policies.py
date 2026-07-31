"""Guardrail policies modelled on municipal securities conduct obligations.

These policies are deterministic and run in the domain layer, independent of any model
output filtering. That matters for two reasons: a demo needs a guardrail that fires the
same way on every run, and a regulated firm needs a control that does not depend on a
model choosing to behave.

Regulatory basis, described accurately and without offering legal advice:

* MSRB Rule G-17 requires dealers to deal fairly and, in negotiated underwritings, to
  disclose in writing that the underwriter is not acting as a municipal advisor or
  fiduciary to the issuer. Draft language that implies advisory or fiduciary standing
  therefore conflicts with the disclosure the firm is obliged to make.
* MSRB Rule G-42 imposes a fiduciary duty on non-solicitor municipal advisors. A firm
  cannot serve as both underwriter and municipal advisor on the same transaction.
* FINRA Regulatory Notice 24-09 confirms FINRA's rules apply to generative AI on a
  technology-neutral basis, including Rule 3110 supervision and Rule 2210
  communications standards.

These checks model those obligations. They do not certify compliance with them.
"""

from __future__ import annotations

import re
from typing import Protocol

from src.domain.contracts.agent_contracts import PolicyFinding


class TextPolicy(Protocol):
    """A deterministic check applied to generated text."""

    policy_id: str

    def evaluate(self, text: str) -> PolicyFinding:
        """Assess text and return a finding."""
        ...


def _first_match(text: str, patterns: tuple[str, ...]) -> str | None:
    """Return the first matching span, or None. Case-insensitive."""
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return None


class FiduciaryImplicationPolicy:
    """Reject drafts implying the firm acts as advisor or fiduciary to the issuer.

    Modelled on the MSRB Rule G-17 disclosure obligation in negotiated underwritings.
    An underwriter's arm's-length role is the point of that disclosure, so language
    asserting the opposite is the clearest thing to detect.
    """

    policy_id = "msrb-g17-fiduciary-implication"

    _PATTERNS: tuple[str, ...] = (
        r"\bas your (?:financial )?(?:advisor|adviser)\b",
        r"\bacting as (?:your |the )?(?:municipal )?(?:advisor|adviser)\b",
        r"\bfiduciary (?:duty|capacity|obligation)\b",
        r"\bin your best interests?\b",
        r"\bwe (?:advise|recommend) (?:that )?(?:you|the district|the issuer)\b",
    )

    def evaluate(self, text: str) -> PolicyFinding:
        """Flag language implying advisory or fiduciary standing."""
        offending = _first_match(text, self._PATTERNS)
        if offending is None:
            return PolicyFinding(
                policy_id=self.policy_id,
                passed=True,
                detail="No language implying advisory or fiduciary standing was found.",
            )
        return PolicyFinding(
            policy_id=self.policy_id,
            passed=False,
            detail=(
                "Draft implies an advisory or fiduciary relationship with the issuer. "
                "In a negotiated underwriting the firm must disclose it is not acting "
                "as a municipal advisor, so this language must be revised before use."
            ),
            offending_text=offending,
        )


class RetailRecommendationPolicy:
    """Reject investment recommendations directed at investors.

    The Deal Desk supports bankers preparing issuer-facing materials. A securities
    recommendation to an investor is a different activity carrying suitability and
    best-interest obligations, and is out of scope for this agent by design.
    """

    policy_id = "retail-recommendation-out-of-scope"

    _PATTERNS: tuple[str, ...] = (
        r"\b(?:you|investors?|clients?) should (?:buy|purchase|sell|invest)\b",
        r"\bwe recommend (?:buying|purchasing|selling|investing)\b",
        r"\b(?:a |an )?(?:attractive|compelling|strong) (?:buy|investment opportunity)\b",
        r"\bsuitable for (?:retail |individual )?investors?\b",
    )

    def evaluate(self, text: str) -> PolicyFinding:
        """Flag investor-directed recommendation language."""
        offending = _first_match(text, self._PATTERNS)
        if offending is None:
            return PolicyFinding(
                policy_id=self.policy_id,
                passed=True,
                detail="No investor-directed recommendation language was found.",
            )
        return PolicyFinding(
            policy_id=self.policy_id,
            passed=False,
            detail=(
                "Draft contains an investment recommendation directed at investors. "
                "This agent supports issuer-facing banker workflows and does not "
                "produce securities recommendations."
            ),
            offending_text=offending,
        )


class UncitedFigurePolicy:
    """Require that monetary and rate figures carry a citation marker.

    A figure without provenance is the failure mode that matters most in this domain,
    because it is the one a reviewer is least likely to catch by reading.
    """

    policy_id = "uncited-figure"

    _FIGURE = re.compile(r"(?:\$[\d,]+(?:\.\d+)?(?:\s?(?:million|billion))?|\b\d+\.\d{2}\s?%)")
    _CITATION_MARKER = re.compile(r"\[(?:cite|source):[^\]]+\]")

    def evaluate(self, text: str) -> PolicyFinding:
        """Flag sentences containing figures but no citation marker."""
        uncited: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if self._FIGURE.search(sentence) and not self._CITATION_MARKER.search(sentence):
                uncited.append(sentence.strip())

        if not uncited:
            return PolicyFinding(
                policy_id=self.policy_id,
                passed=True,
                detail="All monetary and rate figures carry a citation marker.",
            )
        return PolicyFinding(
            policy_id=self.policy_id,
            passed=False,
            detail=(
                f"{len(uncited)} statement(s) contain a figure without a citation. "
                "Figures reaching a client document must be traceable to a source."
            ),
            offending_text=uncited[0],
        )


DEFAULT_POLICIES: tuple[TextPolicy, ...] = (
    FiduciaryImplicationPolicy(),
    RetailRecommendationPolicy(),
    UncitedFigurePolicy(),
)
