"""Tests for the FastAPI web routes — filters, defaults, and validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from vallejo_scraper import config
from vallejo_scraper.web import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


class TestGetDefaults:
    """GET /api/defaults should return config defaults."""

    def test_returns_defaults(self, client: TestClient) -> None:
        resp = client.get("/api/defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_price"] == config.MIN_PRICE
        assert data["max_price"] == config.MAX_PRICE
        assert data["min_units"] == config.MIN_UNITS
        assert data["max_units"] == config.MAX_UNITS


class TestIndexPage:
    """GET / should serve the HTML page."""

    def test_returns_html(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Target Filters" in resp.text


class TestRunPipelineFilters:
    """POST /api/run with filter query parameters."""

    def _mock_listings(self):
        """Return a minimal listing that will survive underwriting."""
        from datetime import datetime, timezone

        from vallejo_scraper.models import Listing, RentSource

        return [
            Listing(
                address="100 Test St, Vallejo, CA 94590",
                list_price=500_000,
                num_units=2,
                units_confirmed=True,
                monthly_rent_total=3000.0,
                rent_source=RentSource.listing_disclosed,
                scraped_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
        ]

    @patch.dict("os.environ", {"RENTCAST_API_KEY": "test-key"})
    @patch("vallejo_scraper.web.fetch_sale_listings")
    def test_no_filters_uses_defaults(self, mock_fetch, client: TestClient) -> None:
        mock_fetch.return_value = self._mock_listings()
        resp = client.post("/api/run")
        assert resp.status_code == 200
        body = resp.json()
        af = body["active_filters"]
        assert af["min_price"] == config.MIN_PRICE
        assert af["max_price"] == config.MAX_PRICE
        assert af["min_units"] == config.MIN_UNITS
        assert af["max_units"] == config.MAX_UNITS
        assert len(body["results"]) == 1

    @patch.dict("os.environ", {"RENTCAST_API_KEY": "test-key"})
    @patch("vallejo_scraper.web.fetch_sale_listings")
    def test_custom_filters_passed_through(self, mock_fetch, client: TestClient) -> None:
        mock_fetch.return_value = self._mock_listings()
        resp = client.post("/api/run?min_price=500000&max_price=900000&min_units=3&max_units=6")
        assert resp.status_code == 200
        af = resp.json()["active_filters"]
        assert af["min_price"] == 500_000
        assert af["max_price"] == 900_000
        assert af["min_units"] == 3
        assert af["max_units"] == 6

        # Verify the filters were passed to fetch_sale_listings
        call_kwargs = mock_fetch.call_args
        filters_arg = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert filters_arg.min_price == 500_000
        assert filters_arg.max_price == 900_000

    @patch.dict("os.environ", {"RENTCAST_API_KEY": "test-key"})
    def test_invalid_filters_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/run?min_price=900000&max_price=400000")
        assert resp.status_code == 422

    @patch.dict("os.environ", {"RENTCAST_API_KEY": "test-key"})
    def test_negative_price_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/run?min_price=-100")
        assert resp.status_code == 422

    @patch.dict("os.environ", {"RENTCAST_API_KEY": "test-key"})
    def test_invalid_units_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/run?min_units=5&max_units=3")
        assert resp.status_code == 422

    def test_missing_api_key_returns_500(self, client: TestClient) -> None:
        with patch.dict("os.environ", {}, clear=True):
            resp = client.post("/api/run")
            assert resp.status_code == 500

    @patch.dict("os.environ", {"RENTCAST_API_KEY": "test-key"})
    @patch("vallejo_scraper.web.fetch_sale_listings")
    def test_partial_filters_fill_defaults(self, mock_fetch, client: TestClient) -> None:
        mock_fetch.return_value = self._mock_listings()
        resp = client.post("/api/run?min_price=500000")
        assert resp.status_code == 200
        af = resp.json()["active_filters"]
        assert af["min_price"] == 500_000
        assert af["max_price"] == config.MAX_PRICE  # default
        assert af["min_units"] == config.MIN_UNITS  # default
