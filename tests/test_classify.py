"""Tests for verdict classification with exact edge thresholds and unverified cap behavior."""

from __future__ import annotations

import pytest

from vallejo_scraper.models import RentSource, VerdictLabel
from vallejo_scraper.underwriter import classify


class TestVerifiedThresholds:
    """Verified rent source (listing_disclosed) thresholds."""

    def test_gap_exactly_5_pct_is_tour_candidate(self) -> None:
        mrp = 100_000.0
        ask = 105_000.0  # gap = +5%
        verdict = classify(ask, mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.tour_candidate
        assert verdict.gap_pct == pytest.approx(0.05)

    def test_gap_below_5_pct_is_tour_candidate(self) -> None:
        mrp = 100_000.0
        ask = 103_000.0  # gap = +3%
        verdict = classify(ask, mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.tour_candidate

    def test_gap_negative_is_tour_candidate(self) -> None:
        mrp = 100_000.0
        ask = 90_000.0  # gap = -10%
        verdict = classify(ask, mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.tour_candidate

    def test_gap_exactly_12_pct_is_conditional_watchlist(self) -> None:
        mrp = 100_000.0
        ask = 112_000.0  # gap = +12%
        verdict = classify(ask, mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.conditional_watchlist
        assert verdict.gap_pct == pytest.approx(0.12)

    def test_gap_6_pct_is_conditional_watchlist(self) -> None:
        mrp = 100_000.0
        ask = 106_000.0  # gap = +6%
        verdict = classify(ask, mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.conditional_watchlist

    def test_gap_exactly_20_pct_is_passive_watchlist(self) -> None:
        mrp = 100_000.0
        ask = 120_000.0  # gap = +20%
        verdict = classify(ask, mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.passive_watchlist
        assert verdict.gap_pct == pytest.approx(0.20)

    def test_gap_15_pct_is_passive_watchlist(self) -> None:
        mrp = 100_000.0
        ask = 115_000.0  # gap = +15%
        verdict = classify(ask, mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.passive_watchlist

    def test_gap_21_pct_is_graveyard(self) -> None:
        mrp = 100_000.0
        ask = 121_000.0  # gap = +21%
        verdict = classify(ask, mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.graveyard

    def test_gap_50_pct_is_graveyard(self) -> None:
        mrp = 100_000.0
        ask = 150_000.0  # gap = +50%
        verdict = classify(ask, mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.graveyard


class TestUnverifiedCapBehavior:
    """Unverified rent sources are capped at conditional_watchlist_unverified."""

    def test_unverified_below_5_pct_capped_to_conditional_unverified(self) -> None:
        """Tour candidate gap with unverified rent → capped to conditional_watchlist_unverified."""
        mrp = 100_000.0
        ask = 103_000.0  # gap = +3% → would be tour_candidate if verified
        verdict = classify(ask, mrp, RentSource.rentcast_estimate)
        assert verdict.label == VerdictLabel.conditional_watchlist_unverified

    def test_unverified_exactly_5_pct_capped(self) -> None:
        mrp = 100_000.0
        ask = 105_000.0
        verdict = classify(ask, mrp, RentSource.estimated_from_sqft)
        assert verdict.label == VerdictLabel.conditional_watchlist_unverified

    def test_unverified_10_pct_is_conditional_unverified(self) -> None:
        mrp = 100_000.0
        ask = 110_000.0
        verdict = classify(ask, mrp, RentSource.rentcast_estimate)
        assert verdict.label == VerdictLabel.conditional_watchlist_unverified

    def test_unverified_15_pct_is_passive_unverified(self) -> None:
        mrp = 100_000.0
        ask = 115_000.0
        verdict = classify(ask, mrp, RentSource.estimated_from_sqft)
        assert verdict.label == VerdictLabel.passive_watchlist_unverified

    def test_unverified_25_pct_is_graveyard_unverified(self) -> None:
        mrp = 100_000.0
        ask = 125_000.0
        verdict = classify(ask, mrp, RentSource.unknown)
        assert verdict.label == VerdictLabel.graveyard_unverified

    def test_unknown_rent_source_is_unverified(self) -> None:
        mrp = 100_000.0
        ask = 102_000.0
        verdict = classify(ask, mrp, RentSource.unknown)
        assert verdict.label == VerdictLabel.conditional_watchlist_unverified


class TestReferenceDealVerdicts:
    """Verify verdicts for the three reference deals end-to-end via classify."""

    def test_302_carolina_tour_candidate(self) -> None:
        # MRP ~608K, ask 599K → gap negative → tour_candidate
        from vallejo_scraper.underwriter import calculate_mrp

        mrp_result = calculate_mrp(6000.0, 3)
        verdict = classify(599_000.0, mrp_result.mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.tour_candidate

    def test_706_porter_passive_watchlist(self) -> None:
        # MRP ~400K, ask 450K → gap ~12.5% → passive_watchlist
        from vallejo_scraper.underwriter import calculate_mrp

        mrp_result = calculate_mrp(4200.0, 3)
        verdict = classify(450_000.0, mrp_result.mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.passive_watchlist

    def test_2008_marin_passive_watchlist(self) -> None:
        # MRP ~690K, ask 809K → gap ~17% → passive_watchlist
        from vallejo_scraper.underwriter import calculate_mrp

        mrp_result = calculate_mrp(6800.0, 3)
        verdict = classify(809_000.0, mrp_result.mrp, RentSource.listing_disclosed)
        assert verdict.label == VerdictLabel.passive_watchlist
