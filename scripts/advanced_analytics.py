"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
Day 6: Advanced Analytics
File   : scripts/advanced_analytics.py
Author : Shahin Shafi
Date   : 2026-06
============================================================
Tasks:
  1. Historical VaR (95%) & CVaR for all 40 schemes
  2. Rolling 90-day Sharpe for 5 key funds
  3. Investor cohort analysis
  4. SIP continuity analysis
  5. Fund recommender system
  6. Sector HHI concentration
Outputs:
  data/processed/var_cvar_report.csv
  reports/charts/22_rolling_sharpe.png
  reports/charts/23_hhi_concentration.png
  reports/charts/24_cohort_analysis.png
  reports/charts/25_sip_continuity.png
============================================================
"""

import warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

BASE_DIR   = Path(__file__).resolve().parent.parent
DB_PATH    = BASE_DIR / "bluestock_mf.db"
PROC_DIR   = BASE_DIR / "data" / "processed"
CHARTS_DIR = BASE_DIR / "reports" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams["figure.dpi"] = 120
COLORS = ["#1565C0","#E53935","#2E7D32","#6A1B9A","#E65100",
          "#00838F","#F9A825","#AD1457","#558B2F","#4527A0"]

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ══════════════════════════════════════════════════════════
# LOAD DATA
# ══════════════════════════════════════════════════════════
def load_data():
    conn = sqlite3.connect(DB_PATH)
    nav = pd.read_sql("""
        SELECT n.amfi_code, n.date_id, n.nav,
               f.scheme_name, f.sub_category, f.category,
               f.risk_category, f.plan, f.fund_house
        FROM fact_nav n JOIN dim_fund f ON n.amfi_code=f.amfi_code
    """, conn)
    nav["date"] = pd.to_datetime(nav["date_id"])

    tx = pd.read_sql("SELECT * FROM fact_transactions", conn)
    tx["date"] = pd.to_datetime(tx["transaction_date"])

    perf = pd.read_sql("""
        SELECT p.amfi_code, p.scheme_name, p.sharpe_ratio,
               p.return_3yr_pct, p.expense_ratio_pct,
               p.risk_grade, p.morningstar_rating,
               f.sub_category, f.plan, f.fund_house
        FROM fact_performance p
        JOIN dim_fund f ON p.amfi_code=f.amfi_code
    """, conn)

    port = pd.read_sql("""
        SELECT p.amfi_code, p.sector, p.weight_pct, p.stock_name,
               f.scheme_name, f.sub_category
        FROM fact_portfolio p
        JOIN dim_fund f ON p.amfi_code=f.amfi_code
        WHERE f.category='Equity'
    """, conn)

    conn.close()

    nav_wide = nav.pivot_table(index="date", columns="amfi_code", values="nav")
    returns  = nav_wide.pct_change().dropna()

    # Fund metadata lookup
    fund_meta = nav[["amfi_code","scheme_name","sub_category",
                     "risk_category","plan","fund_house"]].drop_duplicates("amfi_code")

    print(f"  NAV returns : {returns.shape}")
    print(f"  Transactions: {len(tx):,}")
    print(f"  Funds       : {len(fund_meta)}")
    return returns, tx, perf, port, fund_meta

# ══════════════════════════════════════════════════════════
# TASK 1: VaR & CVaR
# ══════════════════════════════════════════════════════════
def compute_var_cvar(returns, fund_meta):
    section("Task 1: Historical VaR (95%) & CVaR")

    results = []
    for code in returns.columns:
        r = returns[code].dropna()
        if len(r) < 100:
            continue

        var_95  = np.percentile(r, 5)          # 5th percentile = 95% VaR
        cvar_95 = r[r <= var_95].mean()         # Mean of tail losses

        var_99  = np.percentile(r, 1)
        cvar_99 = r[r <= var_99].mean()

        # Annualised VaR (approximate)
        var_ann = var_95 * np.sqrt(252)

        meta = fund_meta[fund_meta["amfi_code"]==code]
        results.append({
            "amfi_code"       : code,
            "scheme_name"     : meta["scheme_name"].values[0] if len(meta) else str(code),
            "sub_category"    : meta["sub_category"].values[0] if len(meta) else "",
            "plan"            : meta["plan"].values[0] if len(meta) else "",
            "var_95_daily_pct": round(var_95 * 100, 4),
            "cvar_95_daily_pct": round(cvar_95 * 100, 4),
            "var_99_daily_pct": round(var_99 * 100, 4),
            "cvar_99_daily_pct": round(cvar_99 * 100, 4),
            "var_ann_pct"     : round(var_ann * 100, 4),
            "n_trading_days"  : len(r),
        })

    df = pd.DataFrame(results).sort_values("var_95_daily_pct")

    print(f"\n  Highest Risk (worst VaR 95%):")
    print(df.nsmallest(5,"var_95_daily_pct")[
        ["scheme_name","var_95_daily_pct","cvar_95_daily_pct"]
    ].to_string(index=False))

    print(f"\n  Lowest Risk (best VaR 95%):")
    print(df.nlargest(5,"var_95_daily_pct")[
        ["scheme_name","var_95_daily_pct","cvar_95_daily_pct"]
    ].to_string(index=False))

    out = PROC_DIR / "var_cvar_report.csv"
    df.to_csv(out, index=False)
    print(f"\n  💾 Saved → var_cvar_report.csv ({len(df)} rows)")
    return df

# ══════════════════════════════════════════════════════════
# TASK 2: Rolling 90-day Sharpe
# ══════════════════════════════════════════════════════════
def rolling_sharpe_chart(returns, fund_meta):
    section("Task 2: Rolling 90-Day Sharpe Ratio")

    RF_DAILY = 0.065 / 252

    # Select 5 key funds — top 5 by AUM (largest)
    top5 = [119552, 125497, 120504, 119094, 148567]
    top5 = [c for c in top5 if c in returns.columns]
    if len(top5) < 5:
        top5 = list(returns.columns[:5])

    fig, ax = plt.subplots(figsize=(14, 6))

    for i, code in enumerate(top5):
        r = returns[code].dropna()
        roll_mean = (r - RF_DAILY).rolling(90).mean()
        roll_std  = r.rolling(90).std()
        roll_sharpe = roll_mean / roll_std * np.sqrt(252)

        meta = fund_meta[fund_meta["amfi_code"]==code]
        name = meta["scheme_name"].values[0] if len(meta) else str(code)
        short = str(name).split(" - ")[0][:22]

        ax.plot(roll_sharpe.index, roll_sharpe,
                label=short, color=COLORS[i], linewidth=1.8)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.axhline(1, color="gray",  linewidth=0.8, linestyle=":",  alpha=0.5)
    ax.set_ylabel("Rolling Sharpe Ratio (90-day)")
    ax.set_title("Rolling 90-Day Sharpe Ratio — 5 Key Funds", fontsize=13)
    ax.legend(fontsize=9, ncol=2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=30)
    plt.tight_layout()
    out = CHARTS_DIR / "22_rolling_sharpe.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  ✅ Saved → 22_rolling_sharpe.png")

# ══════════════════════════════════════════════════════════
# TASK 3: Investor Cohort Analysis
# ══════════════════════════════════════════════════════════
def cohort_analysis(tx, fund_meta):
    section("Task 3: Investor Cohort Analysis")

    # Assign each investor to their first transaction year
    first_tx = tx.groupby("investor_id")["date"].min().dt.year.rename("cohort_year")
    tx_c = tx.join(first_tx, on="investor_id")

    # SIP cohort metrics
    sip = tx_c[tx_c["transaction_type"]=="SIP"]
    cohort = sip.groupby("cohort_year").agg(
        unique_investors = ("investor_id","nunique"),
        total_sip_txns   = ("amount_inr","count"),
        avg_sip_amount   = ("amount_inr","mean"),
        total_invested   = ("amount_inr","sum"),
        median_sip       = ("amount_inr","median"),
    ).round(2)
    cohort["avg_sip_amount"] = cohort["avg_sip_amount"].round(0)
    cohort["total_invested_cr"] = (cohort["total_invested"] / 1e7).round(2)

    print(f"\n  Cohort Summary:")
    print(cohort[["unique_investors","avg_sip_amount","total_invested_cr","median_sip"]].to_string())

    # Top fund preference per cohort
    top_fund = (tx_c[tx_c["transaction_type"]=="SIP"]
                .groupby(["cohort_year","amfi_code"])["amount_inr"]
                .sum().reset_index()
                .sort_values("amount_inr", ascending=False)
                .groupby("cohort_year").first()
                .reset_index())
    top_fund = top_fund.merge(fund_meta[["amfi_code","scheme_name"]], on="amfi_code", how="left")
    print(f"\n  Top Fund per Cohort:")
    print(top_fund[["cohort_year","scheme_name","amount_inr"]].to_string(index=False))

    # Chart
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    cohort_plot = cohort.reset_index()

    axes[0].bar(cohort_plot["cohort_year"].astype(str),
                cohort_plot["total_invested_cr"],
                color=["#1565C0","#E53935"], edgecolor="white", width=0.5)
    axes[0].set_title("Total SIP Investment by Cohort Year", fontsize=12, fontweight="bold")
    axes[0].set_ylabel("Total Invested (₹ Crore)")
    axes[0].set_xlabel("Cohort Year (First Transaction)")
    for i, v in enumerate(cohort_plot["total_invested_cr"]):
        axes[0].text(i, v+0.3, f"₹{v:.1f}Cr", ha="center", fontsize=10)

    axes[1].bar(cohort_plot["cohort_year"].astype(str),
                cohort_plot["avg_sip_amount"],
                color=["#2E7D32","#F9A825"], edgecolor="white", width=0.5)
    axes[1].set_title("Average SIP Amount by Cohort Year", fontsize=12, fontweight="bold")
    axes[1].set_ylabel("Avg SIP Amount (₹)")
    axes[1].set_xlabel("Cohort Year")
    for i, v in enumerate(cohort_plot["avg_sip_amount"]):
        axes[1].text(i, v+50, f"₹{v:,.0f}", ha="center", fontsize=10)

    plt.suptitle("Investor Cohort Analysis", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "24_cohort_analysis.png", dpi=150)
    plt.close()
    print(f"\n  ✅ Saved → 24_cohort_analysis.png")
    return cohort

# ══════════════════════════════════════════════════════════
# TASK 4: SIP Continuity Analysis
# ══════════════════════════════════════════════════════════
def sip_continuity(tx):
    section("Task 4: SIP Continuity Analysis")

    sip = tx[tx["transaction_type"]=="SIP"].sort_values(["investor_id","date"])

    # Only investors with 6+ SIP transactions
    sip_counts = sip.groupby("investor_id").size()
    eligible   = sip_counts[sip_counts >= 6].index
    sip_elig   = sip[sip["investor_id"].isin(eligible)]

    # Compute avg gap between SIP dates per investor
    gaps = (sip_elig.groupby("investor_id")["date"]
            .apply(lambda x: x.sort_values().diff().dt.days.mean())
            .dropna()
            .rename("avg_gap_days"))

    at_risk    = (gaps > 35).sum()
    consistent = (gaps <= 35).sum()
    total      = len(gaps)

    print(f"\n  Eligible investors (6+ SIPs): {total:,}")
    print(f"  Consistent (gap ≤ 35 days)  : {consistent:,} ({consistent/total*100:.1f}%)")
    print(f"  At-risk (gap > 35 days)      : {at_risk:,}  ({at_risk/total*100:.1f}%)")
    print(f"  Median gap                   : {gaps.median():.1f} days")
    print(f"  Mean gap                     : {gaps.mean():.1f} days")

    # Flag at-risk investors
    gap_df = gaps.reset_index()
    gap_df["status"] = gap_df["avg_gap_days"].apply(
        lambda x: "At-Risk" if x > 35 else "Consistent")

    # Chart — distribution of gaps
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(gaps[gaps <= 60], bins=30,
                 color="#1565C0", alpha=0.8, edgecolor="white")
    axes[0].axvline(35, color="#E53935", linewidth=2,
                    linestyle="--", label="At-risk threshold (35 days)")
    axes[0].set_xlabel("Average Gap Between SIPs (days)")
    axes[0].set_ylabel("Number of Investors")
    axes[0].set_title("SIP Gap Distribution", fontsize=12, fontweight="bold")
    axes[0].legend()

    status_counts = gap_df["status"].value_counts()
    axes[1].pie(status_counts, labels=status_counts.index,
                autopct="%1.1f%%",
                colors=["#2E7D32","#E53935"],
                startangle=90,
                wedgeprops=dict(edgecolor="white", linewidth=2))
    axes[1].set_title("SIP Continuity Status", fontsize=12, fontweight="bold")

    plt.suptitle("SIP Continuity Analysis", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "25_sip_continuity.png", dpi=150)
    plt.close()
    print(f"\n  ✅ Saved → 25_sip_continuity.png")
    return gap_df

# ══════════════════════════════════════════════════════════
# TASK 5: Fund Recommender
# ══════════════════════════════════════════════════════════
def fund_recommender(perf):
    section("Task 5: Fund Recommender System")

    RISK_MAP = {
        "Low"      : ["Low"],
        "Moderate" : ["Moderately High", "Moderate"],
        "High"     : ["High", "Very High"],
    }

    print("\n  Testing recommender for all 3 risk profiles:\n")
    for risk_input in ["Low", "Moderate", "High"]:
        matching_grades = RISK_MAP[risk_input]
        filtered = perf[perf["risk_grade"].isin(matching_grades)]
        top3 = (filtered
                .sort_values("sharpe_ratio", ascending=False)
                .head(3)[["scheme_name","sub_category","plan",
                           "sharpe_ratio","return_3yr_pct",
                           "expense_ratio_pct","risk_grade"]])
        print(f"  Risk Appetite: {risk_input}")
        print(f"  {'─'*55}")
        print(top3.to_string(index=False))
        print()

    return RISK_MAP

# ══════════════════════════════════════════════════════════
# TASK 6: Sector HHI Concentration
# ══════════════════════════════════════════════════════════
def sector_hhi(port, fund_meta):
    section("Task 6: Sector HHI Concentration")

    hhi_results = []
    for code in port["amfi_code"].unique():
        fund_port = port[port["amfi_code"]==code]
        weights   = fund_port["weight_pct"] / 100
        hhi       = (weights ** 2).sum()

        # Top sector
        top_sector = fund_port.nlargest(1,"weight_pct")["sector"].values[0]
        top_weight = fund_port["weight_pct"].max()

        meta = fund_meta[fund_meta["amfi_code"]==code]
        hhi_results.append({
            "amfi_code"  : code,
            "scheme_name": meta["scheme_name"].values[0] if len(meta) else str(code),
            "sub_category": meta["sub_category"].values[0] if len(meta) else "",
            "hhi"        : round(hhi, 4),
            "top_sector" : top_sector,
            "top_weight_pct": round(top_weight, 2),
            "n_holdings" : len(fund_port),
            "concentration": "High" if hhi > 0.15 else "Moderate" if hhi > 0.08 else "Low",
        })

    df = pd.DataFrame(hhi_results).sort_values("hhi", ascending=False)

    print(f"\n  Most Concentrated Funds (highest HHI):")
    print(df.head(5)[["scheme_name","hhi","top_sector","concentration"]].to_string(index=False))
    print(f"\n  Most Diversified Funds (lowest HHI):")
    print(df.tail(5)[["scheme_name","hhi","top_sector","concentration"]].to_string(index=False))

    # Chart
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    top10 = df.head(10)
    short_names = [str(n).split(" - ")[0][:22] for n in top10["scheme_name"]]
    bar_colors  = ["#E53935" if h > 0.15 else "#FF9800" if h > 0.08 else "#4CAF50"
                   for h in top10["hhi"]]
    axes[0].barh(short_names[::-1], top10["hhi"].values[::-1],
                 color=bar_colors[::-1], edgecolor="white")
    axes[0].axvline(0.15, color="#E53935", linestyle="--",
                    linewidth=1.5, label="High concentration (HHI>0.15)")
    axes[0].axvline(0.08, color="#FF9800", linestyle="--",
                    linewidth=1.5, label="Moderate (HHI>0.08)")
    axes[0].set_xlabel("HHI Score")
    axes[0].set_title("Top 10 Most Concentrated Funds", fontsize=12, fontweight="bold")
    axes[0].legend(fontsize=8)

    conc_counts = df["concentration"].value_counts()
    axes[1].pie(conc_counts, labels=conc_counts.index,
                autopct="%1.1f%%",
                colors=["#E53935","#FF9800","#4CAF50"],
                startangle=90,
                wedgeprops=dict(edgecolor="white", linewidth=2))
    axes[1].set_title("Portfolio Concentration Distribution", fontsize=12, fontweight="bold")

    plt.suptitle("Sector HHI Concentration Analysis", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "23_hhi_concentration.png", dpi=150)
    plt.close()
    print(f"\n  ✅ Saved → 23_hhi_concentration.png")
    return df

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def main():
    print("\n" + "🔬 " * 20)
    print("  BLUESTOCK FINTECH — DAY 6: ADVANCED ANALYTICS")
    print("🔬 " * 20)

    returns, tx, perf, port, fund_meta = load_data()

    var_df   = compute_var_cvar(returns, fund_meta)
    rolling_sharpe_chart(returns, fund_meta)
    cohort   = cohort_analysis(tx, fund_meta)
    gap_df   = sip_continuity(tx)
    risk_map = fund_recommender(perf)
    hhi_df   = sector_hhi(port, fund_meta)

    section("DAY 6 COMPLETE")
    charts = sorted(CHARTS_DIR.glob("2*.png"))
    print(f"\n  ✅ var_cvar_report.csv  — {len(var_df)} funds")
    print(f"  ✅ Charts generated     — {len(charts)} files")
    for c in sorted(CHARTS_DIR.glob("2[2-5]*.png")):
        print(f"     {c.name}")
    print()

if __name__ == "__main__":
    main()
