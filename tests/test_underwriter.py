"""Tests for the MRP underwriting calculation using reference deals.

Reference deals use hardcoded inputs and do NOT exercise the RentCast
provider or require network access.
"""

from __future__ import annotations

import pytest

from vallejo_scraper.underwriter import calculate_mrp


class TestReferenceDeal302Carolina:
    """302 Carolina: $6,000/mo, 3 units, ask $599,000 → MRP ~$608K, tour_candidate."""

    def setup_method(self) -> None:
        self.result = calculate_mrp(monthly_rent_total=6000.0, num_units=3)

    def test_gross_annual_rent(self) -> None:
        assert self.result.gross_annual_rent == 6000.0 * 12

    def test_egi(self) -> None:
        expected_egi = 72000.0 * (1 - 0.05)
        assert abs(self.result.egi - expected_egi) < 0.01

    def test_mrp_within_5_percent(self) -> None:
        # MRP should be about $608K
        expected_mrp = 608_000.0
        pct_diff = abs(self.result.mrp - expected_mrp) / expected_mrp
        assert pct_diff < 0.05, (
            f"MRP {self.result.mrp:.0f} is more than 5% off expected {expected_mrp:.0f} "
            f"(diff={pct_diff:.2%})"
        )

    def test_noi_pretax_positive(self) -> None:
        assert self.result.noi_pretax > 0


class TestReferenceDeal706Porter:
    """706 Porter: $4,200/mo, 3 units, ask $450,000 → MRP ~$400K, gap ~+12.5%."""

    def setup_method(self) -> None:
        self.result = calculate_mrp(monthly_rent_total=4200.0, num_units=3)

    def test_mrp_within_5_percent(self) -> None:
        expected_mrp = 400_000.0
        pct_diff = abs(self.result.mrp - expected_mrp) / expected_mrp
        assert pct_diff < 0.05, (
            f"MRP {self.result.mrp:.0f} is more than 5% off expected {expected_mrp:.0f} "
            f"(diff={pct_diff:.2%})"
        )

    def test_gap_pct(self) -> None:
        ask_price = 450_000.0
        gap_pct = (ask_price - self.result.mrp) / self.result.mrp
        # Plan approximates ~12.5% but exact formula yields ~17.6% (MRP~383K
        # is within 5% of ~400K).  Verdict remains passive_watchlist either way.
        assert 0.12 <= gap_pct <= 0.20, f"Gap {gap_pct:.2%} outside expected range [12%-20%]"


class TestReferenceDeal2008Marin:
    """2008 Marin: $6,800/mo, 3 units, ask $809,000 → MRP ~$690K, gap ~+17%."""

    def setup_method(self) -> None:
        self.result = calculate_mrp(monthly_rent_total=6800.0, num_units=3)

    def test_mrp_within_5_percent(self) -> None:
        expected_mrp = 690_000.0
        pct_diff = abs(self.result.mrp - expected_mrp) / expected_mrp
        assert pct_diff < 0.05, (
            f"MRP {self.result.mrp:.0f} is more than 5% off expected {expected_mrp:.0f} "
            f"(diff={pct_diff:.2%})"
        )

    def test_gap_pct(self) -> None:
        ask_price = 809_000.0
        gap_pct = (ask_price - self.result.mrp) / self.result.mrp
        # gap should be about +17%
        assert 0.14 <= gap_pct <= 0.20, f"Gap {gap_pct:.2%} outside expected range [14%-20%]"


class TestMRPFormulaDetails:
    """Verify intermediate values in the MRP formula."""

    def test_opex_components(self) -> None:
        result = calculate_mrp(monthly_rent_total=5000.0, num_units=2)

        gross = 5000.0 * 12
        egi = gross * 0.95
        assert result.gross_annual_rent == pytest.approx(gross)
        assert result.egi == pytest.approx(egi)
        assert result.management == pytest.approx(egi * 0.08)
        assert result.maintenance == pytest.approx(egi * 0.085)
        assert result.capex_reserves == pytest.approx(150.0 * 2 * 12)

        expected_opex = (egi * 0.08) + (egi * 0.085) + (150.0 * 2 * 12) + 2400.0 + 600.0
        assert result.total_opex == pytest.approx(expected_opex)
        assert result.noi_pretax == pytest.approx(egi - expected_opex)
        assert result.mrp == pytest.approx((egi - expected_opex) / 0.0825)

    def test_zero_rent(self) -> None:
        result = calculate_mrp(monthly_rent_total=0.0, num_units=2)
        assert result.gross_annual_rent == 0.0
        assert result.egi == 0.0
        assert result.noi_pretax < 0
        assert result.mrp < 0
