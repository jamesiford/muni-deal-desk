"""Conduct policy tests.

These policies gate client-facing text, so each is tested for both the pass and the
fail path. The failing cases double as the phrasings demonstrated during the session.
"""

from __future__ import annotations

from src.domain.policies.conduct_policies import (
    FiduciaryImplicationPolicy,
    RetailRecommendationPolicy,
    UncitedFigurePolicy,
)


class TestFiduciaryImplicationPolicy:
    def test_passes_arms_length_language(self):
        policy = FiduciaryImplicationPolicy()
        text = (
            "As underwriter, the firm proposes the structure below for the "
            "District's consideration."
        )
        assert policy.evaluate(text).passed

    def test_flags_advisor_claim(self):
        policy = FiduciaryImplicationPolicy()
        finding = policy.evaluate("Acting as your municipal advisor, we propose this structure.")
        assert not finding.passed
        assert finding.offending_text is not None

    def test_flags_fiduciary_duty_claim(self):
        policy = FiduciaryImplicationPolicy()
        assert not policy.evaluate("We owe a fiduciary duty to the District.").passed

    def test_flags_best_interests_claim(self):
        policy = FiduciaryImplicationPolicy()
        assert not policy.evaluate("This structure is in your best interest.").passed

    def test_is_case_insensitive(self):
        policy = FiduciaryImplicationPolicy()
        assert not policy.evaluate("ACTING AS YOUR MUNICIPAL ADVISOR, we propose.").passed


class TestRetailRecommendationPolicy:
    def test_passes_structural_description(self):
        policy = RetailRecommendationPolicy()
        text = "The 2025 series priced with a 10-year par call [cite: OS-2025-014 p.12]."
        assert policy.evaluate(text).passed

    def test_flags_investor_directed_recommendation(self):
        policy = RetailRecommendationPolicy()
        finding = policy.evaluate("Investors should buy these bonds at the offered yield.")
        assert not finding.passed

    def test_flags_suitability_language(self):
        policy = RetailRecommendationPolicy()
        assert not policy.evaluate("These bonds are suitable for retail investors.").passed


class TestUncitedFigurePolicy:
    def test_passes_cited_figure(self):
        policy = UncitedFigurePolicy()
        text = "The series totalled $85,000,000 [cite: OS-2025-014 p.1]."
        assert policy.evaluate(text).passed

    def test_flags_uncited_dollar_figure(self):
        policy = UncitedFigurePolicy()
        finding = policy.evaluate("The series totalled $85,000,000.")
        assert not finding.passed
        assert finding.offending_text is not None

    def test_flags_uncited_rate(self):
        policy = UncitedFigurePolicy()
        assert not policy.evaluate("The bonds carried a 4.25 % coupon.").passed

    def test_flags_only_the_uncited_sentence(self):
        policy = UncitedFigurePolicy()
        text = (
            "The series totalled $85,000,000 [cite: OS-2025-014 p.1]. "
            "A later series priced at $42,500,000."
        )
        finding = policy.evaluate(text)
        assert not finding.passed
        assert "42,500,000" in (finding.offending_text or "")

    def test_passes_text_without_figures(self):
        policy = UncitedFigurePolicy()
        assert policy.evaluate("The District expects to issue in the autumn.").passed
