# Data Dictionary — Mutual Fund Analytics Platform
**Bluestock Fintech | Day 2 Deliverable**
Last updated: June 2026

---

## Table of Contents
1. [dim_fund](#1-dim_fund)
2. [dim_date](#2-dim_date)
3. [fact_nav](#3-fact_nav)
4. [fact_transactions](#4-fact_transactions)
5. [fact_performance](#5-fact_performance)
6. [fact_portfolio](#6-fact_portfolio)
7. [fact_aum](#7-fact_aum)
8. [fact_sip_industry](#8-fact_sip_industry)
9. [fact_category_inflows](#9-fact_category_inflows)
10. [fact_folio_count](#10-fact_folio_count)
11. [benchmark_indices](#11-benchmark_indices)

---

## 1. dim_fund
**Source:** `01_fund_master.csv` | **Rows:** 40 | **Type:** Dimension

One row per mutual fund scheme. Primary key for all fund-level fact tables.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| amfi_code | INTEGER (PK) | Unique 6-digit scheme code assigned by AMFI | 119551 |
| fund_house | TEXT | Name of the Asset Management Company (AMC) | SBI Mutual Fund |
| scheme_name | TEXT | Full official scheme name | SBI Bluechip Fund - Regular Plan |
| category | TEXT | Broad SEBI category: Equity or Debt | Equity |
| sub_category | TEXT | Specific sub-category per SEBI classification | Large Cap |
| plan | TEXT | Regular (distributor) or Direct (investor buys directly) | Regular |
| launch_date | DATE | Date the scheme was launched | 2006-02-14 |
| benchmark | TEXT | Original benchmark name from AMFI | NIFTY 100 TRI |
| benchmark_key | TEXT | Normalised benchmark name matching benchmark_indices table | NIFTY100 |
| expense_ratio_pct | REAL | Annual fee charged by AMC as % of AUM | 1.54 |
| exit_load_pct | REAL | Penalty fee for early redemption (%) | 1.0 |
| min_sip_amount | INTEGER | Minimum monthly SIP amount in INR | 500 |
| min_lumpsum_amount | INTEGER | Minimum one-time investment in INR | 1000 |
| fund_manager | TEXT | Name of the portfolio manager | Sohini Andani |
| risk_category | TEXT | SEBI risk label: Low / Moderate / High / Very High | Moderate |
| sebi_category_code | TEXT | SEBI internal classification code | EC01 |

---

## 2. dim_date
**Source:** Generated programmatically | **Rows:** ~1,827 | **Type:** Dimension

Full calendar date dimension from 2022-01-01 to 2026-12-31. Used as FK in all fact tables.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| date_id | TEXT (PK) | Date in YYYY-MM-DD format | 2024-04-01 |
| year | INTEGER | Calendar year | 2024 |
| quarter | INTEGER | Calendar quarter (1–4) | 1 |
| month | INTEGER | Month number (1–12) | 4 |
| month_name | TEXT | Full month name | April |
| week_of_year | INTEGER | ISO week number (1–53) | 14 |
| day_of_week | INTEGER | 0=Monday, 6=Sunday | 0 |
| is_weekend | INTEGER | 1 if Saturday/Sunday, else 0 | 0 |
| fy_year | TEXT | Indian Financial Year (Apr–Mar) | FY2024-25 |
| fy_quarter | TEXT | Financial year quarter label | Q1 FY24-25 |

---

## 3. fact_nav
**Source:** `02_nav_history.csv` | **Rows:** ~66,000 (after ffill) | **Type:** Fact

Daily Net Asset Value for each fund. Missing dates (weekends/holidays) are forward-filled with the last known NAV.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| nav_id | INTEGER (PK) | Auto-incremented surrogate key | 1 |
| amfi_code | INTEGER (FK) | Links to dim_fund | 119551 |
| date_id | TEXT (FK) | Links to dim_date | 2024-04-01 |
| nav | REAL | Net Asset Value in INR per unit | 54.3856 |

**Business Rules:**
- NAV is always > 0
- Forward-filled for non-trading days using last available value
- Used to compute daily returns: `(NAV_t / NAV_t-1) - 1`

---

## 4. fact_transactions
**Source:** `08_investor_transactions.csv` | **Rows:** ~32,778 | **Type:** Fact

Simulated investor-level transactions from Jan 2024 to May 2025.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| tx_id | INTEGER (PK) | Auto-incremented surrogate key | 1 |
| investor_id | TEXT | Unique investor identifier | INV003054 |
| transaction_date | TEXT (FK) | Date of transaction, links to dim_date | 2024-01-01 |
| amfi_code | INTEGER (FK) | Fund invested in, links to dim_fund | 119092 |
| transaction_type | TEXT | SIP / Lumpsum / Redemption | SIP |
| amount_inr | INTEGER | Transaction amount in Indian Rupees | 1834 |
| state | TEXT | Indian state of the investor | Telangana |
| city | TEXT | City of the investor | Hyderabad |
| city_tier | TEXT | T30 (top 30 cities) or B30 (beyond top 30) | T30 |
| age_group | TEXT | Investor age bracket | 36-45 |
| gender | TEXT | Male / Female | Female |
| annual_income_lakh | REAL | Annual income in lakhs INR | 77.1 |
| payment_mode | TEXT | UPI / Cheque / Mandate / NetBanking | UPI |
| kyc_status | TEXT | KYC verification: Verified / Pending | Verified |

---

## 5. fact_performance
**Source:** `07_scheme_performance.csv` | **Rows:** 40 | **Type:** Fact

Pre-computed and validated risk/return metrics for all schemes.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| perf_id | INTEGER (PK) | Auto-incremented surrogate key | 1 |
| amfi_code | INTEGER (FK) | Links to dim_fund | 119551 |
| return_1yr_pct | REAL | 1-year absolute return (%) | 12.42 |
| return_3yr_pct | REAL | 3-year CAGR return (%) | 12.36 |
| return_5yr_pct | REAL | 5-year CAGR return (%) | 14.45 |
| benchmark_3yr_pct | REAL | Benchmark 3-year CAGR for comparison | 11.49 |
| alpha | REAL | Excess return over benchmark (Jensen's Alpha) | 0.87 |
| beta | REAL | Sensitivity to market movements (1 = market) | 0.89 |
| sharpe_ratio | REAL | Risk-adjusted return: (Rp - Rf) / StdDev, annualised | 0.88 |
| sortino_ratio | REAL | Like Sharpe but only penalises downside volatility | 1.29 |
| std_dev_ann_pct | REAL | Annualised standard deviation of daily returns (%) | 14.0 |
| max_drawdown_pct | REAL | Largest peak-to-trough decline (negative value) | -21.70 |
| aum_crore | INTEGER | Assets Under Management in crores INR | 14288 |
| expense_ratio_pct | REAL | Annual expense ratio (%) | 1.54 |
| morningstar_rating | INTEGER | Star rating 1–5 (5 = best) | 4 |
| risk_grade | TEXT | Qualitative risk label | Moderate |

**Note:** Liquid fund Sharpe ratios > 5 are expected due to near-zero volatility and steady positive returns.

---

## 6. fact_portfolio
**Source:** `09_portfolio_holdings.csv` | **Rows:** 322 | **Type:** Fact

Top equity stock holdings per fund as of December 2025.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| holding_id | INTEGER (PK) | Auto-incremented surrogate key | 1 |
| amfi_code | INTEGER (FK) | Links to dim_fund | 119551 |
| stock_symbol | TEXT | NSE/BSE ticker symbol | HDFCBANK |
| stock_name | TEXT | Full company name | HDFC Bank Ltd |
| sector | TEXT | Business sector of the stock | Banking |
| weight_pct | REAL | Portfolio allocation as % of fund AUM | 11.19 |
| market_value_cr | REAL | Market value of holding in crores INR | 88.97 |
| current_price_inr | REAL | Current stock price in INR | 1074.65 |
| portfolio_date | TEXT | Date of portfolio snapshot | 2025-12-31 |

---

## 7. fact_aum
**Source:** `03_aum_by_fund_house.csv` | **Rows:** 90 | **Type:** Fact

Quarterly AUM snapshots at the AMC (fund house) level.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| aum_id | INTEGER (PK) | Auto-incremented surrogate key | 1 |
| date_id | TEXT (FK) | Quarter-end date, links to dim_date | 2022-03-31 |
| fund_house | TEXT | Name of AMC | SBI Mutual Fund |
| aum_lakh_crore | REAL | AUM in lakh crores (1 lakh crore = 10^11 INR) | 6.05 |
| aum_crore | INTEGER | AUM in crores INR | 605000 |
| num_schemes | INTEGER | Number of active schemes managed | 186 |

---

## 8. fact_sip_industry
**Source:** `04_monthly_sip_inflows.csv` | **Rows:** 48 | **Type:** Fact

Industry-wide monthly SIP (Systematic Investment Plan) data.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| sip_id | INTEGER (PK) | Auto-incremented surrogate key | 1 |
| month_id | TEXT (FK) | First day of month, links to dim_date | 2022-01-01 |
| sip_inflow_crore | INTEGER | Total SIP collections in crores INR | 11517 |
| active_sip_accounts_crore | REAL | Number of active SIP accounts (in crores) | 4.91 |
| new_sip_accounts_lakh | REAL | New SIP registrations that month (in lakhs) | 9.1 |
| sip_aum_lakh_crore | REAL | Total SIP AUM in lakh crores | 4.80 |
| yoy_growth_pct | REAL | Year-on-year growth in SIP inflows (%) | 28.4 |

---

## 9. fact_category_inflows
**Source:** `05_category_inflows.csv` | **Rows:** 144 | **Type:** Fact

Monthly net inflows by SEBI fund category for FY2024-25.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| cat_id | INTEGER (PK) | Auto-incremented surrogate key | 1 |
| month_id | TEXT (FK) | First day of month, links to dim_date | 2024-04-01 |
| category | TEXT | SEBI fund category name | Large Cap |
| net_inflow_crore | REAL | Net inflow (inflow minus redemption) in crores | 2413.0 |

---

## 10. fact_folio_count
**Source:** `06_industry_folio_count.csv` | **Rows:** 21 | **Type:** Fact

Quarterly industry-wide folio (investor account) counts.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| folio_id | INTEGER (PK) | Auto-incremented surrogate key | 1 |
| month_id | TEXT (FK) | Quarter start date, links to dim_date | 2022-01-01 |
| total_folios_crore | REAL | Total folios across all categories (in crores) | 13.26 |
| equity_folios_crore | REAL | Equity fund folios (in crores) | 9.28 |
| debt_folios_crore | REAL | Debt fund folios (in crores) | 1.86 |
| hybrid_folios_crore | REAL | Hybrid fund folios (in crores) | 0.80 |
| others_folios_crore | REAL | Other category folios (in crores) | 1.33 |

---

## 11. benchmark_indices
**Source:** `10_benchmark_indices.csv` | **Rows:** 8,050 | **Type:** Reference

Daily closing values for 7 Indian market benchmark indices.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| bench_id | INTEGER (PK) | Auto-incremented surrogate key | 1 |
| date_id | TEXT (FK) | Trading date, links to dim_date | 2022-01-03 |
| index_name | TEXT | Index identifier | NIFTY50 |
| close_value | REAL | Closing index value | 17492.79 |

**Available indices:**

| index_name | Full Name | Used By |
|---|---|---|
| NIFTY50 | Nifty 50 TRI | Large Cap funds |
| NIFTY100 | Nifty 100 TRI | Large Cap funds |
| NIFTY_MIDCAP150 | Nifty Midcap 150 TRI | Mid Cap funds |
| BSE_SMALLCAP | BSE 250 SmallCap TRI | Small Cap funds |
| NIFTY500 | Nifty 500 TRI | Flexi Cap / Multi Cap |
| CRISIL_LIQUID | CRISIL Liquid Fund Index | Liquid / Money Market |
| CRISIL_GILT | CRISIL Gilt Index | Gilt / Long Duration |

---

## Key Business Definitions

| Term | Definition |
|---|---|
| NAV | Net Asset Value — price of one unit of a mutual fund |
| AUM | Assets Under Management — total market value of a fund |
| SIP | Systematic Investment Plan — fixed monthly investment |
| CAGR | Compound Annual Growth Rate — annualised return |
| Alpha | Return generated above the benchmark (positive = outperforming) |
| Beta | Market sensitivity (Beta=1 moves with market, <1 less volatile) |
| Sharpe Ratio | Return per unit of total risk: (Rp - Rf) / StdDev × √252 |
| Sortino Ratio | Like Sharpe but only penalises downside (bad) volatility |
| Max Drawdown | Worst peak-to-trough portfolio decline during a period |
| Folio | An investor's account with a particular mutual fund |
| T30/B30 | Top 30 / Beyond Top 30 cities — SEBI geographic classification |
| TRI | Total Return Index — benchmark including dividends reinvested |
| Direct Plan | Fund bought directly without distributor (lower expense ratio) |
| Regular Plan | Fund bought through distributor (higher expense ratio) |
