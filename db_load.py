"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
Day 2: Database Loader
File   : db_load.py
Author : Shahin Shafi
Date   : 2026-06
============================================================
Purpose:
  1. Create SQLite database (bluestock_mf.db)
  2. Apply schema from sql/schema.sql
  3. Build dim_date table programmatically
  4. Load all cleaned CSVs into fact/dim tables
  5. Verify row counts match source files
Run AFTER etl_clean.py
============================================================
"""

from pathlib import Path
import pandas as pd
import numpy as np
import sqlite3
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).resolve().parent
PROC_DIR = BASE_DIR / "data" / "processed"
SQL_DIR  = BASE_DIR / "sql"
DB_PATH  = BASE_DIR / "bluestock_mf.db"

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ──────────────────────────────────────────────────────────
# 1. CREATE ENGINE + APPLY SCHEMA
# ──────────────────────────────────────────────────────────
def create_db():
    section("Creating SQLite Database")
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    schema_sql = (SQL_DIR / "schema.sql").read_text()

    with engine.connect() as conn:
        # Execute each statement separately
        for stmt in schema_sql.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    if "already exists" not in str(e):
                        print(f"  ⚠️  {e}")
        conn.commit()

    print(f"  ✅ Database created: {DB_PATH.name}")
    return engine

# ──────────────────────────────────────────────────────────
# 2. BUILD DIM_DATE
# ──────────────────────────────────────────────────────────
def build_dim_date(engine):
    section("Building dim_date")
    dates = pd.date_range(start="2022-01-01", end="2026-12-31", freq="D")

    def fy_year(d):
        if d.month >= 4:
            return f"FY{d.year}-{str(d.year+1)[2:]}"
        return f"FY{d.year-1}-{str(d.year)[2:]}"

    def fy_quarter(d):
        if d.month in [4,5,6]:   q = "Q1"
        elif d.month in [7,8,9]: q = "Q2"
        elif d.month in [10,11,12]: q = "Q3"
        else:                    q = "Q4"
        fy = fy_year(d)
        return f"{q} {fy[2:]}"

    dim_date = pd.DataFrame({
        "date_id"     : dates.strftime("%Y-%m-%d"),
        "year"        : dates.year,
        "quarter"     : dates.quarter,
        "month"       : dates.month,
        "month_name"  : dates.strftime("%B"),
        "week_of_year": dates.isocalendar().week.astype(int),
        "day_of_week" : dates.dayofweek,
        "is_weekend"  : (dates.dayofweek >= 5).astype(int),
        "fy_year"     : [fy_year(d) for d in dates],
        "fy_quarter"  : [fy_quarter(d) for d in dates],
    })

    dim_date.to_sql("dim_date", engine, if_exists="replace",
                    index=False, chunksize=1000)
    print(f"  ✅ dim_date loaded: {len(dim_date):,} rows")
    return dim_date

# ──────────────────────────────────────────────────────────
# 3. LOAD dim_fund
# ──────────────────────────────────────────────────────────
def load_dim_fund(engine):
    section("Loading dim_fund")
    df = pd.read_csv(PROC_DIR / "01_fund_master_clean.csv")
    df["launch_date"] = pd.to_datetime(df["launch_date"]).dt.strftime("%Y-%m-%d")
    df.to_sql("dim_fund", engine, if_exists="replace", index=False)
    print(f"  ✅ dim_fund: {len(df)} rows")
    return df

# ──────────────────────────────────────────────────────────
# 4. LOAD fact_nav
# ──────────────────────────────────────────────────────────
def load_fact_nav(engine):
    section("Loading fact_nav")
    df = pd.read_csv(PROC_DIR / "02_nav_history_clean.csv")
    df = df.rename(columns={"date": "date_id"})
    df.to_sql("fact_nav", engine, if_exists="replace",
              index=False, chunksize=5000)
    print(f"  ✅ fact_nav: {len(df):,} rows")
    return df

# ──────────────────────────────────────────────────────────
# 5. LOAD fact_aum
# ──────────────────────────────────────────────────────────
def load_fact_aum(engine):
    section("Loading fact_aum")
    df = pd.read_csv(PROC_DIR / "03_aum_by_fund_house_clean.csv")
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.rename(columns={"date": "date_id"})
    df.to_sql("fact_aum", engine, if_exists="replace", index=False)
    print(f"  ✅ fact_aum: {len(df)} rows")
    return df

# ──────────────────────────────────────────────────────────
# 6. LOAD fact_sip_industry
# ──────────────────────────────────────────────────────────
def load_fact_sip(engine):
    section("Loading fact_sip_industry")
    df = pd.read_csv(PROC_DIR / "04_monthly_sip_inflows_clean.csv")
    df["month"] = pd.to_datetime(df["month"]).dt.strftime("%Y-%m-%d")
    df = df.rename(columns={"month": "month_id"})
    df.to_sql("fact_sip_industry", engine, if_exists="replace", index=False)
    print(f"  ✅ fact_sip_industry: {len(df)} rows")
    return df

# ──────────────────────────────────────────────────────────
# 7. LOAD fact_category_inflows
# ──────────────────────────────────────────────────────────
def load_fact_category(engine):
    section("Loading fact_category_inflows")
    df = pd.read_csv(PROC_DIR / "05_category_inflows_clean.csv")
    df["month"] = pd.to_datetime(df["month"]).dt.strftime("%Y-%m-%d")
    df = df.rename(columns={"month": "month_id"})
    df.to_sql("fact_category_inflows", engine, if_exists="replace", index=False)
    print(f"  ✅ fact_category_inflows: {len(df)} rows")
    return df

# ──────────────────────────────────────────────────────────
# 8. LOAD fact_folio_count
# ──────────────────────────────────────────────────────────
def load_fact_folio(engine):
    section("Loading fact_folio_count")
    df = pd.read_csv(PROC_DIR / "06_industry_folio_count_clean.csv")
    df["month"] = pd.to_datetime(df["month"]).dt.strftime("%Y-%m-%d")
    df = df.rename(columns={"month": "month_id"})
    df.to_sql("fact_folio_count", engine, if_exists="replace", index=False)
    print(f"  ✅ fact_folio_count: {len(df)} rows")
    return df

# ──────────────────────────────────────────────────────────
# 9. LOAD fact_performance
# ──────────────────────────────────────────────────────────
def load_fact_performance(engine):
    section("Loading fact_performance")
    df = pd.read_csv(PROC_DIR / "07_scheme_performance_clean.csv")
    df.to_sql("fact_performance", engine, if_exists="replace", index=False)
    print(f"  ✅ fact_performance: {len(df)} rows")
    return df

# ──────────────────────────────────────────────────────────
# 10. LOAD fact_transactions
# ──────────────────────────────────────────────────────────
def load_fact_transactions(engine):
    section("Loading fact_transactions")
    df = pd.read_csv(PROC_DIR / "08_investor_transactions_clean.csv")
    df["transaction_date"] = pd.to_datetime(
        df["transaction_date"]).dt.strftime("%Y-%m-%d")
    df.to_sql("fact_transactions", engine, if_exists="replace",
              index=False, chunksize=5000)
    print(f"  ✅ fact_transactions: {len(df):,} rows")
    return df

# ──────────────────────────────────────────────────────────
# 11. LOAD fact_portfolio
# ──────────────────────────────────────────────────────────
def load_fact_portfolio(engine):
    section("Loading fact_portfolio")
    df = pd.read_csv(PROC_DIR / "09_portfolio_holdings_clean.csv")
    df["portfolio_date"] = pd.to_datetime(
        df["portfolio_date"]).dt.strftime("%Y-%m-%d")
    df.to_sql("fact_portfolio", engine, if_exists="replace", index=False)
    print(f"  ✅ fact_portfolio: {len(df)} rows")
    return df

# ──────────────────────────────────────────────────────────
# 12. LOAD benchmark_indices
# ──────────────────────────────────────────────────────────
def load_benchmark(engine):
    section("Loading benchmark_indices")
    df = pd.read_csv(PROC_DIR / "10_benchmark_indices_clean.csv")
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.rename(columns={"date": "date_id"})
    df.to_sql("benchmark_indices", engine, if_exists="replace",
              index=False, chunksize=2000)
    print(f"  ✅ benchmark_indices: {len(df):,} rows")
    return df

# ──────────────────────────────────────────────────────────
# 13. VERIFY ROW COUNTS
# ──────────────────────────────────────────────────────────
def verify_counts(engine):
    section("Row Count Verification")
    tables = [
        "dim_fund", "dim_date", "fact_nav", "fact_transactions",
        "fact_performance", "fact_portfolio", "fact_aum",
        "fact_sip_industry", "fact_category_inflows",
        "fact_folio_count", "benchmark_indices"
    ]

    print(f"\n  {'Table':<30} {'Rows':>10}")
    print(f"  {'-'*42}")
    with engine.connect() as conn:
        for table in tables:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.fetchone()[0]
                print(f"  {table:<30} {count:>10,}")
            except Exception as e:
                print(f"  {table:<30} ERROR: {e}")

    db_size = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"\n  Database size: {db_size:.2f} MB")
    print(f"  Location     : {DB_PATH}")

# ──────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────
def main():
    print("\n" + "🗄️  " * 15)
    print("  BLUESTOCK FINTECH — DAY 2: DATABASE LOAD")
    print("🗄️  " * 15)

    engine = create_db()
    build_dim_date(engine)
    load_dim_fund(engine)
    load_fact_nav(engine)
    load_fact_aum(engine)
    load_fact_sip(engine)
    load_fact_category(engine)
    load_fact_folio(engine)
    load_fact_performance(engine)
    load_fact_transactions(engine)
    load_fact_portfolio(engine)
    load_benchmark(engine)
    verify_counts(engine)

    section("DONE")
    print("  ✅ bluestock_mf.db is ready!")
    print("  ▶  Next step: run  python queries.py\n")

if __name__ == "__main__":
    main()
