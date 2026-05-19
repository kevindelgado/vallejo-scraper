---
name: testing-vallejo-underwriter
description: Test the Vallejo multifamily underwriter pipeline end-to-end. Use when verifying MRP formula, verdict classification, RentCast integration, or CSV output changes.
---

## Devin Secrets Needed

- `RENTCAST_API_KEY` — RentCast API key for live pipeline testing (org-scoped)

## Environment Setup

```bash
cd /home/ubuntu/repos/vallejo_scraper
uv sync --all-extras
```

## Testing Procedure

### 1. Unit Tests (offline, no API key needed)

```bash
uv run pytest -v
```

Expect 40+ tests covering:
- 3 reference deals (302 Carolina, 706 Porter, 2008 Marin)
- Verdict edge thresholds at +5%, +12%, +20% boundaries
- Unverified rent cap behavior
- Mocked RentCast provider (no network access)

### 2. MRP Math Spot-Check

Verify intermediate values match the exact formula by running `calculate_mrp()` directly:

```bash
uv run python -c "
from vallejo_scraper.underwriter import calculate_mrp
r = calculate_mrp(6000.0, 3)  # 302 Carolina reference
print(f'gross={r.gross_annual_rent}, egi={r.egi}, opex={r.total_opex}, noi={r.noi_pretax}, mrp={r.mrp:.2f}')
"
```

Expected for 302 Carolina ($6,000/mo, 3 units):
- gross=72000, egi=68400, opex=19686, noi=48714, mrp≈590473
- MRP should be within 5% of ~$608K reference

### 3. Verdict Edge Cases

Test boundary values with `classify()` directly. Key assertions:
- `classify(105000, 100000, listing_disclosed)` → `tour_candidate` (at +5% boundary)
- `classify(105001, 100000, listing_disclosed)` → `conditional_watchlist` (just over)
- `classify(105000, 100000, rentcast_estimate)` → `conditional_watchlist_unverified` (unverified cap)

### 4. Live Pipeline (requires RENTCAST_API_KEY)

```bash
RENTCAST_API_KEY=${RENTCAST_API_KEY} uv run python -m vallejo_scraper.run
```

Verify:
- Exit code 0
- Log shows "Fetched N listings" (N > 0)
- Per-listing underwriting output in logs
- CSV written to `output/vallejo_listings_<timestamp>.csv`

### 5. CSV Validation

Use Python's `csv.DictReader` to validate (not awk — addresses contain commas):
- Header has exactly 18 columns in spec order
- All `list_price` values between $400K–$1.1M
- All `num_units` between 2–4
- All `verdict` and `rent_source` values are valid enums
- `gap_pct` is consistent with `(list_price - mrp) / mrp`

### 6. Error Handling

```bash
unset RENTCAST_API_KEY
uv run python -m vallejo_scraper.run
```

Expect: exit code 1, stderr contains "RENTCAST_API_KEY is not set", no traceback.

### 7. Lint

```bash
uv run ruff check .
```

## Known Behaviors

- RentCast sale listings for Vallejo multi-family typically don't include disclosed rent rolls. Most listings will use `estimated_from_sqft` ($1.85/sqft) rent source.
- Unverified rent sources produce conservative MRP values, leading to large gaps and `graveyard_unverified` verdicts. This is expected.
- Unit count falls back to `bedrooms` when RentCast doesn't provide a `units` field.
- CSV addresses contain commas — always use Python's csv module for parsing, not shell tools like awk.
- The logging module uses %-style formatting — do not use comma thousands separators (`%,.0f`) in log format strings.
