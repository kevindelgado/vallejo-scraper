"""CSV output writer for underwritten listings."""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

from vallejo_scraper import config
from vallejo_scraper.models import Listing, MRPResult, Verdict

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "scraped_at",
    "address",
    "list_price",
    "num_units",
    "sqft",
    "year_built",
    "monthly_rent_total",
    "rent_source",
    "gross_annual_rent",
    "egi",
    "total_opex",
    "noi_pretax",
    "mrp",
    "gap_pct",
    "verdict",
    "days_on_market",
    "listing_url",
    "mls_number",
]


def write_csv(
    rows: list[tuple[Listing, MRPResult, Verdict]],
    output_dir: Path | None = None,
) -> Path:
    """Write underwritten listing results to a timestamped CSV file.

    Returns the path to the written CSV.
    """
    if output_dir is None:
        output_dir = config.OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"vallejo_listings_{timestamp}.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for listing, mrp_result, verdict in rows:
            writer.writerow(
                {
                    "scraped_at": listing.scraped_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "address": listing.address,
                    "list_price": f"{listing.list_price:.0f}",
                    "num_units": listing.num_units,
                    "sqft": f"{listing.sqft:.0f}" if listing.sqft else "",
                    "year_built": listing.year_built or "",
                    "monthly_rent_total": f"{listing.monthly_rent_total:.0f}" if listing.monthly_rent_total else "",
                    "rent_source": listing.rent_source.value,
                    "gross_annual_rent": f"{mrp_result.gross_annual_rent:.0f}",
                    "egi": f"{mrp_result.egi:.0f}",
                    "total_opex": f"{mrp_result.total_opex:.0f}",
                    "noi_pretax": f"{mrp_result.noi_pretax:.0f}",
                    "mrp": f"{mrp_result.mrp:.0f}",
                    "gap_pct": f"{verdict.gap_pct:.4f}",
                    "verdict": verdict.label.value,
                    "days_on_market": listing.days_on_market if listing.days_on_market is not None else "",
                    "listing_url": listing.listing_url or "",
                    "mls_number": listing.mls_number or "",
                }
            )

    logger.info("Wrote %d rows to %s", len(rows), csv_path)
    return csv_path
