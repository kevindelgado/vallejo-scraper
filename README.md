# Vallejo Multifamily Underwriter

Pulls active Vallejo 2–4 unit multifamily sale listings from RentCast, underwrites each listing with the MRP (Maximum Rational Price) formula, classifies verdicts, and writes a timestamped CSV.

## Quick Start

```bash
# Install dependencies (requires uv: https://docs.astral.sh/uv/)
uv sync --all-extras

# Set your RentCast API key
cp .env.example .env
# Edit .env and add your real key

# Run the pipeline
uv run python -m vallejo_scraper.run

# Run tests
uv run pytest -v
```

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync --all-extras
```

## Setting `RENTCAST_API_KEY`

### Local development

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and replace `your_key_here` with your actual RentCast API key.
3. The `.env` file is in `.gitignore` and will not be committed.

### Devin Cloud execution

Add `RENTCAST_API_KEY` via Devin's Secrets Manager. It will be injected as an environment variable automatically.

### Direct environment variable

```bash
export RENTCAST_API_KEY=your_key_here
uv run python -m vallejo_scraper.run
```

If the key is missing at runtime, the program exits with a clear error message.

## Running the Pipeline

```bash
uv run python -m vallejo_scraper.run
```

This will:
1. Fetch active multi-family sale listings from RentCast for Vallejo, CA
2. Filter to 2–4 unit properties in the $400K–$1.1M price band
3. Underwrite each listing using the MRP formula
4. Classify each listing into a verdict category
5. Write a timestamped CSV to `output/`

## Running Tests

```bash
uv run pytest -v
```

All tests use mocked data and do not require network access or consume API quota.

## CSV Output

Output files are written to `output/` with columns in this exact order:

| Column | Description |
|--------|-------------|
| `scraped_at` | Timestamp of the data pull |
| `address` | Property address |
| `list_price` | Asking price |
| `num_units` | Number of units (2–4) |
| `sqft` | Square footage |
| `year_built` | Year built |
| `monthly_rent_total` | Total monthly rent (all units) |
| `rent_source` | How rent was determined |
| `gross_annual_rent` | Monthly rent × 12 |
| `egi` | Effective Gross Income (after vacancy) |
| `total_opex` | Total operating expenses |
| `noi_pretax` | Net Operating Income (pre-tax) |
| `mrp` | Maximum Rational Price |
| `gap_pct` | (ask − MRP) / MRP |
| `verdict` | Classification label |
| `days_on_market` | Days listed |
| `listing_url` | Listing URL |
| `mls_number` | MLS number |

## MRP Formula

```
gross_annual_rent = monthly_rent_total × 12
egi = gross_annual_rent × (1 − vacancy_rate)
management = egi × management_rate
maintenance = egi × maintenance_rate
capex_reserves = capex_reserve_monthly_per_unit × num_units × 12
total_opex = management + maintenance + capex_reserves + insurance_annual + misc_annual
noi_pretax = egi − total_opex
mrp = noi_pretax / cap_rate
```

## Default Assumptions

| Parameter | Value |
|-----------|-------|
| Vacancy rate | 5% |
| Management rate | 8% |
| Maintenance rate | 8.5% |
| CapEx reserve | $150/unit/month |
| Insurance (annual) | $2,400 |
| Misc (annual) | $600 |
| Cap rate | 8.25% |

These can be adjusted in `src/vallejo_scraper/config.py`.

## Verdict Classification

| Gap % | Verified Verdict | Unverified Verdict |
|-------|------------------|--------------------|
| ≤ 5% | `tour_candidate` | `conditional_watchlist_unverified` |
| ≤ 12% | `conditional_watchlist` | `conditional_watchlist_unverified` |
| ≤ 20% | `passive_watchlist` | `passive_watchlist_unverified` |
| > 20% | `graveyard` | `graveyard_unverified` |

Unverified rent sources (`rentcast_estimate`, `estimated_from_sqft`, `unknown`) are capped at `conditional_watchlist_unverified` — they cannot achieve `tour_candidate`.

## Rent Source Values

| Value | Description |
|-------|-------------|
| `listing_disclosed` | Actual rent roll from the listing |
| `rentcast_estimate` | RentCast's estimated rent (unverified) |
| `estimated_from_sqft` | Estimated at $1.85/sqft/month (unverified) |
| `unknown` | No rent or sqft data available (unverified) |

## Web UI Target Filters

The web application includes editable target filters that let you adjust the search criteria for each run:

- **Min Price / Max Price** — price band for listings (default: $400K–$1.1M)
- **Min Units / Max Units** — unit count range (default: 2–4)

City/state is fixed to Vallejo, CA.

Filter changes are **per-request only** — they are not persisted across page reloads or app restarts. When you click **Run Pipeline** without changing filters, the config defaults are used.

The results page displays an "Active filters" banner showing the exact filters that were used for the current result set — this always reflects what was actually sent to RentCast, not what is currently in the form fields.

The CLI (`python -m vallejo_scraper.run`) continues to use the `config.py` defaults and is not affected by web UI filter changes.

## Cron Scheduling

To run daily at 8 AM Pacific:

```bash
0 15 * * * cd /path/to/vallejo_scraper && uv run python -m vallejo_scraper.run >> /var/log/vallejo_scraper.log 2>&1
```

## RentCast Field Limitations

- RentCast sale listings may not include actual rent rolls; in that case, rent is marked as `rentcast_estimate` or estimated from sqft.
- Unit count is inferred from available fields (units, unitCount, or bedrooms as fallback).
- Not all listings include MLS numbers or listing URLs.

## Project Structure

```
src/vallejo_scraper/
├── __init__.py
├── __main__.py      # python -m vallejo_scraper entry point
├── config.py        # All configuration and assumptions
├── models.py        # Pydantic v2 models (Listing, MRPResult, Verdict, TargetFilters)
├── underwriter.py   # MRP calculation and verdict classification
├── rentcast.py      # RentCast API provider
├── output.py        # CSV writer
├── run.py           # Pipeline orchestrator
├── web.py           # FastAPI web application
└── static/
    └── index.html   # Browser UI with filter form
tests/
├── test_underwriter.py  # Reference deal tests
├── test_classify.py     # Verdict threshold tests
├── test_rentcast.py     # Mocked provider tests
├── test_filters.py      # TargetFilters validation tests
└── test_web.py          # FastAPI route tests
```
