"""Pipeline entry point: fetch listings, underwrite, classify, write CSV.

Usage: python -m vallejo_scraper.run
"""

from __future__ import annotations

import logging
import sys

from vallejo_scraper.models import Listing, MRPResult, Verdict
from vallejo_scraper.output import write_csv
from vallejo_scraper.rentcast import RentCastError, fetch_sale_listings
from vallejo_scraper.underwriter import calculate_mrp, classify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def underwrite_listing(listing: Listing) -> tuple[MRPResult, Verdict]:
    """Run MRP underwriting and verdict classification for a single listing."""
    rent = listing.monthly_rent_total or 0.0
    mrp_result = calculate_mrp(monthly_rent_total=rent, num_units=listing.num_units)
    verdict = classify(
        ask_price=listing.list_price,
        mrp=mrp_result.mrp,
        rent_source=listing.rent_source,
    )
    return mrp_result, verdict


def main() -> None:
    logger.info("Starting Vallejo multifamily underwriter pipeline...")

    # Fetch listings from RentCast
    try:
        listings = fetch_sale_listings()
    except RentCastError as exc:
        logger.error("RentCast API error: %s", exc)
        sys.exit(1)

    if not listings:
        logger.warning("No matching listings found. Writing empty CSV.")
        csv_path = write_csv([])
        logger.info("Empty CSV written to %s", csv_path)
        return

    logger.info("Fetched %d listings. Underwriting...", len(listings))

    # Underwrite each listing
    rows: list[tuple[Listing, MRPResult, Verdict]] = []
    for listing in listings:
        mrp_result, verdict = underwrite_listing(listing)
        rows.append((listing, mrp_result, verdict))
        logger.info(
            "  %s | ask=$%.0f | mrp=$%.0f | gap=%+.1f%% | %s | rent_src=%s",
            listing.address,
            listing.list_price,
            mrp_result.mrp,
            verdict.gap_pct * 100,
            verdict.label.value,
            listing.rent_source.value,
        )

    # Write CSV
    csv_path = write_csv(rows)
    logger.info("Pipeline complete. CSV written to %s", csv_path)

    # Summary
    verdicts = [v.label.value for _, _, v in rows]
    for label in sorted(set(verdicts)):
        count = verdicts.count(label)
        logger.info("  %s: %d", label, count)


if __name__ == "__main__":
    main()
