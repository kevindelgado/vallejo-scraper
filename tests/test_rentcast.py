"""Tests for the RentCast provider using mocked JSON fixtures.

Tests do NOT consume API quota or require network access.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from vallejo_scraper.models import RentSource
from vallejo_scraper.rentcast import (
    RentCastError,
    _parse_listing,
    fetch_sale_listings,
)

# ---------------------------------------------------------------------------
# Fixture: sample RentCast sale listing JSON
# ---------------------------------------------------------------------------
SAMPLE_LISTING_JSON = {
    "id": "123-Main-St,-Vallejo,-CA-94590",
    "formattedAddress": "123 Main St, Vallejo, CA 94590",
    "addressLine1": "123 Main St",
    "city": "Vallejo",
    "state": "CA",
    "zipCode": "94590",
    "price": 550000,
    "propertyType": "Multi-Family",
    "bedrooms": 4,
    "bathrooms": 2,
    "squareFootage": 2400,
    "yearBuilt": 1965,
    "daysOnMarket": 15,
    "status": "Active",
    "mlsNumber": "ML81999999",
}

SAMPLE_LISTING_WITH_RENT = {
    **SAMPLE_LISTING_JSON,
    "monthlyRent": 4800,
}

SAMPLE_LISTING_WITH_ESTIMATE = {
    **SAMPLE_LISTING_JSON,
    "rentEstimate": 1200,  # per unit
    "units": 3,
}


class TestParseListingUnit:
    """Unit tests for _parse_listing."""

    def test_basic_listing_no_rent_uses_sqft_fallback(self) -> None:
        now = datetime.now(timezone.utc)
        listing = _parse_listing(SAMPLE_LISTING_JSON, now)
        assert listing is not None
        assert listing.address == "123 Main St, Vallejo, CA 94590"
        assert listing.list_price == 550000.0
        assert listing.sqft == 2400.0
        assert listing.year_built == 1965
        assert listing.rent_source == RentSource.estimated_from_sqft
        # 2400 sqft * $1.85/sqft = $4440
        assert listing.monthly_rent_total == pytest.approx(2400 * 1.85)

    def test_listing_with_disclosed_rent(self) -> None:
        now = datetime.now(timezone.utc)
        listing = _parse_listing(SAMPLE_LISTING_WITH_RENT, now)
        assert listing is not None
        assert listing.rent_source == RentSource.listing_disclosed
        assert listing.monthly_rent_total == 4800.0

    def test_listing_with_rent_estimate(self) -> None:
        now = datetime.now(timezone.utc)
        listing = _parse_listing(SAMPLE_LISTING_WITH_ESTIMATE, now)
        assert listing is not None
        assert listing.rent_source == RentSource.rentcast_estimate
        # 3 units * $1200/unit = $3600
        assert listing.monthly_rent_total == pytest.approx(3600.0)
        assert listing.num_units == 3

    def test_listing_missing_address_returns_none(self) -> None:
        now = datetime.now(timezone.utc)
        raw = {"price": 500000}
        assert _parse_listing(raw, now) is None

    def test_listing_missing_price_returns_none(self) -> None:
        now = datetime.now(timezone.utc)
        raw = {"formattedAddress": "123 Main St", "price": None}
        assert _parse_listing(raw, now) is None

    def test_listing_no_rent_no_sqft_uses_unknown(self) -> None:
        now = datetime.now(timezone.utc)
        raw = {
            "formattedAddress": "456 Oak Ave, Vallejo, CA 94590",
            "price": 400000,
            "bedrooms": 2,
        }
        listing = _parse_listing(raw, now)
        assert listing is not None
        assert listing.rent_source == RentSource.unknown
        assert listing.monthly_rent_total == 0.0


class TestFetchSaleListings:
    """Integration-style tests for fetch_sale_listings using mocked HTTP."""

    @respx.mock
    def test_successful_fetch(self) -> None:
        mock_response = [SAMPLE_LISTING_WITH_RENT]
        respx.get("https://api.rentcast.io/v1/listings/sale").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        listings = fetch_sale_listings(api_key="test-key")
        # Unit count defaults to bedrooms=4, which is within 2-4 range
        assert len(listings) == 1
        assert listings[0].address == "123 Main St, Vallejo, CA 94590"

    @respx.mock
    def test_401_raises_error(self) -> None:
        respx.get("https://api.rentcast.io/v1/listings/sale").mock(
            return_value=httpx.Response(401)
        )
        with pytest.raises(RentCastError, match="401"):
            fetch_sale_listings(api_key="bad-key")

    @respx.mock
    def test_429_raises_error(self) -> None:
        respx.get("https://api.rentcast.io/v1/listings/sale").mock(
            return_value=httpx.Response(429)
        )
        with pytest.raises(RentCastError, match="429"):
            fetch_sale_listings(api_key="test-key")

    @respx.mock
    def test_empty_response(self) -> None:
        respx.get("https://api.rentcast.io/v1/listings/sale").mock(
            return_value=httpx.Response(200, json=[])
        )
        listings = fetch_sale_listings(api_key="test-key")
        assert listings == []

    @respx.mock
    def test_unit_filter_excludes_single_family(self) -> None:
        """Listings with 1 unit (below MIN_UNITS) should be filtered out."""
        raw = {**SAMPLE_LISTING_JSON, "bedrooms": 1, "units": 1}
        respx.get("https://api.rentcast.io/v1/listings/sale").mock(
            return_value=httpx.Response(200, json=[raw])
        )
        listings = fetch_sale_listings(api_key="test-key")
        assert len(listings) == 0

    @respx.mock
    def test_unit_filter_excludes_large_complex(self) -> None:
        """Listings with >4 units should be filtered out."""
        raw = {**SAMPLE_LISTING_JSON, "units": 8}
        respx.get("https://api.rentcast.io/v1/listings/sale").mock(
            return_value=httpx.Response(200, json=[raw])
        )
        listings = fetch_sale_listings(api_key="test-key")
        assert len(listings) == 0
