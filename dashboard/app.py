"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
Day 5: Interactive Streamlit Dashboard
File   : dashboard/app.py
Author : Shahin Shafi
Date   : 2026-06
============================================================
Pages:
  1. Industry Overview  — AUM, SIP trends, folio growth
  2. Fund Performance   — Returns, Sharpe, Alpha, Scorecard
  3. NAV Analysis       — NAV trends, drawdown, correlation
  4. Investor Insights  — Demographics, geography, transactions
============================================================
Run with: streamlit run dashboard/app.py
============================================================
"""

import warnings

from narwhals import corr; warnings.filterwarnings("ignore")
from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ── Page config ────────────────────────────────────────────
st.set_page_config(
    page_title="Bluestock MF Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── DB Path ────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / "bluestock_mf.db"
if not DB_PATH.exists():
    DB_PATH = BASE_DIR / "data" / "db" / "bluestock_mf.db"

# ── Custom CSS ─────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 2rem; font-weight: 700;
        color: #1565C0; margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.95rem; color: #666; margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #f0f4ff; border-radius: 10px;
        padding: 1rem; text-align: center;
        border-left: 4px solid #1565C0;
    }
    .metric-value {
        font-size: 1.6rem; font-weight: 700; color: #1565C0;
    }
    .metric-label {
        font-size: 0.8rem; color: #555; margin-top: 0.2rem;
    }
    .stSelectbox label { font-weight: 600; }
    .stMultiSelect label { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

COLORS = ["#1565C0","#E53935","#2E7D32","#6A1B9A",
          "#E65100","#00838F","#F9A825","#4527A0",
          "#558B2F","#AD1457"]

# ══════════════════════════════════════════════════════════
# DATA LOADER — cached so DB is only read once
# ══════════════════════════════════════════════════════════
@st.cache_data
def load_all_data():
    conn = sqlite3.connect(DB_PATH)

    nav = pd.read_sql("""
        SELECT n.amfi_code, n.date_id, n.nav,
               f.scheme_name, f.sub_category, f.category,
               f.fund_house, f.plan, f.risk_category
        FROM fact_nav n JOIN dim_fund f ON n.amfi_code=f.amfi_code
    """, conn)
    nav["date"] = pd.to_datetime(nav["date_id"])

    perf = pd.read_sql("""
    SELECT p.amfi_code, p.scheme_name, p.category,
           p.return_1yr_pct, p.return_3yr_pct, p.return_5yr_pct,
           p.benchmark_3yr_pct, p.alpha, p.beta,
           p.sharpe_ratio, p.sortino_ratio, p.std_dev_ann_pct,
           p.max_drawdown_pct, p.aum_crore, p.expense_ratio_pct,
           p.morningstar_rating, p.risk_grade,
           f.fund_house, f.sub_category as sub_cat,
           f.plan, f.risk_category
    FROM fact_performance p JOIN dim_fund f ON p.amfi_code=f.amfi_code
""", conn)

    aum = pd.read_sql("SELECT * FROM fact_aum", conn)
    aum["date"] = pd.to_datetime(aum["date_id"])
    aum["year"] = aum["date"].dt.year

    sip = pd.read_sql("SELECT * FROM fact_sip_industry ORDER BY month_id", conn)
    sip["date"] = pd.to_datetime(sip["month_id"])

    tx = pd.read_sql("SELECT * FROM fact_transactions", conn)
    tx["date"] = pd.to_datetime(tx["transaction_date"])

    folio = pd.read_sql("SELECT * FROM fact_folio_count ORDER BY month_id", conn)
    folio["date"] = pd.to_datetime(folio["month_id"])

    port = pd.read_sql("""
        SELECT p.*, f.category, f.fund_house, f.scheme_name as fund_name
        FROM fact_portfolio p JOIN dim_fund f ON p.amfi_code=f.amfi_code
    """, conn)

    cat = pd.read_sql("SELECT * FROM fact_category_inflows", conn)
    cat["date"] = pd.to_datetime(cat["month_id"])

    fund = pd.read_sql("SELECT * FROM dim_fund", conn)

    scorecard = None
    sc_path = BASE_DIR / "data" / "processed" / "fund_scorecard.csv"
    if sc_path.exists():
        scorecard = pd.read_csv(sc_path)

    conn.close()
    return nav, perf, aum, sip, tx, folio, port, cat, fund, scorecard

# ══════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════
def render_sidebar():
    st.sidebar.image(
        "https://img.icons8.com/color/96/combo-chart.png", width=60)
    st.sidebar.title("Bluestock MF Analytics")
    st.sidebar.markdown("**Capstone Project | June 2026**")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "📄 Navigate to",
        ["🏦 Industry Overview",
         "📈 Fund Performance",
         "📉 NAV Analysis",
         "👥 Investor Insights"],
        index=0
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Data Coverage**")
    st.sidebar.markdown("- 40 Mutual Fund Schemes")
    st.sidebar.markdown("- 10 AMCs")
    st.sidebar.markdown("- Jan 2022 – May 2026")
    st.sidebar.markdown("- 32,778 Transactions")
    st.sidebar.markdown("---")
    st.sidebar.markdown("Built with ❤️ by **Shahin Shafi**")
    return page

# ══════════════════════════════════════════════════════════
# PAGE 1: INDUSTRY OVERVIEW
# ══════════════════════════════════════════════════════════
def page_industry(aum, sip, folio, cat):
    st.markdown('<p class="main-header">🏦 Industry Overview</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Indian Mutual Fund Industry — AUM, SIP & Folio Trends</p>', unsafe_allow_html=True)

    # ── Slicers ───────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        years = sorted(aum["year"].unique().tolist())
        sel_years = st.multiselect("📅 Filter by Year", years, default=years)
    with col2:
        fund_houses = sorted(aum["fund_house"].unique().tolist())
        sel_fh = st.multiselect("🏦 Filter by Fund House", fund_houses, default=fund_houses)

    aum_f = aum[aum["year"].isin(sel_years) & aum["fund_house"].isin(sel_fh)]

    # ── KPI Cards ─────────────────────────────────────────
    latest_aum = aum[aum["date_id"]==aum["date_id"].max()]["aum_crore"].sum()
    latest_sip = sip["sip_inflow_crore"].iloc[-1]
    latest_folio = folio["total_folios_crore"].iloc[-1]
    sip_growth = sip["sip_inflow_crore"].iloc[-1] / sip["sip_inflow_crore"].iloc[0] * 100 - 100

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total AUM", f"₹{latest_aum/1e5:.1f}L Cr", "Latest Quarter")
    k2.metric("Monthly SIP", f"₹{latest_sip:,} Cr", "Dec 2025 ATH")
    k3.metric("Total Folios", f"{latest_folio:.2f} Cr", "Dec 2025")
    k4.metric("SIP Growth", f"+{sip_growth:.0f}%", "Since Jan 2022")

    st.markdown("---")

    # ── AUM Bar Chart ──────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("AUM by Fund House")
        aum_latest = aum_f[aum_f["date_id"]==aum_f["date_id"].max()] if not aum_f.empty else aum[aum["date_id"]==aum["date_id"].max()]
        fig = px.bar(
            aum_latest.sort_values("aum_crore", ascending=True),
            x="aum_crore", y="fund_house", orientation="h",
            color="aum_crore", color_continuous_scale="Blues",
            labels={"aum_crore":"AUM (₹ Crore)", "fund_house":"Fund House"},
            title="Latest Quarter AUM"
        )
        fig.update_layout(height=380, showlegend=False,
                          coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("SIP Inflow Trend")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=sip["date"], y=sip["sip_inflow_crore"],
            fill="tozeroy", fillcolor="rgba(21,101,192,0.15)",
            line=dict(color="#1565C0", width=2),
            name="SIP Inflow (₹ Cr)"
        ))
        # ATH annotation
        ath = sip.loc[sip["sip_inflow_crore"].idxmax()]
        fig2.add_annotation(
            x=ath["date"], y=ath["sip_inflow_crore"],
            text=f"ATH ₹{ath['sip_inflow_crore']:,}Cr",
            showarrow=True, arrowhead=2,
            font=dict(color="#E53935", size=11),
            bgcolor="white", bordercolor="#E53935"
        )
        fig2.update_layout(height=380, xaxis_title="Month",
                           yaxis_title="₹ Crore")
        st.plotly_chart(fig2, use_container_width=True)

    # ── Folio Growth + Category Heatmap ───────────────────
    col_c, col_d = st.columns(2)
    with col_c:
        st.subheader("Folio Count Growth")
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=folio["date"], y=folio["total_folios_crore"],
            mode="lines+markers", name="Total",
            line=dict(color="black", width=2)))
        fig3.add_trace(go.Scatter(
            x=folio["date"], y=folio["equity_folios_crore"],
            mode="lines", name="Equity",
            line=dict(color="#1565C0", width=1.5)))
        fig3.add_trace(go.Scatter(
            x=folio["date"], y=folio["debt_folios_crore"],
            mode="lines", name="Debt",
            line=dict(color="#E53935", width=1.5)))
        fig3.update_layout(height=320, yaxis_title="Folios (Crore)",
                           legend=dict(orientation="h"))
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.subheader("Category Net Inflows")
        cat_grp = cat.groupby("category")["net_inflow_crore"].sum().sort_values(ascending=False).reset_index()
        fig4 = px.pie(cat_grp, values="net_inflow_crore", names="category",
                      hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
        fig4.update_layout(height=320, legend=dict(font=dict(size=10)))
        st.plotly_chart(fig4, use_container_width=True)

# ══════════════════════════════════════════════════════════
# PAGE 2: FUND PERFORMANCE
# ══════════════════════════════════════════════════════════
def page_performance(perf, scorecard):
    st.markdown('<p class="main-header">📈 Fund Performance</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Returns, Risk Metrics & Fund Scorecard</p>', unsafe_allow_html=True)

    # ── Slicers ───────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        cats = ["All"] + sorted(perf["category"].unique().tolist())
        sel_cat = st.selectbox("📂 Category", cats)
    with col2:
        plans = ["All", "Direct", "Regular"]
        sel_plan = st.selectbox("📋 Plan Type", plans)
    with col3:
        risks = ["All"] + sorted(perf["risk_category"].dropna().unique().tolist())
        sel_risk = st.selectbox("⚠️ Risk Grade", risks)

    pf = perf.copy()
    if sel_cat  != "All": pf = pf[pf["category"]   == sel_cat]
    if sel_plan != "All": pf = pf[pf["plan"]        == sel_plan]
    if sel_risk != "All": pf = pf[pf["risk_category"]== sel_risk]

    st.markdown(f"**Showing {len(pf)} funds**")

    # ── KPIs ──────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Avg 3yr Return", f"{pf['return_3yr_pct'].mean():.1f}%")
    k2.metric("Avg Sharpe",     f"{pf['sharpe_ratio'].mean():.2f}")
    k3.metric("Avg Alpha",      f"{pf['alpha'].mean():.2f}%")
    k4.metric("Avg Expense",    f"{pf['expense_ratio_pct'].mean():.2f}%")

    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("3-Year Return vs Sharpe Ratio")
        fig = px.scatter(
            pf, x="sharpe_ratio", y="return_3yr_pct",
            size="aum_crore", color="sub_cat",
            hover_name="scheme_name",
            labels={"sharpe_ratio":"Sharpe Ratio",
                    "return_3yr_pct":"3-Year Return (%)"},
            color_discrete_sequence=COLORS
        )
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Expense Ratio Distribution")
        fig2 = px.histogram(
            pf, x="expense_ratio_pct", nbins=20,
            color="plan", barmode="overlay",
            labels={"expense_ratio_pct":"Expense Ratio (%)"},
            color_discrete_map={"Direct":"#1565C0","Regular":"#90CAF9"}
        )
        fig2.update_layout(height=380)
        st.plotly_chart(fig2, use_container_width=True)

    # ── Scorecard Table ───────────────────────────────────
    st.subheader("📋 Fund Performance Table")
    display_cols = ["scheme_name","fund_house","sub_cat","plan",
                    "return_1yr_pct","return_3yr_pct","return_5yr_pct",
                    "sharpe_ratio","alpha","expense_ratio_pct",
                    "max_drawdown_pct","morningstar_rating"]
    show_df = pf[display_cols].copy()
    show_df.columns = ["Scheme","Fund House","Sub-Category","Plan",
                        "1yr %","3yr %","5yr %",
                        "Sharpe","Alpha","Exp Ratio",
                        "Max DD %","⭐ Rating"]
    show_df = show_df.sort_values("3yr %", ascending=False).reset_index(drop=True)
    show_df.index = show_df.index + 1
    st.dataframe(show_df, use_container_width=True, height=400)

    # ── Scorecard chart ───────────────────────────────────
    if scorecard is not None:
        st.subheader("🏆 Fund Composite Scorecard (0-100)")
        sc_show = scorecard.head(15).copy()
        sc_show["short"] = sc_show["scheme_name"].apply(
            lambda x: str(x).split(" - ")[0][:25])
        fig3 = px.bar(
            sc_show.sort_values("composite_score"),
            x="composite_score", y="short", orientation="h",
            color="composite_score",
            color_continuous_scale="Blues",
            labels={"composite_score":"Score","short":"Fund"}
        )
        fig3.update_layout(height=450, coloraxis_showscale=False)
        st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════════════════
# PAGE 3: NAV ANALYSIS
# ══════════════════════════════════════════════════════════
def page_nav(nav, perf):
    st.markdown('<p class="main-header">📉 NAV Analysis</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">NAV Trends, Drawdown & Return Correlation</p>', unsafe_allow_html=True)

    # ── Slicers ───────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        all_funds = sorted(nav["scheme_name"].unique().tolist())
        default_funds = all_funds[:5]
        sel_funds = st.multiselect("📊 Select Funds", all_funds, default=default_funds)
    with col2:
        date_from = st.date_input("📅 From Date", value=pd.Timestamp("2023-01-01"))
    with col3:
        date_to = st.date_input("📅 To Date", value=pd.Timestamp("2026-05-29"))

    if not sel_funds:
        st.warning("Please select at least one fund.")
        return

    nav_f = nav[
        (nav["scheme_name"].isin(sel_funds)) &
        (nav["date"] >= pd.Timestamp(date_from)) &
        (nav["date"] <= pd.Timestamp(date_to))
    ].copy()

    # ── NAV Trend Chart ───────────────────────────────────
    st.subheader("NAV Trend (Indexed to 100)")
    fig = go.Figure()
    for i, fname in enumerate(sel_funds):
        fd = nav_f[nav_f["scheme_name"]==fname].sort_values("date")
        if fd.empty: continue
        idx = fd["nav"] / fd["nav"].iloc[0] * 100
        short = fname.split(" - ")[0][:25]
        fig.add_trace(go.Scatter(
            x=fd["date"], y=idx,
            mode="lines", name=short,
            line=dict(color=COLORS[i % len(COLORS)], width=2)
        ))
    fig.add_vrect(x0="2023-01-01", x1="2023-12-31",
                  fillcolor="green", opacity=0.05,
                  annotation_text="2023 Bull Run")
    fig.add_vrect(x0="2024-09-01", x1="2024-12-31",
                  fillcolor="red", opacity=0.05,
                  annotation_text="2024 Correction")
    fig.update_layout(height=420, xaxis_title="Date",
                      yaxis_title="Indexed NAV",
                      legend=dict(font=dict(size=9)))
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)

    # ── Drawdown Chart ────────────────────────────────────
    with col_a:
        st.subheader("Drawdown Chart")
        fig2 = go.Figure()
        for i, fname in enumerate(sel_funds[:5]):
            fd = nav_f[nav_f["scheme_name"]==fname].sort_values("date")
            if fd.empty: continue
            peak = fd["nav"].cummax()
            dd   = (fd["nav"] / peak - 1) * 100
            short = fname.split(" - ")[0][:20]
            fig2.add_trace(go.Scatter(
                x=fd["date"], y=dd,
                mode="lines", name=short, fill="tozeroy",
                line=dict(color=COLORS[i % len(COLORS)], width=1.5),
                fillcolor=f"rgba({int(COLORS[i%len(COLORS)][1:3],16)},"
                          f"{int(COLORS[i%len(COLORS)][3:5],16)},"
                          f"{int(COLORS[i%len(COLORS)][5:],16)},0.1)"
            ))
        fig2.update_layout(height=350, yaxis_title="Drawdown (%)",
                           legend=dict(font=dict(size=8)))
        st.plotly_chart(fig2, use_container_width=True)

    # ── Correlation Matrix ────────────────────────────────
    with col_b:
        st.subheader("Return Correlation")
        nav_wide = nav_f.pivot_table(
            index="date", columns="scheme_name", values="nav")
        returns  = nav_wide.pct_change().dropna()
        if returns.shape[1] >= 2:
            corr = returns.corr()
            corr.columns = [c.split(" - ")[0][:15] for c in corr.columns]
            corr.index   = corr.columns
            corr.columns = [f"{c[:12]}_{i}" for i, c in enumerate(corr.columns)]
            corr.index = corr.columns
            fig3 = px.imshow(
                corr, color_continuous_scale="RdYlGn",
                zmin=0, zmax=1, text_auto=".2f",
                aspect="auto"
            )
            fig3.update_layout(height=350)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Select 2+ funds to see correlation.")

# ══════════════════════════════════════════════════════════
# PAGE 4: INVESTOR INSIGHTS
# ══════════════════════════════════════════════════════════
def page_investors(tx):
    st.markdown('<p class="main-header">👥 Investor Insights</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Demographics, Geography & Transaction Analysis</p>', unsafe_allow_html=True)

    # ── Slicers ───────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        tx_types = ["All"] + sorted(tx["transaction_type"].unique().tolist())
        sel_tx = st.selectbox("💳 Transaction Type", tx_types)
    with col2:
        tiers = ["All"] + sorted(tx["city_tier"].unique().tolist())
        sel_tier = st.selectbox("🏙️ City Tier", tiers)
    with col3:
        genders = ["All"] + sorted(tx["gender"].unique().tolist())
        sel_gender = st.selectbox("👤 Gender", genders)

    txf = tx.copy()
    if sel_tx     != "All": txf = txf[txf["transaction_type"] == sel_tx]
    if sel_tier   != "All": txf = txf[txf["city_tier"]        == sel_tier]
    if sel_gender != "All": txf = txf[txf["gender"]           == sel_gender]

    # ── KPIs ──────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Transactions", f"{len(txf):,}")
    k2.metric("Unique Investors",   f"{txf['investor_id'].nunique():,}")
    k3.metric("Total Amount",       f"₹{txf['amount_inr'].sum()/1e7:.0f} Cr")
    k4.metric("Avg Transaction",    f"₹{txf['amount_inr'].mean():,.0f}")

    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Investment by State (Top 15)")
        state_amt = (txf.groupby("state")["amount_inr"]
                     .sum().sort_values(ascending=False)
                     .head(15).reset_index())
        state_amt["amount_cr"] = state_amt["amount_inr"] / 1e7
        fig = px.bar(
            state_amt.sort_values("amount_cr"),
            x="amount_cr", y="state", orientation="h",
            color="amount_cr", color_continuous_scale="Blues",
            labels={"amount_cr":"Amount (₹ Cr)","state":"State"}
        )
        fig.update_layout(height=420, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Age Group & Gender Split")
        age_gen = (txf.groupby(["age_group","gender"])["amount_inr"]
                   .sum().reset_index())
        age_gen["amount_cr"] = age_gen["amount_inr"] / 1e7
        fig2 = px.bar(
            age_gen, x="age_group", y="amount_cr", color="gender",
            barmode="group",
            color_discrete_map={"Male":"#1565C0","Female":"#E91E63"},
            labels={"amount_cr":"Amount (₹ Cr)",
                    "age_group":"Age Group"}
        )
        fig2.update_layout(height=420)
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Payment Mode Distribution")
        pay = (txf.groupby("payment_mode")["amount_inr"]
               .sum().reset_index())
        pay["amount_cr"] = pay["amount_inr"] / 1e7
        fig3 = px.pie(
            pay, values="amount_cr", names="payment_mode",
            hole=0.4, color_discrete_sequence=COLORS
        )
        fig3.update_layout(height=320)
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.subheader("Monthly Transaction Trend")
        txf["month"] = txf["date"].dt.to_period("M").dt.to_timestamp()
        monthly = (txf.groupby(["month","transaction_type"])["amount_inr"]
                   .sum().reset_index())
        monthly["amount_cr"] = monthly["amount_inr"] / 1e7
        fig4 = px.line(
            monthly, x="month", y="amount_cr",
            color="transaction_type",
            color_discrete_map={
                "SIP":"#1565C0",
                "Lumpsum":"#2E7D32",
                "Redemption":"#E53935"},
            labels={"amount_cr":"Amount (₹ Cr)","month":"Month"}
        )
        fig4.update_layout(height=320)
        st.plotly_chart(fig4, use_container_width=True)

    # ── T30 vs B30 ────────────────────────────────────────
    st.subheader("T30 vs B30 City Tier Comparison")
    tier_data = (txf.groupby("city_tier").agg(
        transactions=("amount_inr","count"),
        total_cr=("amount_inr", lambda x: x.sum()/1e7),
        avg_amount=("amount_inr","mean"),
        unique_investors=("investor_id","nunique")
    ).reset_index())
    st.dataframe(tier_data, use_container_width=True)

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def main():
    # Load data
    with st.spinner("Loading data..."):
        nav, perf, aum, sip, tx, folio, port, cat, fund, scorecard = load_all_data()

    # Sidebar navigation
    page = render_sidebar()

    # Route to correct page
    if page == "🏦 Industry Overview":
        page_industry(aum, sip, folio, cat)
    elif page == "📈 Fund Performance":
        page_performance(perf, scorecard)
    elif page == "📉 NAV Analysis":
        page_nav(nav, perf)
    elif page == "👥 Investor Insights":
        page_investors(tx)

if __name__ == "__main__":
    main()
