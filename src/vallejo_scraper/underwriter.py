"""MRP underwriting calculation and verdict classification."""

from __future__ import annotations

from vallejo_scraper import config
from vallejo_scraper.models import MRPResult, RentSource, Verdict, VerdictLabel


def calculate_mrp(
    monthly_rent_total: float,
    num_units: int,
    *,
    vacancy_rate: float = config.VACANCY_RATE,
    management_rate: float = config.MANAGEMENT_RATE,
    maintenance_rate: float = config.MAINTENANCE_RATE,
    capex_reserve_monthly_per_unit: float = config.CAPEX_RESERVE_MONTHLY_PER_UNIT,
    insurance_annual: float = config.INSURANCE_ANNUAL,
    misc_annual: float = config.MISC_ANNUAL,
    cap_rate: float = config.CAP_RATE,
) -> MRPResult:
    """Pure deterministic MRP calculation following the exact formula."""
    gross_annual_rent = monthly_rent_total * 12
    egi = gross_annual_rent * (1 - vacancy_rate)
    management = egi * management_rate
    maintenance = egi * maintenance_rate
    capex_reserves = capex_reserve_monthly_per_unit * num_units * 12
    total_opex = management + maintenance + capex_reserves + insurance_annual + misc_annual
    noi_pretax = egi - total_opex
    mrp = noi_pretax / cap_rate

    return MRPResult(
        gross_annual_rent=gross_annual_rent,
        egi=egi,
        management=management,
        maintenance=maintenance,
        capex_reserves=capex_reserves,
        total_opex=total_opex,
        noi_pretax=noi_pretax,
        mrp=mrp,
    )


def classify(
    ask_price: float,
    mrp: float,
    rent_source: RentSource = RentSource.listing_disclosed,
) -> Verdict:
    """Classify a deal based on the gap between ask price and MRP.

    Unverified rent sources are capped at conditional_watchlist_unverified
    (i.e. tour_candidate is not possible for unverified rents).
    """
    gap_pct = (ask_price - mrp) / mrp
    is_verified = rent_source == RentSource.listing_disclosed

    if gap_pct <= config.TOUR_CANDIDATE_MAX_GAP:
        if is_verified:
            label = VerdictLabel.tour_candidate
        else:
            # Unverified cap: best possible is conditional_watchlist_unverified
            label = VerdictLabel.conditional_watchlist_unverified
    elif gap_pct <= config.CONDITIONAL_WATCHLIST_MAX_GAP:
        if is_verified:
            label = VerdictLabel.conditional_watchlist
        else:
            label = VerdictLabel.conditional_watchlist_unverified
    elif gap_pct <= config.PASSIVE_WATCHLIST_MAX_GAP:
        if is_verified:
            label = VerdictLabel.passive_watchlist
        else:
            label = VerdictLabel.passive_watchlist_unverified
    else:
        if is_verified:
            label = VerdictLabel.graveyard
        else:
            label = VerdictLabel.graveyard_unverified

    return Verdict(gap_pct=gap_pct, label=label)
