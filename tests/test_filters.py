"""Tests for TargetFilters validation and default loading."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vallejo_scraper import config
from vallejo_scraper.models import TargetFilters


class TestTargetFiltersDefaults:
    """Defaults should come from config module constants."""

    def test_defaults_match_config(self) -> None:
        f = TargetFilters()
        assert f.min_price == config.MIN_PRICE
        assert f.max_price == config.MAX_PRICE
        assert f.min_units == config.MIN_UNITS
        assert f.max_units == config.MAX_UNITS
        assert f.city == config.TARGET_CITY
        assert f.state == config.TARGET_STATE
        assert f.active_only == config.ACTIVE_ONLY

    def test_partial_override_keeps_other_defaults(self) -> None:
        f = TargetFilters(min_price=500_000)
        assert f.min_price == 500_000
        assert f.max_price == config.MAX_PRICE
        assert f.min_units == config.MIN_UNITS

    def test_all_overrides(self) -> None:
        f = TargetFilters(min_price=300_000, max_price=900_000, min_units=3, max_units=6)
        assert f.min_price == 300_000
        assert f.max_price == 900_000
        assert f.min_units == 3
        assert f.max_units == 6


class TestTargetFiltersValidation:
    """Validation rules from the plan."""

    def test_min_price_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="min_price must be >= 0"):
            TargetFilters(min_price=-1)

    def test_max_price_below_min_rejected(self) -> None:
        with pytest.raises(ValidationError, match="max_price must be >= min_price"):
            TargetFilters(min_price=600_000, max_price=400_000)

    def test_min_units_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unit counts"):
            TargetFilters(min_units=0)

    def test_max_units_exceeds_10_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unit counts"):
            TargetFilters(max_units=11)

    def test_max_units_below_min_units_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unit counts"):
            TargetFilters(min_units=5, max_units=3)

    def test_min_price_zero_accepted(self) -> None:
        f = TargetFilters(min_price=0)
        assert f.min_price == 0

    def test_boundary_units_accepted(self) -> None:
        f = TargetFilters(min_units=1, max_units=10)
        assert f.min_units == 1
        assert f.max_units == 10

    def test_equal_price_accepted(self) -> None:
        f = TargetFilters(min_price=500_000, max_price=500_000)
        assert f.min_price == f.max_price

    def test_equal_units_accepted(self) -> None:
        f = TargetFilters(min_units=3, max_units=3)
        assert f.min_units == f.max_units

    def test_units_above_4_accepted(self) -> None:
        """Plan: unit counts above 4 are allowed so the user can screen larger small multifamily."""
        f = TargetFilters(min_units=2, max_units=8)
        assert f.max_units == 8
