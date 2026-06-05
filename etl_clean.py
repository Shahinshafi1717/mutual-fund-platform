"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
Day 2: ETL Cleaning Pipeline
File   : etl_clean.py
Author : Shahin Shafi
Date   : 2026-06
============================================================
Purpose:
  Read all 10 raw CSVs, apply cleaning rules per dataset,
  save cleaned versions to data/processed/.
  Run this BEFORE db_load.py.
============================================================
"""

from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR  = BASE_DIR / "data" / "raw"
PROC_DIR = BASE_DIR / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ── VALID ENUM VALUES ─────────────────────────────────────
VALID_TX_TYPES  = {"SIP", "Lumpsum", "Redemption"}
VALID_KYC       = {"Verified", "Pending"}
VALID_PLANS     = {"Regular", "Direct"}
VALID_RISK      = {"Low", "Moderately Low", "Moderate", "Moderately High", "High", "Very High"}

# ── BENCHMARK NAME MAP (fund_master → benchmark_indices) ──
BENCHMARK_MAP = {
    "NIFTY 100 TRI"          : "NIFTY100",
    "BSE 250 SmallCap TRI"   : "BSE_SMALLCAP",
    "Nifty Midcap 150 TRI"   : "NIFTY_MIDCAP150",
    "NIFTY 500 TRI"          : "NIFTY500",
    "NIFTY 50 TRI"           : "NIFTY50",
    "CRISIL Liquid Fund Index": "CRISIL_LIQUID",
    "CRISIL Gilt Index"      : "CRISIL_GILT",
}

# ──────────────────────────────────────────────────────────
# 1. FUND MASTER
# ──────────────────────────────────────────────────────────
def clean_fund_master():
    section("Cleaning: 01_fund_master.csv")
    df = pd.read_csv(RAW_DIR / "01_fund_master.csv",
                     dtype={"amfi_code": "int64"},
                     parse_dates=["launch_date"])

    before = len(df)

    # Normalise benchmark names to match benchmark_indices table
    df["benchmark_key"] = df["benchmark"].map(BENCHMARK_MAP)
    unmapped = df[df["benchmark_key"].isna()]["benchmark"].unique()
    if len(unmapped):
        print(f"  ⚠️  Unmapped benchmarks: {unmapped}")
    else:
        print("  ✅ All benchmark names mapped")

    # Validate enums
    bad_plan = df[~df["plan"].isin(VALID_PLANS)]
    bad_risk = df[~df["risk_category"].isin(VALID_RISK)]
    print(f"  Plan enum errors : {len(bad_plan)}")
    print(f"  Risk enum errors : {len(bad_risk)}")

    # Validate expense ratio range
    bad_exp = df[(df["expense_ratio_pct"] < 0.1) | (df["expense_ratio_pct"] > 2.5)]
    print(f"  Expense ratio out of range (0.1–2.5%): {len(bad_exp)} rows")

    # Remove duplicates
    df = df.drop_duplicates(subset=["amfi_code"])
    print(f"  Rows: {before} → {len(df)} (removed {before - len(df)} duplicates)")

    out = PROC_DIR / "01_fund_master_clean.csv"
    df.to_csv(out, index=False)
    print(f"  💾 Saved → {out.name}")
    return df

# ──────────────────────────────────────────────────────────
# 2. NAV HISTORY  (most complex — needs ffill)
# ──────────────────────────────────────────────────────────
def clean_nav_history():
    section("Cleaning: 02_nav_history.csv")
    df = pd.read_csv(RAW_DIR / "02_nav_history.csv",
                     dtype={"amfi_code": "int64"},
                     parse_dates=["date"])

    before = len(df)

    # Sort correctly — essential before ffill
    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)

    # Remove duplicates (same fund + same date)
    df = df.drop_duplicates(subset=["amfi_code", "date"])
    print(f"  Duplicates removed: {before - len(df)}")

    # Remove rows with NAV <= 0
    bad_nav = df[df["nav"] <= 0]
    if len(bad_nav):
        print(f"  ⚠️  Removing {len(bad_nav)} rows with NAV ≤ 0")
        df = df[df["nav"] > 0]
    else:
        print("  ✅ All NAV values positive")

    # Forward-fill missing dates (weekends + holidays)
    # Reindex each fund to a full calendar date range, then ffill
    full_date_range = pd.date_range(
        start=df["date"].min(),
        end=df["date"].max(),
        freq="D"
    )
    funds = df["amfi_code"].unique()
    filled_frames = []

    for code in funds:
        fund_df = df[df["amfi_code"] == code].set_index("date")
        fund_df = fund_df.reindex(full_date_range)         # insert missing dates as NaN
        fund_df["amfi_code"] = code                        # restore fund code
        fund_df["nav"] = fund_df["nav"].ffill()            # carry last known NAV forward
        fund_df = fund_df.dropna(subset=["nav"])           # drop leading NaNs (before first NAV)
        filled_frames.append(fund_df)

    df_filled = pd.concat(filled_frames)
    df_filled.index.name = "date"
    df_filled = df_filled.reset_index()
    df_filled = df_filled[["amfi_code", "date", "nav"]]
    df_filled["date"] = df_filled["date"].dt.strftime("%Y-%m-%d")

    print(f"  Rows before ffill : {before:,}")
    print(f"  Rows after  ffill : {len(df_filled):,}")
    print(f"  Dates filled in   : {len(df_filled) - before:,} (weekends/holidays)")

    out = PROC_DIR / "02_nav_history_clean.csv"
    df_filled.to_csv(out, index=False)
    print(f"  💾 Saved → {out.name}")
    return df_filled

# ──────────────────────────────────────────────────────────
# 3. AUM BY FUND HOUSE
# ──────────────────────────────────────────────────────────
def clean_aum():
    section("Cleaning: 03_aum_by_fund_house.csv")
    df = pd.read_csv(RAW_DIR / "03_aum_by_fund_house.csv", parse_dates=["date"])

    df = df.drop_duplicates()
    df = df.sort_values(["fund_house", "date"]).reset_index(drop=True)

    bad_aum = df[df["aum_crore"] <= 0]
    print(f"  Negative/zero AUM rows: {len(bad_aum)}")
    print(f"  ✅ Shape: {df.shape}")

    out = PROC_DIR / "03_aum_by_fund_house_clean.csv"
    df.to_csv(out, index=False)
    print(f"  💾 Saved → {out.name}")
    return df

# ──────────────────────────────────────────────────────────
# 4. MONTHLY SIP INFLOWS
# ──────────────────────────────────────────────────────────
def clean_sip():
    section("Cleaning: 04_monthly_sip_inflows.csv")
    df = pd.read_csv(RAW_DIR / "04_monthly_sip_inflows.csv", parse_dates=["month"])

    df = df.sort_values("month").reset_index(drop=True)

    # yoy_growth_pct: first 12 months are NaN by design (no prior year)
    # Calculate it from the data instead of leaving nulls
    df["yoy_growth_pct"] = df["yoy_growth_pct"].fillna(
        df["sip_inflow_crore"].pct_change(periods=12).mul(100).round(2)
    )
    nulls_remaining = df["yoy_growth_pct"].isna().sum()
    print(f"  yoy_growth_pct nulls remaining: {nulls_remaining}")
    print(f"  ✅ Shape: {df.shape}")

    out = PROC_DIR / "04_monthly_sip_inflows_clean.csv"
    df.to_csv(out, index=False)
    print(f"  💾 Saved → {out.name}")
    return df

# ──────────────────────────────────────────────────────────
# 5. CATEGORY INFLOWS
# ──────────────────────────────────────────────────────────
def clean_category_inflows():
    section("Cleaning: 05_category_inflows.csv")
    df = pd.read_csv(RAW_DIR / "05_category_inflows.csv", parse_dates=["month"])

    df = df.drop_duplicates()
    df = df.sort_values(["category", "month"]).reset_index(drop=True)
    print(f"  Categories: {df['category'].unique().tolist()}")
    print(f"  ✅ Shape: {df.shape}")

    out = PROC_DIR / "05_category_inflows_clean.csv"
    df.to_csv(out, index=False)
    print(f"  💾 Saved → {out.name}")
    return df

# ──────────────────────────────────────────────────────────
# 6. FOLIO COUNT
# ──────────────────────────────────────────────────────────
def clean_folio():
    section("Cleaning: 06_industry_folio_count.csv")
    df = pd.read_csv(RAW_DIR / "06_industry_folio_count.csv", parse_dates=["month"])

    df = df.drop_duplicates()
    df = df.sort_values("month").reset_index(drop=True)

    # Validate: equity + debt + hybrid + others should ≈ total
    df["computed_total"] = (
        df["equity_folios_crore"] + df["debt_folios_crore"] +
        df["hybrid_folios_crore"] + df["others_folios_crore"]
    ).round(2)
    df["total_diff"] = (df["total_folios_crore"] - df["computed_total"]).abs()
    mismatches = df[df["total_diff"] > 0.05]
    print(f"  Total folio mismatches: {len(mismatches)}")
    df = df.drop(columns=["computed_total", "total_diff"])
    print(f"  ✅ Shape: {df.shape}")

    out = PROC_DIR / "06_industry_folio_count_clean.csv"
    df.to_csv(out, index=False)
    print(f"  💾 Saved → {out.name}")
    return df

# ──────────────────────────────────────────────────────────
# 7. SCHEME PERFORMANCE
# ──────────────────────────────────────────────────────────
def clean_scheme_perf():
    section("Cleaning: 07_scheme_performance.csv")
    df = pd.read_csv(RAW_DIR / "07_scheme_performance.csv",
                     dtype={"amfi_code": "int64"})

    # Validate all return columns are numeric
    return_cols = ["return_1yr_pct", "return_3yr_pct", "return_5yr_pct", "benchmark_3yr_pct"]
    for col in return_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        nulls = df[col].isna().sum()
        if nulls:
            print(f"  ⚠️  {col}: {nulls} non-numeric values coerced to NaN")

    # Flag anomalies — note: Sharpe > 5 for Liquid funds is VALID (not a bug)
    # Liquid funds have very low volatility so Sharpe naturally looks high
    high_sharpe = df[df["sharpe_ratio"] > 5][["scheme_name", "sharpe_ratio", "category"]]
    if len(high_sharpe):
        print(f"\n  ℹ️  High Sharpe funds (Liquid funds — expected):")
        print(high_sharpe.to_string(index=False))

    # Validate expense ratio range
    bad_exp = df[(df["expense_ratio_pct"] < 0.1) | (df["expense_ratio_pct"] > 2.5)]
    print(f"\n  Expense ratio out of 0.1–2.5% range: {len(bad_exp)} rows")
    if len(bad_exp):
        print(bad_exp[["scheme_name", "expense_ratio_pct"]].to_string(index=False))

    # Validate beta is positive (equity funds)
    neg_beta = df[df["beta"] < 0]
    print(f"  Negative beta rows: {len(neg_beta)}")

    # Validate max_drawdown is negative (drawdowns are losses)
    bad_dd = df[df["max_drawdown_pct"] > 0]
    if len(bad_dd):
        print(f"  ⚠️  Positive max_drawdown (should be negative): {len(bad_dd)}")
        df.loc[df["max_drawdown_pct"] > 0, "max_drawdown_pct"] *= -1

    df = df.drop_duplicates(subset=["amfi_code"])
    print(f"  ✅ Shape: {df.shape}")

    out = PROC_DIR / "07_scheme_performance_clean.csv"
    df.to_csv(out, index=False)
    print(f"  💾 Saved → {out.name}")
    return df

# ──────────────────────────────────────────────────────────
# 8. INVESTOR TRANSACTIONS
# ──────────────────────────────────────────────────────────
def clean_transactions():
    section("Cleaning: 08_investor_transactions.csv")
    df = pd.read_csv(RAW_DIR / "08_investor_transactions.csv",
                     dtype={"amfi_code": "int64"},
                     parse_dates=["transaction_date"])

    before = len(df)

    # Standardise transaction_type capitalisation
    df["transaction_type"] = df["transaction_type"].str.strip().str.title()
    # Map variations to standard values
    tx_map = {"Sip": "SIP", "Lumpsum": "Lumpsum", "Redemption": "Redemption"}
    df["transaction_type"] = df["transaction_type"].replace(tx_map)
    invalid_tx = df[~df["transaction_type"].isin(VALID_TX_TYPES)]
    print(f"  Invalid transaction types: {len(invalid_tx)}")
    print(f"  Transaction type counts:\n{df['transaction_type'].value_counts().to_string()}")

    # Validate amount > 0
    bad_amt = df[df["amount_inr"] <= 0]
    print(f"  Rows with amount ≤ 0: {len(bad_amt)}")
    df = df[df["amount_inr"] > 0]

    # Validate KYC status enum
    invalid_kyc = df[~df["kyc_status"].isin(VALID_KYC)]
    print(f"  Invalid KYC values: {len(invalid_kyc)}")

    # Remove duplicates
    df = df.drop_duplicates()
    print(f"  Rows: {before:,} → {len(df):,} (removed {before - len(df)})")

    out = PROC_DIR / "08_investor_transactions_clean.csv"
    df.to_csv(out, index=False)
    print(f"  💾 Saved → {out.name}")
    return df

# ──────────────────────────────────────────────────────────
# 9. PORTFOLIO HOLDINGS
# ──────────────────────────────────────────────────────────
def clean_portfolio():
    section("Cleaning: 09_portfolio_holdings.csv")
    df = pd.read_csv(RAW_DIR / "09_portfolio_holdings.csv",
                     dtype={"amfi_code": "int64"},
                     parse_dates=["portfolio_date"])

    df = df.drop_duplicates(subset=["amfi_code", "stock_symbol"])
    df = df.sort_values(["amfi_code", "weight_pct"], ascending=[True, False])

    # Validate weight_pct > 0
    bad_wt = df[df["weight_pct"] <= 0]
    print(f"  Rows with weight ≤ 0: {len(bad_wt)}")

    # Check total weight per fund (should be ≤ 100%)
    wt_check = df.groupby("amfi_code")["weight_pct"].sum().round(2)
    over_100 = wt_check[wt_check > 100]
    if len(over_100):
        print(f"  ⚠️  Funds with total weight > 100%: {over_100.to_dict()}")
    else:
        print(f"  ✅ All fund weights ≤ 100% (showing top 5 holdings shown per fund)")

    print(f"  ✅ Shape: {df.shape}")

    out = PROC_DIR / "09_portfolio_holdings_clean.csv"
    df.to_csv(out, index=False)
    print(f"  💾 Saved → {out.name}")
    return df

# ──────────────────────────────────────────────────────────
# 10. BENCHMARK INDICES
# ──────────────────────────────────────────────────────────
def clean_benchmark():
    section("Cleaning: 10_benchmark_indices.csv")
    df = pd.read_csv(RAW_DIR / "10_benchmark_indices.csv", parse_dates=["date"])

    before = len(df)
    df = df.drop_duplicates(subset=["date", "index_name"])
    df = df.sort_values(["index_name", "date"]).reset_index(drop=True)

    bad_val = df[df["close_value"] <= 0]
    print(f"  Rows with close_value ≤ 0: {len(bad_val)}")
    print(f"  Indices: {df['index_name'].unique().tolist()}")
    print(f"  Rows: {before} → {len(df)} (removed {before - len(df)} duplicates)")

    out = PROC_DIR / "10_benchmark_indices_clean.csv"
    df.to_csv(out, index=False)
    print(f"  💾 Saved → {out.name}")
    return df

# ──────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────
def main():
    print("\n" + "🧹 " * 20)
    print("  BLUESTOCK FINTECH — DAY 2: ETL CLEANING")
    print("🧹 " * 20)

    datasets = {}
    datasets["fund_master"]    = clean_fund_master()
    datasets["nav_history"]    = clean_nav_history()
    datasets["aum"]            = clean_aum()
    datasets["sip"]            = clean_sip()
    datasets["cat_inflows"]    = clean_category_inflows()
    datasets["folio"]          = clean_folio()
    datasets["scheme_perf"]    = clean_scheme_perf()
    datasets["transactions"]   = clean_transactions()
    datasets["portfolio"]      = clean_portfolio()
    datasets["benchmark"]      = clean_benchmark()

    section("CLEANING SUMMARY")
    print(f"\n  {'Dataset':<30} {'Rows':>8}")
    print(f"  {'-'*40}")
    for name, df in datasets.items():
        print(f"  {name:<30} {len(df):>8,}")

    print(f"\n  ✅ All 10 cleaned CSVs saved to: data/processed/")
    print("  ▶  Next step: run  python db_load.py\n")

if __name__ == "__main__":
    main()
