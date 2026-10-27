"""E-Commerce Business Intelligence Dashboard - command line entry point.

    python main.py init-db                      create the MySQL database and tables
    python main.py seed [--reset]               load synthetic store data into MySQL
    python main.py report [--period-type month --period 2026-09]
    python main.py definitions                  regenerate docs/KPI_DEFINITIONS.md
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from bi_dashboard import charts, db, generator, report
from bi_dashboard.config import DEFAULT_OUTPUT_DIR, DOCS_DIR, get_currency, get_db_settings
from bi_dashboard.definitions import write_definitions_markdown
from bi_dashboard.pipeline import run_analysis


def cmd_init_db(_: argparse.Namespace) -> int:
    settings = get_db_settings()
    db.init_database(settings)
    print(f"Database '{settings.name}' and tables products, orders, order_items are ready "
          f"on {settings.host}:{settings.port}.")
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    settings = get_db_settings()
    engine = db.make_engine(settings)
    try:
        counts = db.table_row_counts(engine)
        if any(counts.values()) and not args.reset:
            print(f"Tables already contain data {counts}. Re-run with --reset to replace it.")
            return 1
        tables = generator.generate(args.start, args.end, args.orders_per_day, args.seed)
        t0 = time.perf_counter()
        if args.reset:
            db.clear_tables(engine)
        db.insert_tables(engine, tables)
        counts = db.table_row_counts(engine)
    finally:
        engine.dispose()
    print(f"Loaded {counts['products']:,} products, {counts['orders']:,} orders and "
          f"{counts['order_items']:,} order items ({args.start} to {args.end}) "
          f"in {time.perf_counter() - t0:.1f}s.")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    currency = get_currency()
    if args.offline:
        tables = generator.generate(args.start, args.end, args.orders_per_day, args.seed)
        data = run_analysis(tables, args.period_type, args.period, currency,
                            source="synthetic data (offline preview, not MySQL)")
    else:
        settings = get_db_settings()
        engine = db.make_engine(settings)
        try:
            tables = db.load_tables(engine)
            data = run_analysis(tables, args.period_type, args.period, currency,
                                source=f"MySQL {settings.name}@{settings.host}",
                                sql_totals=lambda s, e: db.sql_period_totals(engine, s, e))
        finally:
            engine.dispose()

    out_dir = Path(args.output)
    chart_list = charts.render_all(data, out_dir)
    files = report.write_all(data, chart_list, out_dir)
    print(report.console_summary(data))
    print("\nOutputs:")
    for path in [*files.values(), *(c.path for c in chart_list)]:
        print(f"  {path}")
    return 1 if (data.reconciliation["status"] == "FAIL").any() else 0


def cmd_definitions(_: argparse.Namespace) -> int:
    path = write_definitions_markdown(DOCS_DIR / "KPI_DEFINITIONS.md")
    print(f"Wrote {path}")
    return 0


def _add_generator_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--start", default="2024-01-01", help="first order date (YYYY-MM-DD)")
    p.add_argument("--end", default="2026-09-30", help="last order date (YYYY-MM-DD)")
    p.add_argument("--orders-per-day", type=float, default=40.0, help="average orders per day at the start")
    p.add_argument("--seed", type=int, default=42, help="random seed for reproducible data")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="E-Commerce Business Intelligence Dashboard")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="create the MySQL database and tables").set_defaults(func=cmd_init_db)

    seed = sub.add_parser("seed", help="load synthetic store data into MySQL")
    _add_generator_args(seed)
    seed.add_argument("--reset", action="store_true", help="delete existing rows before loading")
    seed.set_defaults(func=cmd_seed)

    rep = sub.add_parser("report", help="build the KPI dashboard, charts, HTML and Excel reports")
    rep.add_argument("--period-type", choices=["month", "quarter", "year"], default="month")
    rep.add_argument("--period", help="e.g. 2026-09, 2026Q3 or 2025 (default: latest complete period)")
    rep.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="output folder")
    rep.add_argument("--offline", action="store_true",
                     help="preview with freshly generated data instead of reading MySQL")
    _add_generator_args(rep)
    rep.set_defaults(func=cmd_report)

    sub.add_parser("definitions", help="write docs/KPI_DEFINITIONS.md").set_defaults(func=cmd_definitions)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # show a clear message instead of a long traceback
        name = type(exc).__name__
        if "OperationalError" in name or "Access denied" in str(exc):
            print(f"Could not connect to MySQL: {exc}\nCheck DB_HOST, DB_USER and DB_PASSWORD in .env.",
                  file=sys.stderr)
            return 2
        if isinstance(exc, (RuntimeError, ValueError)):
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main())
