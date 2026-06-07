"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
Day 4: Performance Analytics & Risk Metrics
File   : performance_analytics.py
Author : Shahin Shafi
Date   : 2026-06
============================================================
Purpose:
  Compute from scratch using NAV data:
    1. Daily returns
    2. CAGR (1yr, 3yr, 5yr)
    3. Sharpe Ratio (Rf = 6.5%)
    4. Sortino Ratio
    5. Alpha & Beta (OLS regression vs benchmark)
    6. Maximum Drawdown
    7. Fund Scorecard (0-100 composite)
    8. Benchmark comparison + tracking error

Outputs:
    data/processed/fund_scorecard.csv
    data/processed/alpha_beta.csv
    reports/charts/16_benchmark_comparison.png
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
from scipy import stats

# ── Paths ──────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent
DB_PATH    = BASE_DIR / "bluestock_mf.db"
PROC_DIR   = BASE_DIR / "data" / "processed"
CHARTS_DIR = BASE_DIR / "reports" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
PROC_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ──────────────────────────────────────────────
RF_ANNUAL  = 0.065          # RBI repo rate proxy
RF_DAILY   = RF_ANNUAL / 252
TRADING_DAYS = 252

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ══════════════════════════════════════════════════════════
# LOAD DATA
# ══════════════════════════════════════════════════════════
def load_data():
    section("Loading Data from SQLite")
    conn = sqlite3.connect(DB_PATH)

    df_nav = pd.read_sql("""
        SELECT n.amfi_code, n.date_id, n.nav,
               f.scheme_name, f.sub_category, f.category,
               f.plan, f.expense_ratio_pct, f.fund_house,
               COALESCE(f.benchmark_key, 'NIFTY100') AS benchmark_key
        FROM fact_nav n
        JOIN dim_fund f ON n.amfi_code = f.amfi_code
    """, conn)
    df_nav["date"] = pd.to_datetime(df_nav["date_id"])
    df_nav = df_nav.sort_values(["amfi_code","date"]).reset_index(drop=True)

    df_bench = pd.read_sql(
        "SELECT date_id, index_name, close_value FROM benchmark_indices", conn)
    df_bench["date"] = pd.to_datetime(df_bench["date_id"])

    df_fund = pd.read_sql("SELECT * FROM dim_fund", conn)
    conn.close()

    print(f"  NAV rows     : {len(df_nav):,}")
    print(f"  Funds        : {df_nav['amfi_code'].nunique()}")
    print(f"  Date range   : {df_nav['date'].min().date()} → {df_nav['date'].max().date()}")
    print(f"  Benchmarks   : {df_bench['index_name'].unique().tolist()}")
    return df_nav, df_bench, df_fund

# ══════════════════════════════════════════════════════════
# STEP 1: DAILY RETURNS
# ══════════════════════════════════════════════════════════
def compute_daily_returns(df_nav):
    section("Step 1: Computing Daily Returns")

    nav_wide = df_nav.pivot_table(index="date", columns="amfi_code", values="nav")
    returns  = nav_wide.pct_change().dropna()

    print(f"  Returns matrix : {returns.shape[0]} days × {returns.shape[1]} funds")

    # Validation — distribution check
    all_returns = returns.values.flatten()
    all_returns = all_returns[~np.isnan(all_returns)]
    print(f"  Mean daily return : {all_returns.mean()*100:.4f}%")
    print(f"  Std daily return  : {all_returns.std()*100:.4f}%")
    print(f"  Min daily return  : {all_returns.min()*100:.2f}%")
    print(f"  Max daily return  : {all_returns.max()*100:.2f}%")

    # Sanity checks
    extreme = np.sum(np.abs(all_returns) > 0.20)
    print(f"  Returns > ±20%   : {extreme} (should be near 0 for diversified funds)")
    print(f"  ✅ Distribution looks reasonable")

    return nav_wide, returns

# ══════════════════════════════════════════════════════════
# STEP 2: CAGR
# ══════════════════════════════════════════════════════════
def compute_cagr(nav_wide):
    section("Step 2: Computing CAGR (1yr, 3yr, 5yr)")

    end_date   = nav_wide.index.max()
    date_1yr   = end_date - pd.DateOffset(years=1)
    date_3yr   = end_date - pd.DateOffset(years=3)
    date_5yr   = end_date - pd.DateOffset(years=5)

    def nearest_nav(target_date):
        """Get NAV row closest to target_date."""
        idx = nav_wide.index.get_indexer([target_date], method="nearest")[0]
        return nav_wide.iloc[idx]

    nav_end  = nav_wide.iloc[-1]
    nav_1yr  = nearest_nav(date_1yr)
    nav_3yr  = nearest_nav(date_3yr)
    nav_5yr  = nearest_nav(date_5yr)

    cagr_1yr = (nav_end / nav_1yr) ** (1/1) - 1
    cagr_3yr = (nav_end / nav_3yr) ** (1/3) - 1
    cagr_5yr = (nav_end / nav_5yr) ** (1/5) - 1

    cagr_df = pd.DataFrame({
        "amfi_code"    : nav_wide.columns,
        "cagr_1yr_pct" : (cagr_1yr.values * 100).round(2),
        "cagr_3yr_pct" : (cagr_3yr.values * 100).round(2),
        "cagr_5yr_pct" : (cagr_5yr.values * 100).round(2),
    })

    print(f"\n  CAGR Summary (top 5 by 3yr):")
    print(cagr_df.nlargest(5,"cagr_3yr_pct")[
        ["amfi_code","cagr_1yr_pct","cagr_3yr_pct","cagr_5yr_pct"]].to_string(index=False))
    return cagr_df

# ══════════════════════════════════════════════════════════
# STEP 3 & 4: SHARPE & SORTINO
# ══════════════════════════════════════════════════════════
def compute_sharpe_sortino(returns):
    section("Step 3 & 4: Sharpe & Sortino Ratios")
    results = []

    for code in returns.columns:
        r = returns[code].dropna()
        if len(r) < 50:
            continue

        excess      = r - RF_DAILY
        sharpe      = excess.mean() / r.std() * np.sqrt(TRADING_DAYS)

        downside    = r[r < RF_DAILY]
        if len(downside) > 1:
            sortino = excess.mean() / downside.std() * np.sqrt(TRADING_DAYS)
        else:
            sortino = np.nan

        results.append({
            "amfi_code"   : code,
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "ann_return_pct": round(r.mean() * TRADING_DAYS * 100, 2),
            "ann_vol_pct"   : round(r.std() * np.sqrt(TRADING_DAYS) * 100, 2),
        })

    df = pd.DataFrame(results)
    print(f"\n  Top 5 by Sharpe Ratio:")
    print(df.nlargest(5,"sharpe_ratio")[
        ["amfi_code","sharpe_ratio","sortino_ratio","ann_return_pct","ann_vol_pct"]
    ].to_string(index=False))
    return df

# ══════════════════════════════════════════════════════════
# STEP 5: ALPHA & BETA
# ══════════════════════════════════════════════════════════
def compute_alpha_beta(returns, df_bench, df_fund):
    section("Step 5: Alpha & Beta (OLS Regression)")

    # Build benchmark returns dict
    bench_returns = {}
    for idx_name in df_bench["index_name"].unique():
        b = (df_bench[df_bench["index_name"]==idx_name]
             .set_index("date")["close_value"]
             .sort_index()
             .pct_change()
             .dropna())
        bench_returns[idx_name] = b

    # Default benchmark for unmapped funds
    default_bench = bench_returns["NIFTY100"]

    results = []
    for code in returns.columns:
        fund_info   = df_fund[df_fund["amfi_code"]==code].iloc[0]
        bench_key   = fund_info.get("benchmark_key","NIFTY100")
        if pd.isna(bench_key):
            bench_key = "NIFTY100"

        bench_ret   = bench_returns.get(bench_key, default_bench)
        fund_ret    = returns[code].dropna()

        # Align on common dates
        aligned     = pd.concat([fund_ret, bench_ret], axis=1, join="inner").dropna()
        aligned.columns = ["fund","bench"]

        if len(aligned) < 50:
            continue

        slope, intercept, r_val, p_val, std_err = stats.linregress(
            aligned["bench"], aligned["fund"])

        alpha_ann = intercept * TRADING_DAYS * 100   # annualised %
        beta      = slope
        r_squared = r_val ** 2

        # Tracking error
        diff = aligned["fund"] - aligned["bench"]
        tracking_error = diff.std() * np.sqrt(TRADING_DAYS) * 100

        results.append({
            "amfi_code"      : code,
            "scheme_name"    : str(fund_info["scheme_name"]),
            "fund_house"     : str(fund_info["fund_house"]),
            "sub_category"   : str(fund_info["sub_category"]),
            "plan"           : str(fund_info["plan"]),
            "benchmark_used" : bench_key,
            "alpha_ann_pct"  : round(alpha_ann, 4),
            "beta"           : round(beta, 4),
            "r_squared"      : round(r_squared, 4),
            "tracking_error_pct": round(tracking_error, 4),
        })

    df = pd.DataFrame(results)
    print(f"\n  Top 5 by Alpha:")
    print(df.nlargest(5,"alpha_ann_pct")[
        ["scheme_name","alpha_ann_pct","beta","r_squared"]
    ].to_string(index=False))
    return df

# ══════════════════════════════════════════════════════════
# STEP 6: MAXIMUM DRAWDOWN
# ══════════════════════════════════════════════════════════
def compute_max_drawdown(nav_wide):
    section("Step 6: Maximum Drawdown")
    results = []

    for code in nav_wide.columns:
        nav   = nav_wide[code].dropna()
        peak  = nav.cummax()
        dd    = (nav / peak) - 1

        max_dd        = dd.min()
        max_dd_date   = dd.idxmin()
        # Find peak date before max drawdown
        peak_date     = nav[:max_dd_date].idxmax()
        # Find recovery date (first date after trough where NAV exceeds peak)
        nav_after     = nav[max_dd_date:]
        peak_val      = nav[peak_date]
        recovery      = nav_after[nav_after >= peak_val]
        recovery_date = recovery.index[0] if not recovery.empty else None

        results.append({
            "amfi_code"      : code,
            "max_drawdown_pct": round(max_dd * 100, 2),
            "drawdown_peak"  : peak_date.date(),
            "drawdown_trough": max_dd_date.date(),
            "recovery_date"  : recovery_date.date() if recovery_date else "Not recovered",
            "drawdown_days"  : (max_dd_date - peak_date).days,
        })

    df = pd.DataFrame(results)
    print(f"\n  Worst 5 Drawdowns:")
    print(df.nsmallest(5,"max_drawdown_pct")[
        ["amfi_code","max_drawdown_pct","drawdown_peak","drawdown_trough","drawdown_days"]
    ].to_string(index=False))
    return df

# ══════════════════════════════════════════════════════════
# STEP 7: FUND SCORECARD
# ══════════════════════════════════════════════════════════
def compute_scorecard(cagr_df, sharpe_df, alpha_df, drawdown_df, df_fund):
    section("Step 7: Fund Scorecard (0-100 Composite)")

    # Merge all metrics
    sc = (cagr_df
          .merge(sharpe_df[["amfi_code","sharpe_ratio","ann_return_pct","ann_vol_pct"]], on="amfi_code")
          .merge(alpha_df[["amfi_code","alpha_ann_pct","beta","tracking_error_pct"]], on="amfi_code")
          .merge(drawdown_df[["amfi_code","max_drawdown_pct"]], on="amfi_code")
          .merge(df_fund[["amfi_code","scheme_name","fund_house","sub_category",
                           "plan","expense_ratio_pct","category"]], on="amfi_code"))

    # ── Ranking (higher rank = better) ──────────────────
    # 3yr return: higher is better
    sc["rank_3yr"]     = sc["cagr_3yr_pct"].rank(ascending=True)
    # Sharpe: higher is better
    sc["rank_sharpe"]  = sc["sharpe_ratio"].rank(ascending=True)
    # Alpha: higher is better
    sc["rank_alpha"]   = sc["alpha_ann_pct"].rank(ascending=True)
    # Expense ratio: LOWER is better → inverse rank
    sc["rank_expense"] = sc["expense_ratio_pct"].rank(ascending=False)
    # Max drawdown: LESS negative is better → inverse rank
    sc["rank_maxdd"]   = sc["max_drawdown_pct"].rank(ascending=False)

    n = len(sc)

    # ── Composite score: normalize each rank to 0-100 ───
    sc["score_3yr"]     = (sc["rank_3yr"]     / n) * 100
    sc["score_sharpe"]  = (sc["rank_sharpe"]  / n) * 100
    sc["score_alpha"]   = (sc["rank_alpha"]   / n) * 100
    sc["score_expense"] = (sc["rank_expense"] / n) * 100
    sc["score_maxdd"]   = (sc["rank_maxdd"]   / n) * 100

    # ── Weighted composite ───────────────────────────────
    sc["composite_score"] = (
        0.30 * sc["score_3yr"]     +
        0.25 * sc["score_sharpe"]  +
        0.20 * sc["score_alpha"]   +
        0.15 * sc["score_expense"] +
        0.10 * sc["score_maxdd"]
    ).round(2)

    sc = sc.sort_values("composite_score", ascending=False).reset_index(drop=True)
    sc.index = sc.index + 1   # rank from 1
    sc.index.name = "overall_rank"

    print(f"\n  Top 10 Funds by Composite Score:")
    print(sc[["scheme_name","composite_score","cagr_3yr_pct",
              "sharpe_ratio","alpha_ann_pct","expense_ratio_pct"]
             ].head(10).to_string())

    return sc

# ══════════════════════════════════════════════════════════
# STEP 8: BENCHMARK COMPARISON CHART
# ══════════════════════════════════════════════════════════
def benchmark_comparison_chart(nav_wide, returns, df_bench, scorecard):
    section("Step 8: Benchmark Comparison Chart")

    sns.set_theme(style="whitegrid", font_scale=1.1)
    plt.rcParams["figure.dpi"] = 120

    # Top 5 funds by composite score (Direct plans only)
    direct_mask = scorecard["plan"] == "Direct"
    top5_codes  = scorecard[direct_mask].head(5)["amfi_code"].tolist()

    # 3-year window
    end_date   = nav_wide.index.max()
    start_date = end_date - pd.DateOffset(years=3)
    window     = nav_wide.index >= start_date

    fig, axes = plt.subplots(2, 1, figsize=(14, 12))

    # ── Panel 1: Indexed NAV comparison ─────────────────
    ax = axes[0]
    COLORS = ["#1565C0","#E53935","#2E7D32","#6A1B9A","#E65100","#795548","#546E7A"]

    for i, code in enumerate(top5_codes):
        series = nav_wide.loc[window, code].dropna()
        idx    = series / series.iloc[0] * 100
        name   = scorecard[scorecard["amfi_code"]==code]["scheme_name"].values[0]
        short  = str(name).split(" - ")[0][:22]
        ax.plot(series.index, idx, linewidth=2,
                label=short, color=COLORS[i])

    # NIFTY50 benchmark
    n50 = (df_bench[df_bench["index_name"]=="NIFTY50"]
           .set_index("date")["close_value"].sort_index())
    n50_window = n50[n50.index >= start_date]
    n50_idx    = n50_window / n50_window.iloc[0] * 100
    ax.plot(n50_idx.index, n50_idx, linewidth=2, linestyle="--",
            color="black", label="NIFTY50", alpha=0.8)

    # NIFTY100 benchmark
    n100 = (df_bench[df_bench["index_name"]=="NIFTY100"]
            .set_index("date")["close_value"].sort_index())
    n100_window = n100[n100.index >= start_date]
    n100_idx    = n100_window / n100_window.iloc[0] * 100
    ax.plot(n100_idx.index, n100_idx, linewidth=2, linestyle=":",
            color="gray", label="NIFTY100", alpha=0.8)

    ax.set_title("Top 5 Funds vs NIFTY50 & NIFTY100 (3-Year, Indexed to 100)",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("Indexed Value (Base=100)")
    ax.legend(fontsize=9, ncol=2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30)

    # ── Panel 2: Tracking Error bar chart ────────────────
    ax2 = axes[1]
    te_data = []

    n100_ret = n100.pct_change().dropna()
    n50_ret  = n50.pct_change().dropna()

    for code in top5_codes:
        fund_ret   = returns[code].dropna()
        fund_ret_3 = fund_ret[fund_ret.index >= start_date]

        # vs NIFTY100
        aligned100 = pd.concat([fund_ret_3, n100_ret], axis=1, join="inner").dropna()
        te100 = (aligned100.iloc[:,0] - aligned100.iloc[:,1]).std() * np.sqrt(252) * 100

        # vs NIFTY50
        aligned50  = pd.concat([fund_ret_3, n50_ret],  axis=1, join="inner").dropna()
        te50  = (aligned50.iloc[:,0]  - aligned50.iloc[:,1]).std()  * np.sqrt(252) * 100

        name  = scorecard[scorecard["amfi_code"]==code]["scheme_name"].values[0]
        short = str(name).split(" - ")[0][:22]
        te_data.append({"Fund": short, "vs NIFTY100": round(te100,2), "vs NIFTY50": round(te50,2)})

    te_df = pd.DataFrame(te_data)
    x     = np.arange(len(te_df))
    w     = 0.35
    ax2.bar(x - w/2, te_df["vs NIFTY100"], w, label="vs NIFTY100",
            color="#1565C0", alpha=0.85)
    ax2.bar(x + w/2, te_df["vs NIFTY50"],  w, label="vs NIFTY50",
            color="#E53935", alpha=0.85)
    for i, row in te_df.iterrows():
        ax2.text(i-w/2, row["vs NIFTY100"]+0.1, f"{row['vs NIFTY100']:.1f}%",
                 ha="center", fontsize=8)
        ax2.text(i+w/2, row["vs NIFTY50"]+0.1,  f"{row['vs NIFTY50']:.1f}%",
                 ha="center", fontsize=8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(te_df["Fund"], rotation=20, ha="right", fontsize=9)
    ax2.set_ylabel("Tracking Error (% Annualised)")
    ax2.set_title("Tracking Error vs Benchmarks — Top 5 Funds (3-Year)",
                  fontsize=13, fontweight="bold")
    ax2.legend()

    plt.suptitle("Benchmark Comparison Analysis", fontsize=15,
                 fontweight="bold", y=1.01)
    plt.tight_layout()
    out = CHARTS_DIR / "16_benchmark_comparison.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✅ Saved → {out.name}")

    # Print tracking error table
    print(f"\n  Tracking Error Summary:")
    print(te_df.to_string(index=False))

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def main():
    print("\n" + "📈 " * 20)
    print("  BLUESTOCK FINTECH — DAY 4: PERFORMANCE ANALYTICS")
    print("📈 " * 20)

    df_nav, df_bench, df_fund = load_data()

    nav_wide, returns = compute_daily_returns(df_nav)
    cagr_df           = compute_cagr(nav_wide)
    sharpe_df         = compute_sharpe_sortino(returns)
    alpha_df          = compute_alpha_beta(returns, df_bench, df_fund)
    drawdown_df       = compute_max_drawdown(nav_wide)
    scorecard         = compute_scorecard(cagr_df, sharpe_df, alpha_df, drawdown_df, df_fund)
    benchmark_comparison_chart(nav_wide, returns, df_bench, scorecard)

    # ── Save CSVs ────────────────────────────────────────
    section("Saving Output Files")

    scorecard_out = PROC_DIR / "fund_scorecard.csv"
    scorecard.reset_index().to_csv(scorecard_out, index=False)
    print(f"  💾 fund_scorecard.csv  ({len(scorecard)} rows)")

    alpha_out = PROC_DIR / "alpha_beta.csv"
    alpha_df.to_csv(alpha_out, index=False)
    print(f"  💾 alpha_beta.csv      ({len(alpha_df)} rows)")

    cagr_out = PROC_DIR / "cagr_metrics.csv"
    cagr_df.to_csv(cagr_out, index=False)
    print(f"  💾 cagr_metrics.csv    ({len(cagr_df)} rows)")

    section("DAY 4 COMPLETE")
    print("  ✅ fund_scorecard.csv    → data/processed/")
    print("  ✅ alpha_beta.csv        → data/processed/")
    print("  ✅ cagr_metrics.csv      → data/processed/")
    print("  ✅ 16_benchmark_comparison.png → reports/charts/")
    print("\n  Next step: open Performance_Analytics.ipynb\n")

if __name__ == "__main__":
    main()
