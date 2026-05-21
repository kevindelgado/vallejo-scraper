"""FastAPI web application for the Vallejo underwriter pipeline."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from vallejo_scraper.models import Listing, MRPResult, TargetFilters, Verdict
from vallejo_scraper.rentcast import RentCastError, fetch_sale_listings
from vallejo_scraper.underwriter import calculate_mrp, classify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Vallejo Underwriter")

STATIC_DIR = Path(__file__).parent / "static"


def _underwrite(listing: Listing) -> tuple[MRPResult, Verdict]:
    rent = listing.monthly_rent_total or 0.0
    mrp_result = calculate_mrp(monthly_rent_total=rent, num_units=listing.num_units)
    verdict = classify(
        ask_price=listing.list_price,
        mrp=mrp_result.mrp,
        rent_source=listing.rent_source,
    )
    return mrp_result, verdict


def _resolve_filters(
    min_price: Optional[int],
    max_price: Optional[int],
    min_units: Optional[int],
    max_units: Optional[int],
) -> TargetFilters:
    """Build a ``TargetFilters`` from optional query parameters.

    Any parameter that is ``None`` falls back to the config default.
    Raises ``ValueError`` on invalid combinations.
    """
    kwargs: dict[str, int] = {}
    if min_price is not None:
        kwargs["min_price"] = min_price
    if max_price is not None:
        kwargs["max_price"] = max_price
    if min_units is not None:
        kwargs["min_units"] = min_units
    if max_units is not None:
        kwargs["max_units"] = max_units
    return TargetFilters(**kwargs)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/defaults")
async def get_defaults() -> dict:
    """Return the default target filter values from config."""
    defaults = TargetFilters()
    return {
        "min_price": defaults.min_price,
        "max_price": defaults.max_price,
        "min_units": defaults.min_units,
        "max_units": defaults.max_units,
    }


@app.post("/api/run")
async def run_pipeline(
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    min_units: Optional[int] = Query(None),
    max_units: Optional[int] = Query(None),
) -> dict:
    api_key = os.environ.get("RENTCAST_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="RENTCAST_API_KEY not configured on server.")

    try:
        filters = _resolve_filters(min_price, max_price, min_units, max_units)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        listings = fetch_sale_listings(api_key=api_key, filters=filters)
    except RentCastError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    results = []
    for listing in listings:
        mrp_result, verdict = _underwrite(listing)
        results.append({
            "scraped_at": listing.scraped_at.strftime("%Y-%m-%d %H:%M:%S"),
            "address": listing.address,
            "list_price": listing.list_price,
            "num_units": listing.num_units if listing.units_confirmed else None,
            "bedrooms": listing.bedrooms,
            "sqft": listing.sqft,
            "year_built": listing.year_built,
            "monthly_rent_total": round(listing.monthly_rent_total, 0) if listing.monthly_rent_total else None,
            "rent_source": listing.rent_source.value,
            "gross_annual_rent": round(mrp_result.gross_annual_rent, 0),
            "egi": round(mrp_result.egi, 0),
            "total_opex": round(mrp_result.total_opex, 0),
            "noi_pretax": round(mrp_result.noi_pretax, 0),
            "mrp": round(mrp_result.mrp, 0),
            "gap_pct": round(verdict.gap_pct, 4),
            "verdict": verdict.label.value,
            "days_on_market": listing.days_on_market,
            "listing_url": listing.listing_url,
            "mls_number": listing.mls_number,
        })

    active_filters = {
        "min_price": filters.min_price,
        "max_price": filters.max_price,
        "min_units": filters.min_units,
        "max_units": filters.max_units,
    }

    logger.info("Pipeline returned %d results (filters=%s)", len(results), active_filters)
    return {"results": results, "active_filters": active_filters}
