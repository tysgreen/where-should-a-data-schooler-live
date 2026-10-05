"""Build the DuckDB database from the raw files, layer by layer.

    python pipeline/run_models.py

1. raw      - load saved API responses (sql/01_raw.sql) + the ONS spreadsheet
2. staging  - clean, type and deduplicate (sql/02_staging.sql)
3. marts    - one scored row per station (sql/03_marts.sql)
4. export   - write marts.stations to data/marts/stations.parquet for the app

Full rebuild every time: the database is thrown away and recreated from the
raw files, so running this twice always gives the same result.
"""
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from config import CRIME_MONTHS, DB_PATH, RADIUS_M, RAW_DIR, ROOT  # noqa: E402

SQL_DIR = ROOT / "sql"
MART_EXPORT = ROOT / "data" / "marts" / "stations.parquet"


def load_ons_rents(con: duckdb.DuckDBPyConnection) -> None:
    """The ONS file is an Excel workbook; the data sits in sheet 'Table 1'
    under two lines of title text, so the header is on the third row."""
    df = pd.read_excel(RAW_DIR / "ons" / "pipr_monthly.xlsx", sheet_name="Table 1", header=2)
    df = df.astype({c: "string" for c in df.columns if c != "Time period"})  # keep '[x]' markers as text
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE OR REPLACE TABLE raw.ons_rents AS SELECT * FROM df")


def load_london_rents(con: duckdb.DuckDBPyConnection) -> None:
    """ONS 'Private rental market in London': sheet '2' has rents by borough and
    type of home (Room, Studio, One Bedroom...). The period covered is in the
    cover sheet's title, e.g. 'Private Rental Market in London: April 2025 to March 2026'."""
    path = RAW_DIR / "ons" / "london_rental_stats.xlsx"
    df = pd.read_excel(path, sheet_name="2", header=2).astype("string")  # keep '..' markers as text
    title = pd.read_excel(path, sheet_name="Cover sheet", header=None).iloc[0, 0]
    df["period"] = title.split(":")[-1].strip()
    con.execute("CREATE OR REPLACE TABLE raw.ons_london_rents AS SELECT * FROM df")


def run_sql_file(con, path: Path, **params) -> None:
    sql = path.read_text(encoding="utf-8").format(**params)
    con.execute(sql)


def main():
    start = time.time()
    DB_PATH.unlink(missing_ok=True)  # full rebuild
    con = duckdb.connect(str(DB_PATH))
    params = {"raw_dir": RAW_DIR.as_posix(), "radius_m": RADIUS_M, "crime_months": CRIME_MONTHS}

    print("1/4 raw")
    run_sql_file(con, SQL_DIR / "01_raw.sql", **params)
    load_ons_rents(con)
    load_london_rents(con)
    print("2/4 staging")
    run_sql_file(con, SQL_DIR / "02_staging.sql", **params)
    print("3/4 marts")
    run_sql_file(con, SQL_DIR / "03_marts.sql", **params)

    print("4/4 export")
    MART_EXPORT.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY marts.stations TO '{MART_EXPORT.as_posix()}' (FORMAT parquet)")

    for schema, table in con.execute(
        "SELECT schema_name, table_name FROM duckdb_tables() ORDER BY schema_name, table_name"
    ).fetchall():
        n = con.execute(f"SELECT count(*) FROM {schema}.{table}").fetchone()[0]
        print(f"   {schema}.{table:22} {n:>9,} rows")
    con.close()
    print(f"done in {time.time() - start:.0f}s -> {DB_PATH.name}, {MART_EXPORT.name}")


if __name__ == "__main__":
    main()
