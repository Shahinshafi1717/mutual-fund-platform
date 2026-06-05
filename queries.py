"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
Day 2: Analytical SQL Queries
File   : queries.py
Author : Shahin Shafi
Date   : 2026-06
============================================================
Purpose:
  Run 10 analytical queries against bluestock_mf.db and
  print formatted results. Run AFTER db_load.py.
============================================================
"""

from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).resolve().parent
DB_PATH  = BASE_DIR / "bluestock_mf.db"
engine   = create_engine(f"sqlite:///{DB_PATH}", echo=False)

def run_query(title, sql, query_num):
    print(f"\n{'='*60}")
    print(f"  Q{query_num}: {title}")
    print(f"{'='*60}")
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)
    print(df.to_string(index=False))
    return df

# ──────────────────────────────────────────────────────────
# Q1: Top 5 Fund Houses by Latest AUM
# ──────────────────────────────────────────────────────────
Q1 = """
SELECT
    fund_house,
    aum_crore,
    aum_lakh_crore,
    num_schemes,
    ROUND(100.0 * aum_crore / SUM(aum_crore) OVER(), 2) AS market_share_pct
FROM fact_aum
WHERE date_id = (SELECT MAX(date_id) FROM fact_aum)
ORDER BY aum_crore DESC
LIMIT 5;
"""

# ──────────────────────────────────────────────────────────
# Q2: Average Monthly NAV per Fund (last 12 months)
# ──────────────────────────────────────────────────────────
Q2 = """
SELECT
    f.scheme_name,
    f.category,
    d.year,
    d.month_name,
    ROUND(AVG(n.nav), 4) AS avg_nav
FROM fact_nav n
JOIN dim_fund f ON n.amfi_code = f.amfi_code
JOIN dim_date d ON n.date_id  = d.date_id
WHERE n.date_id >= DATE('now', '-12 months')
  AND f.plan = 'Direct'
GROUP BY f.scheme_name, d.year, d.month
ORDER BY f.scheme_name, n.date_id
LIMIT 24;
"""

# ──────────────────────────────────────────────────────────
# Q3: SIP YoY Growth Trend (all 48 months)
# ──────────────────────────────────────────────────────────
Q3 = """
SELECT
    month_id,
    sip_inflow_crore,
    active_sip_accounts_crore,
    new_sip_accounts_lakh,
    ROUND(yoy_growth_pct, 2) AS yoy_growth_pct
FROM fact_sip_industry
ORDER BY month_id
LIMIT 12;
"""

# ──────────────────────────────────────────────────────────
# Q4: Total Transaction Amount by State (Top 10)
# ──────────────────────────────────────────────────────────
Q4 = """
SELECT
    state,
    COUNT(*)                            AS num_transactions,
    SUM(amount_inr)                     AS total_amount_inr,
    ROUND(AVG(amount_inr), 0)           AS avg_amount_inr,
    COUNT(DISTINCT investor_id)         AS unique_investors
FROM fact_transactions
GROUP BY state
ORDER BY total_amount_inr DESC
LIMIT 10;
"""

# ──────────────────────────────────────────────────────────
# Q5: Funds with Expense Ratio Below 1% (low-cost funds)
# ──────────────────────────────────────────────────────────
Q5 = """
SELECT
    f.scheme_name,
    f.fund_house,
    f.category,
    f.plan,
    f.expense_ratio_pct,
    p.return_3yr_pct,
    p.sharpe_ratio
FROM dim_fund f
JOIN fact_performance p ON f.amfi_code = p.amfi_code
WHERE f.expense_ratio_pct < 1.0
ORDER BY f.expense_ratio_pct ASC;
"""

# ──────────────────────────────────────────────────────────
# Q6: Top 5 Funds by 3-Year Return (Direct Plans only)
# ──────────────────────────────────────────────────────────
Q6 = """
SELECT
    f.scheme_name,
    f.fund_house,
    f.sub_category,
    p.return_3yr_pct,
    p.return_1yr_pct,
    p.alpha,
    p.sharpe_ratio,
    p.morningstar_rating
FROM fact_performance p
JOIN dim_fund f ON p.amfi_code = f.amfi_code
WHERE f.plan = 'Direct'
ORDER BY p.return_3yr_pct DESC
LIMIT 5;
"""

# ──────────────────────────────────────────────────────────
# Q7: SIP vs Lumpsum vs Redemption — Monthly Flow Analysis
# ──────────────────────────────────────────────────────────
Q7 = """
SELECT
    d.year,
    d.month_name,
    t.transaction_type,
    COUNT(*)                AS num_transactions,
    SUM(t.amount_inr)       AS total_amount_inr
FROM fact_transactions t
JOIN dim_date d ON t.transaction_date = d.date_id
GROUP BY d.year, d.month, t.transaction_type
ORDER BY d.year, d.month, t.transaction_type
LIMIT 18;
"""

# ──────────────────────────────────────────────────────────
# Q8: Sector Concentration — Top Sectors by Portfolio Weight
# ──────────────────────────────────────────────────────────
Q8 = """
SELECT
    sector,
    COUNT(DISTINCT amfi_code)           AS num_funds_holding,
    ROUND(AVG(weight_pct), 2)           AS avg_weight_pct,
    ROUND(SUM(market_value_cr), 2)      AS total_market_value_cr
FROM fact_portfolio
GROUP BY sector
ORDER BY total_market_value_cr DESC;
"""

# ──────────────────────────────────────────────────────────
# Q9: Investor Demographics — Age Group vs Avg Investment
# ──────────────────────────────────────────────────────────
Q9 = """
SELECT
    age_group,
    gender,
    COUNT(*)                            AS num_transactions,
    ROUND(AVG(amount_inr), 0)           AS avg_amount_inr,
    ROUND(SUM(amount_inr)/1e7, 2)       AS total_amount_crore
FROM fact_transactions
WHERE transaction_type IN ('SIP','Lumpsum')
GROUP BY age_group, gender
ORDER BY age_group, gender;
"""

# ──────────────────────────────────────────────────────────
# Q10: Category Net Inflow Trend — Top 3 Categories
# ──────────────────────────────────────────────────────────
Q10 = """
SELECT
    ci.category,
    ci.month_id,
    ROUND(ci.net_inflow_crore, 2)       AS net_inflow_crore
FROM fact_category_inflows ci
WHERE ci.category IN (
    SELECT category
    FROM fact_category_inflows
    GROUP BY category
    ORDER BY SUM(net_inflow_crore) DESC
    LIMIT 3
)
ORDER BY ci.category, ci.month_id;
"""

# ──────────────────────────────────────────────────────────
# MAIN — Run all 10 queries
# ──────────────────────────────────────────────────────────
def main():
    print("\n" + "📊 " * 20)
    print("  BLUESTOCK FINTECH — DAY 2: ANALYTICAL QUERIES")
    print("📊 " * 20)

    run_query("Top 5 Fund Houses by Latest AUM",              Q1,  1)
    run_query("Average Monthly NAV — Direct Funds (12 mo)",   Q2,  2)
    run_query("SIP Industry Trend (first 12 months shown)",   Q3,  3)
    run_query("Transaction Volume by State (Top 10)",         Q4,  4)
    run_query("Low-Cost Funds — Expense Ratio < 1%",          Q5,  5)
    run_query("Top 5 Funds by 3-Year Return (Direct)",        Q6,  6)
    run_query("SIP vs Lumpsum vs Redemption Monthly Flow",    Q7,  7)
    run_query("Sector Concentration in Portfolios",           Q8,  8)
    run_query("Investor Demographics — Age & Gender",         Q9,  9)
    run_query("Top 3 Categories — Monthly Net Inflow",        Q10, 10)

    print(f"\n{'='*60}")
    print("  ✅ All 10 queries complete!")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
