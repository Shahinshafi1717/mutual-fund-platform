"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
Day 1: Data Ingestion & Quality Validation
File   : data_ingestion.py
Author : <Your Name>
Date   : 2026-06
============================================================
Purpose:
  Load all 10 raw CSV datasets, print diagnostics (.shape,
  .dtypes, .head), flag anomalies, and run a cross-file
  AMFI-code integrity check.
============================================================
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# ──────────────────────────────────────────────────────────
# 0. PATH SETUP  (never hardcode paths — always use pathlib)
# ──────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent          # project root
RAW_DIR   = BASE_DIR / "data" / "raw"
PROC_DIR  = BASE_DIR / "data" / "processed"

# Guarantee output folder exists
PROC_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────
# 1. FILE REGISTRY
# ──────────────────────────────────────────────────────────
FILES = {
    "fund_master"       : "01_fund_master.csv",
    "nav_history"       : "02_nav_history.csv",
    "aum_by_fund_house" : "03_aum_by_fund_house.csv",
    "monthly_sip"       : "04_monthly_sip_inflows.csv",
    "category_inflows"  : "05_category_inflows.csv",
    "folio_count"       : "06_industry_folio_count.csv",
    "scheme_perf"       : "07_scheme_performance.csv",
    "transactions"      : "08_investor_transactions.csv",
    "portfolio_holdings": "09_portfolio_holdings.csv",
    "benchmark_indices" : "10_benchmark_indices.csv",
}

# ──────────────────────────────────────────────────────────
# 2. DTYPE OVERRIDES
#    Specify expected dtypes so pandas doesn't silently
#    coerce AMFI codes or dates to wrong types.
# ──────────────────────────────────────────────────────────
DTYPE_MAP = {
    "fund_master"       : {"amfi_code": "int64"},
    "nav_history"       : {"amfi_code": "int64"},
    "scheme_perf"       : {"amfi_code": "int64"},
    "transactions"      : {"amfi_code": "int64"},
    "portfolio_holdings": {"amfi_code": "int64"},
}

# Columns to parse as dates
DATE_COLS = {
    "fund_master"       : ["launch_date"],
    "nav_history"       : ["date"],
    "aum_by_fund_house" : ["date"],
    "monthly_sip"       : ["month"],
    "category_inflows"  : ["month"],
    "folio_count"       : ["month"],
    "transactions"      : ["transaction_date"],
    "portfolio_holdings": ["portfolio_date"],
    "benchmark_indices" : ["date"],
}

# ──────────────────────────────────────────────────────────
# 3. HELPER UTILITIES
# ──────────────────────────────────────────────────────────

def section(title: str) -> None:
    """Print a formatted section header."""
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def load_csv(key: str, filename: str) -> pd.DataFrame:
    """
    Load a single CSV from RAW_DIR with optional dtype and
    date-parsing overrides.  Returns an empty DataFrame and
    prints an error if the file is missing.
    """
    filepath = RAW_DIR / filename
    if not filepath.exists():
        print(f"  [ERROR] File not found: {filepath}")
        return pd.DataFrame()

    kwargs = {}
    if key in DTYPE_MAP:
        kwargs["dtype"] = DTYPE_MAP[key]
    if key in DATE_COLS:
        kwargs["parse_dates"] = DATE_COLS[key]

    df = pd.read_csv(filepath, **kwargs)
    return df


def print_diagnostics(key: str, df: pd.DataFrame) -> dict:
    """
    Print shape, dtypes, head(3), null counts, and any
    obvious anomalies.  Returns a dict of anomaly flags.
    """
    section(f"[{key.upper()}]  →  {FILES[key]}")
    anomalies = {}

    print(f"\n📐 Shape : {df.shape[0]:,} rows × {df.shape[1]} columns")

    print("\n📋 Data Types:")
    print(df.dtypes.to_string())

    print("\n👀 First 3 rows:")
    print(df.head(3).to_string(index=False))

    # ── Null audit ──────────────────────────────────────
    null_counts = df.isnull().sum()
    null_cols   = null_counts[null_counts > 0]
    if not null_cols.empty:
        print(f"\n⚠️  Nulls detected:")
        for col, cnt in null_cols.items():
            pct = 100 * cnt / len(df)
            print(f"     {col:35s} → {cnt:5d} nulls  ({pct:.1f}%)")
        anomalies["nulls"] = null_cols.to_dict()
    else:
        print("\n✅ No null values")

    # ── Duplicate rows ───────────────────────────────────
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        print(f"\n⚠️  {dup_count} duplicate rows found")
        anomalies["duplicates"] = dup_count
    else:
        print("✅ No duplicate rows")

    return anomalies


# ──────────────────────────────────────────────────────────
# 4. DATASET-SPECIFIC ANOMALY CHECKS
# ──────────────────────────────────────────────────────────

def check_nav_history(df: pd.DataFrame) -> None:
    """Check NAV gaps (weekends/holidays need ffill later)."""
    print("\n🔍 NAV-specific checks:")
    print(f"   Date range : {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"   Unique funds: {df['amfi_code'].nunique()}")

    # Check for negative NAVs (impossible)
    neg_nav = df[df["nav"] <= 0]
    if not neg_nav.empty:
        print(f"   ⚠️  {len(neg_nav)} rows with NAV ≤ 0 — INVESTIGATE")
    else:
        print("   ✅ All NAV values are positive")

    # Rows per fund (expect ~1150 per fund for ~4.5 years daily)
    counts = df.groupby("amfi_code").size()
    print(f"   Rows per fund: min={counts.min()}, max={counts.max()}, mean={counts.mean():.0f}")
    if counts.min() < 900:
        short = counts[counts < 900].index.tolist()
        print(f"   ⚠️  Funds with < 900 NAV rows (possible data gaps): {short}")


def check_transactions(df: pd.DataFrame) -> None:
    """Check transaction distribution."""
    print("\n🔍 Transaction-specific checks:")
    print(f"   Date range  : {df['transaction_date'].min().date()} → {df['transaction_date'].max().date()}")
    print(f"   Unique investors: {df['investor_id'].nunique():,}")
    print(f"   Transaction types:\n{df['transaction_type'].value_counts().to_string()}")
    print(f"   Amount stats (INR):\n{df['amount_inr'].describe().to_string()}")

    # Flag zero-amount transactions
    zero_amt = (df["amount_inr"] == 0).sum()
    if zero_amt > 0:
        print(f"   ⚠️  {zero_amt} transactions with ₹0 amount")


def check_scheme_perf(df: pd.DataFrame) -> None:
    """Sanity-check performance metrics."""
    print("\n🔍 Performance-specific checks:")
    # Beta should typically be 0.5–1.5 for diversified equity funds
    outlier_beta = df[(df["beta"] < 0) | (df["beta"] > 2)]
    if not outlier_beta.empty:
        print(f"   ⚠️  {len(outlier_beta)} funds with unusual Beta (<0 or >2)")
    else:
        print("   ✅ Beta values in normal range")

    # Sharpe Ratio — negative is poor but valid; flag extreme outliers
    extreme_sharpe = df[df["sharpe_ratio"].abs() > 5]
    if not extreme_sharpe.empty:
        print(f"   ⚠️  {len(extreme_sharpe)} funds with Sharpe > ±5 — verify")
    else:
        print("   ✅ Sharpe ratios in expected range")


# ──────────────────────────────────────────────────────────
# 5. AMFI CODE INTEGRITY CHECK
# ──────────────────────────────────────────────────────────

def validate_amfi_codes(datasets: dict) -> None:
    """
    Cross-file validation:
    Every amfi_code in fund_master must exist in nav_history,
    scheme_performance, and portfolio_holdings.
    """
    section("DATA QUALITY REPORT — AMFI CODE INTEGRITY")

    master_codes = set(datasets["fund_master"]["amfi_code"].unique())
    print(f"\n📌 Reference set: {len(master_codes)} unique AMFI codes in fund_master")

    checks = {
        "nav_history"       : "amfi_code",
        "scheme_perf"       : "amfi_code",
        "portfolio_holdings": "amfi_code",
        "transactions"      : "amfi_code",
    }

    all_ok = True
    for ds_key, col in checks.items():
        df      = datasets[ds_key]
        ds_codes = set(df[col].unique())
        missing  = master_codes - ds_codes
        orphan   = ds_codes - master_codes

        status = "✅" if not missing and not orphan else "⚠️"
        print(f"\n  {status} {ds_key}")
        print(f"     Codes in this file  : {len(ds_codes)}")

        if missing:
            all_ok = False
            print(f"     ❌ In fund_master but MISSING here  : {sorted(missing)}")
        else:
            print(f"     ✅ All master codes present")

        if orphan:
            all_ok = False
            print(f"     ❌ In this file but NOT in master    : {sorted(orphan)}")
        else:
            print(f"     ✅ No orphan codes")

    section("SUMMARY")
    if all_ok:
        print("  🎉 All AMFI code checks PASSED — referential integrity OK")
    else:
        print("  ⚠️  Some checks FAILED — review above before building database")


# ──────────────────────────────────────────────────────────
# 6. FUND MASTER EXPLORATION  (Task 6)
# ──────────────────────────────────────────────────────────

def explore_fund_master(df: pd.DataFrame) -> None:
    """Print breakdown of unique values in key categorical columns."""
    section("FUND MASTER — CATEGORICAL BREAKDOWN")

    print("\n🏦 Fund Houses:")
    for i, fh in enumerate(df["fund_house"].unique(), 1):
        count = (df["fund_house"] == fh).sum()
        print(f"   {i:2d}. {fh:35s} — {count} schemes")

    print("\n📂 Categories:")
    print(df["category"].value_counts().to_string())

    print("\n📁 Sub-categories:")
    print(df["sub_category"].value_counts().to_string())

    print("\n⚠️  Risk Grades:")
    print(df["risk_category"].value_counts().to_string())

    print("\n📋 Plan types (Regular vs Direct):")
    print(df["plan"].value_counts().to_string())

    print("\n🔑 AMFI Code Structure:")
    codes = df["amfi_code"].sort_values()
    print(f"   Range : {codes.min()} → {codes.max()}")
    print(f"   Digits: {codes.astype(str).str.len().unique()} characters")
    print("   Note  : AMFI codes are 6-digit integers assigned sequentially")
    print("           by AMFI at scheme launch. Direct plans have codes")
    print("           close to (but different from) their Regular counterparts.")

    # Show Regular vs Direct pairing
    print("\n🔗 Regular ↔ Direct Plan Pairs (first 5):")
    pairs = df.groupby("scheme_name")
    paired = df[df.duplicated(subset=["fund_house","sub_category"], keep=False)]
    print(df[["amfi_code","scheme_name","plan"]].head(10).to_string(index=False))


# ──────────────────────────────────────────────────────────
# 7. MAIN ORCHESTRATOR
# ──────────────────────────────────────────────────────────

def main():
    print("\n" + "🚀 " * 20)
    print("  BLUESTOCK FINTECH — DAY 1: DATA INGESTION")
    print("🚀 " * 20)
    print(f"\n  Raw data folder  : {RAW_DIR}")
    print(f"  Processed folder : {PROC_DIR}")

    datasets    = {}
    all_anomalies = {}

    # ── Load & diagnose every file ──────────────────────
    for key, filename in FILES.items():
        df = load_csv(key, filename)
        if df.empty:
            print(f"  [SKIP] {key} — could not load")
            continue
        datasets[key] = df
        anomalies = print_diagnostics(key, df)
        if anomalies:
            all_anomalies[key] = anomalies

    # ── Dataset-specific deep dives ─────────────────────
    if "nav_history" in datasets:
        check_nav_history(datasets["nav_history"])

    if "transactions" in datasets:
        check_transactions(datasets["transactions"])

    if "scheme_perf" in datasets:
        check_scheme_perf(datasets["scheme_perf"])

    # ── Task 6: Fund master exploration ─────────────────
    if "fund_master" in datasets:
        explore_fund_master(datasets["fund_master"])

    # ── Task 7: AMFI code integrity ──────────────────────
    validate_amfi_codes(datasets)

    # ── Final anomaly summary ─────────────────────────────
    section("OVERALL ANOMALY SUMMARY")
    if not all_anomalies:
        print("  ✅ No critical anomalies detected across all files")
    else:
        for ds, issues in all_anomalies.items():
            print(f"  ⚠️  {ds}: {list(issues.keys())}")

    print("\n  📝 Action items for Day 2 (ETL):")
    print("     1. Forward-fill NAV gaps after reindexing to full date range")
    print("     2. Normalise benchmark name strings (e.g. 'NIFTY 100 TRI' → 'NIFTY100')")
    print("     3. Impute yoy_growth_pct nulls in monthly_sip (first 12 months)")
    print("     4. Cast all date columns to datetime64 before DB load")

    print("\n✅ Day 1 ingestion complete.\n")


if __name__ == "__main__":
    main()
