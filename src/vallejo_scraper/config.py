"""Centralized configuration for the Vallejo multifamily underwriter."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from project root (no-op if the file doesn't exist)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Target listing filters
# ---------------------------------------------------------------------------
TARGET_CITY: str = "Vallejo"
TARGET_STATE: str = "CA"
MIN_PRICE: int = 400_000
MAX_PRICE: int = 1_100_000
MIN_UNITS: int = 2
MAX_UNITS: int = 4
ACTIVE_ONLY: bool = True

# ---------------------------------------------------------------------------
# Underwriting assumptions
# ---------------------------------------------------------------------------
VACANCY_RATE: float = 0.05
MANAGEMENT_RATE: float = 0.08
MAINTENANCE_RATE: float = 0.085
CAPEX_RESERVE_MONTHLY_PER_UNIT: float = 150.0
INSURANCE_ANNUAL: float = 2400.0
MISC_ANNUAL: float = 600.0
CAP_RATE: float = 0.0825

# ---------------------------------------------------------------------------
# Verdict thresholds (gap_pct = (ask - mrp) / mrp)
# ---------------------------------------------------------------------------
TOUR_CANDIDATE_MAX_GAP: float = 0.05
CONDITIONAL_WATCHLIST_MAX_GAP: float = 0.12
PASSIVE_WATCHLIST_MAX_GAP: float = 0.20

# ---------------------------------------------------------------------------
# Rent estimate fallback
# ---------------------------------------------------------------------------
RENT_PER_SQFT_MONTHLY: float = 1.85

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
OUTPUT_DIR: Path = _PROJECT_ROOT / "output"

# ---------------------------------------------------------------------------
# RentCast
# ---------------------------------------------------------------------------
RENTCAST_BASE_URL: str = "https://api.rentcast.io/v1"


def get_rentcast_api_key() -> str:
    """Return the RentCast API key or exit with a helpful message."""
    key = os.environ.get("RENTCAST_API_KEY", "")
    if not key:
        print(
            "ERROR: RENTCAST_API_KEY is not set.\n"
            "Set it as an environment variable or add it to a .env file in the project root.\n"
            "See README.md for setup instructions.",
            file=sys.stderr,
        )
        sys.exit(1)
    return key
