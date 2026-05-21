"""RentCast API provider for fetching sale listings and rent estimates."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from vallejo_scraper import config
from vallejo_scraper.models import Listing, RentSource, TargetFilters

logger = logging.getLogger(__name__)


class RentCastError(Exception):
    """Raised for RentCast API errors."""


def _build_headers(api_key: str) -> dict[str, str]:
    return {"X-Api-Key": api_key, "Accept": "application/json"}


def _parse_listing(raw: dict[str, Any], now: datetime) -> Listing | None:
    """Convert a raw RentCast sale listing JSON record into our Listing model.

    Returns None if the record cannot be meaningfully parsed (e.g. missing
    address or price).
    """
    address = raw.get("formattedAddress") or raw.get("addressLine1")
    if not address:
        logger.warning("Skipping listing with no address: %s", raw.get("id"))
        return None

    list_price = raw.get("price")
    if list_price is None:
        logger.warning("Skipping listing with no price: %s", address)
        return None

    # Unit count: RentCast sometimes provides a "units" field for
    # multi-family, but often does not.  We track whether the value is
    # confirmed by RentCast so the caller can decide whether to filter.
    units_confirmed = False
    num_units = raw.get("units")
    if num_units is None:
        num_units = raw.get("unitCount") or raw.get("numberOfUnits")
    if num_units is not None:
        units_confirmed = True
    else:
        # Fallback: use bedrooms as a rough proxy for underwriting only
        num_units = raw.get("bedrooms") or 2
    num_units = int(num_units)

    bedrooms = raw.get("bedrooms")
    if bedrooms is not None:
        bedrooms = int(bedrooms)

    sqft = raw.get("squareFootage")
    if sqft is not None:
        sqft = float(sqft)

    year_built = raw.get("yearBuilt")
    days_on_market = raw.get("daysOnMarket")

    # Listing URL / MLS
    listing_url = raw.get("listingUrl") or raw.get("url")
    mls_number = raw.get("mlsNumber") or raw.get("listingId")

    # ---- Rent / income data ----
    monthly_rent_total: float | None = None
    rent_source = RentSource.unknown

    # 1) Check for disclosed rent roll or income fields
    rent_roll = raw.get("rentRoll") or raw.get("monthlyRent") or raw.get("income")
    if rent_roll is not None and float(rent_roll) > 0:
        monthly_rent_total = float(rent_roll)
        rent_source = RentSource.listing_disclosed
    else:
        # 2) Check for RentCast estimated rent (per-unit)
        estimated_rent = raw.get("rentEstimate") or raw.get("estimatedRent")
        if estimated_rent is not None and float(estimated_rent) > 0:
            monthly_rent_total = float(estimated_rent) * num_units
            rent_source = RentSource.rentcast_estimate

    # 3) Fallback: estimate from sqft
    if monthly_rent_total is None and sqft is not None and sqft > 0:
        monthly_rent_total = sqft * config.RENT_PER_SQFT_MONTHLY
        rent_source = RentSource.estimated_from_sqft

    # 4) No data at all → unknown
    if monthly_rent_total is None:
        monthly_rent_total = 0.0
        rent_source = RentSource.unknown

    return Listing(
        address=address,
        list_price=float(list_price),
        num_units=num_units,
        units_confirmed=units_confirmed,
        bedrooms=bedrooms,
        sqft=sqft,
        year_built=year_built,
        days_on_market=days_on_market,
        listing_url=listing_url,
        mls_number=mls_number,
        monthly_rent_total=monthly_rent_total,
        rent_source=rent_source,
        scraped_at=now,
    )


def fetch_sale_listings(
    api_key: str | None = None,
    filters: TargetFilters | None = None,
) -> list[Listing]:
    """Fetch active multi-family sale listings from RentCast.

    Uses *filters* for city/state/price/unit criteria.  Falls back to
    ``config`` module-level defaults when *filters* is ``None``.
    """
    if api_key is None:
        api_key = config.get_rentcast_api_key()
    if filters is None:
        filters = TargetFilters()

    headers = _build_headers(api_key)
    params: dict[str, Any] = {
        "city": filters.city,
        "state": filters.state,
        "propertyType": "Multi-Family",
        "status": "Active",
        "price": f"{filters.min_price}-{filters.max_price}",
        "limit": 500,
        "offset": 0,
    }

    url = f"{config.RENTCAST_BASE_URL}/listings/sale"
    now = datetime.now(timezone.utc)
    all_listings: list[Listing] = []

    try:
        with httpx.Client(timeout=30.0) as client:
            while True:
                logger.info("Fetching RentCast listings offset=%d", params["offset"])
                resp = client.get(url, headers=headers, params=params)

                if resp.status_code == 401:
                    raise RentCastError("Invalid or missing RentCast API key (401 Unauthorized).")
                if resp.status_code == 403:
                    raise RentCastError("RentCast API access forbidden (403). Check your API key permissions.")
                if resp.status_code == 429:
                    raise RentCastError("RentCast API rate limit exceeded (429). Try again later.")
                resp.raise_for_status()

                try:
                    data = resp.json()
                except Exception as exc:
                    raise RentCastError(f"Malformed JSON response from RentCast: {exc}") from exc

                if not isinstance(data, list):
                    logger.warning("Unexpected RentCast response type: %s", type(data))
                    break

                if not data:
                    break

                for raw in data:
                    listing = _parse_listing(raw, now)
                    if listing is None:
                        continue
                    # Only filter on unit count when RentCast confirmed it;
                    # otherwise let the listing through (bedrooms != units).
                    if listing.units_confirmed and not (filters.min_units <= listing.num_units <= filters.max_units):
                        continue
                    all_listings.append(listing)

                # Paginate
                if len(data) < params["limit"]:
                    break
                params["offset"] += len(data)

    except httpx.TimeoutException as exc:
        raise RentCastError(f"RentCast API request timed out: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise RentCastError(f"RentCast API HTTP error: {exc}") from exc

    logger.info("Fetched %d Vallejo multi-family listings from RentCast.", len(all_listings))
    return all_listings


def fetch_rent_estimate(address: str, api_key: str | None = None) -> float | None:
    """Fetch a per-unit rent estimate from RentCast's AVM endpoint.

    Returns the monthly rent estimate for one unit, or None if unavailable.
    """
    if api_key is None:
        api_key = config.get_rentcast_api_key()

    headers = _build_headers(api_key)
    params = {
        "address": address,
        "propertyType": "Multi-Family",
    }
    url = f"{config.RENTCAST_BASE_URL}/avm/rent/long-term"

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code in (401, 403, 429):
                logger.warning("RentCast rent estimate API returned %d for %s", resp.status_code, address)
                return None
            resp.raise_for_status()
            data = resp.json()
            return data.get("rent")
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("Failed to fetch rent estimate for %s: %s", address, exc)
        return None
