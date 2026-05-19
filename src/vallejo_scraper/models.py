"""Pydantic v2 models for listings, MRP results, and verdicts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Rent source
# ---------------------------------------------------------------------------
class RentSource(str, Enum):
    listing_disclosed = "listing_disclosed"
    rentcast_estimate = "rentcast_estimate"
    estimated_from_sqft = "estimated_from_sqft"
    unknown = "unknown"


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
class VerdictLabel(str, Enum):
    tour_candidate = "tour_candidate"
    conditional_watchlist = "conditional_watchlist"
    passive_watchlist = "passive_watchlist"
    graveyard = "graveyard"
    # Unverified variants
    conditional_watchlist_unverified = "conditional_watchlist_unverified"
    passive_watchlist_unverified = "passive_watchlist_unverified"
    graveyard_unverified = "graveyard_unverified"


# ---------------------------------------------------------------------------
# Listing (input)
# ---------------------------------------------------------------------------
class Listing(BaseModel):
    address: str
    list_price: float
    num_units: int
    units_confirmed: bool = False
    sqft: Optional[float] = None
    year_built: Optional[int] = None
    days_on_market: Optional[int] = None
    listing_url: Optional[str] = None
    mls_number: Optional[str] = None
    monthly_rent_total: Optional[float] = None
    rent_source: RentSource = RentSource.unknown
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# MRP result (output of underwriting calc)
# ---------------------------------------------------------------------------
class MRPResult(BaseModel):
    gross_annual_rent: float
    egi: float
    management: float
    maintenance: float
    capex_reserves: float
    total_opex: float
    noi_pretax: float
    mrp: float


# ---------------------------------------------------------------------------
# Verdict result
# ---------------------------------------------------------------------------
class Verdict(BaseModel):
    gap_pct: float
    label: VerdictLabel
