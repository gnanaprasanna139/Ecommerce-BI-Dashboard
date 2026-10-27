# Project 15 - E-Commerce Business Intelligence Dashboard

A management view of store performance built on MySQL, pandas, NumPy and Matplotlib. It covers headline KPIs (Gross Sales, Net Sales, Order Count, AOV and supporting rates), revenue by month, category and region, and growth against the previous period and the same period last year.

All figures are aggregated business performance. There is no customer-level segmentation. Order-level drill-downs (Project 8) and customer behaviour (Project 19) are out of scope.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env      # then set DB_PASSWORD (and DB_NAME if needed)
```

Requires MySQL 8.0.16+ (CHECK constraints are enforced from that version).

## Run

```powershell
.\.venv\Scripts\python.exe main.py init-db       # create database + tables (sql/schema.sql)
.\.venv\Scripts\python.exe main.py seed          # load synthetic data, Jan 2024 - Sep 2026
.\.venv\Scripts\python.exe main.py report        # latest complete month vs previous month
```

Report options:

| Option | Example | Meaning |
|---|---|---|
| `--period-type` | `month` (default), `quarter`, `year` | Reporting grain |
| `--period` | `2026-09`, `2026Q3`, `2025` | Period to report (default: latest complete one) |
| `--output` | `output` | Output folder |
| `--offline` | | Preview with generated data, without MySQL |

`seed` refuses to write into tables that already hold rows. Use `seed --reset` to replace them. `init-db` stops without changing anything if the target database already has `products`/`orders`/`order_items` tables with a different layout.

## Outputs (in `output/`)

| File | Content |
|---|---|
| `executive_report_<period>.html` | Self-contained executive KPI report: KPI tiles, summary, consolidated KPI table, all charts, monthly/category/region tables, reconciliation, KPI definitions |
| `kpi_report_<period>.xlsx` | Same data as sheets: KPI Summary, Monthly Trend, Category, Region, Category x Region, Reconciliation, Data Quality, KPI Definitions, Treatment Rules, Comparison Metrics |
| `charts/01_executive_dashboard.png` | One-page dashboard (8 KPI tiles, trend, category and region) |
| `charts/02-08_*.png` | Revenue trend + MoM/YoY growth, orders & AOV, gross-to-net waterfall, category and region comparisons, category × region heatmap, discount/return rates by category |
| `kpi_definitions.md` | KPI definitions sheet |

## KPI definitions

The full sheet, with formulas, inclusions, exclusions and treatment rules, is in [docs/KPI_DEFINITIONS.md](docs/KPI_DEFINITIONS.md). It is generated from `bi_dashboard/definitions.py`, the same module the code uses, so the written formulas and the calculations always match. Regenerate it with `python main.py definitions`.

Core rules:

- `Net Sales = Gross Sales − Discounts − Returns`, computed per line: `quantity × unit_price − COALESCE(discount,0) − COALESCE(return_amount,0)`.
- Cancelled orders are excluded from every sales KPI and every breakdown. They are reported only as Cancelled Orders, Cancellation Rate and Cancelled Order Value.
- Discount Rate and Return Rate both use Gross Sales as the denominator. Rate changes are reported in percentage points.
- Returns are attributed to the original order date. Returned orders stay in Order Count.

Each report includes reconciliation checks: category, region and month totals must equal the overall total, and the pandas results must match an independent SQL aggregate run in MySQL.

## Project structure

```
main.py                    CLI: init-db, seed, report, definitions
sql/schema.sql             MySQL tables, keys, CHECK constraints
sql/kpi_queries.sql        Reference SQL for every KPI (for checking in Workbench)
bi_dashboard/
  config.py                .env settings
  db.py                    MySQL schema setup, loading, SQL cross-check
  generator.py             Synthetic store data (trend, seasonality, discounts, returns, cancellations)
  definitions.py           KPI definitions + treatment rules (single source of truth)
  kpis.py                  Fact table, pandas aggregation, NumPy % change, reconciliation
  pipeline.py              Runs the analysis for one period
  charts.py                Matplotlib charts
  report.py                HTML, Excel and console outputs
docs/KPI_DEFINITIONS.md    Generated KPI definitions sheet
```
