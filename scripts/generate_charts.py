"""
Day 3: EDA Chart Generator
Run this script to produce all PNG/HTML charts.
"""
import warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import sqlite3, os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import seaborn as sns

BASE_DIR   = Path(__file__).resolve().parent
DB_PATH    = BASE_DIR / "bluestock_mf.db"
CHARTS_DIR = BASE_DIR / "reports" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", palette="husl", font_scale=1.1)
plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.bbox"] = "tight"
COLORS = ["#2196F3","#FF5722","#4CAF50","#9C27B0",
          "#FF9800","#00BCD4","#E91E63","#607D8B","#8BC34A","#FFC107"]

conn = sqlite3.connect(DB_PATH)
print(f"Connected to {DB_PATH.name}")

# ── Load data ──────────────────────────────────────────────
df_nav  = pd.read_sql("SELECT n.amfi_code,n.date_id,n.nav,f.scheme_name,f.sub_category,f.fund_house FROM fact_nav n JOIN dim_fund f ON n.amfi_code=f.amfi_code", conn)
df_nav["date"] = pd.to_datetime(df_nav["date_id"])

df_fund = pd.read_sql("SELECT * FROM dim_fund", conn)
df_aum  = pd.read_sql("SELECT * FROM fact_aum", conn)
df_aum["date"] = pd.to_datetime(df_aum["date_id"])
df_aum["year"] = df_aum["date"].dt.year

df_sip  = pd.read_sql("SELECT * FROM fact_sip_industry ORDER BY month_id", conn)
df_sip["date"] = pd.to_datetime(df_sip["month_id"])

df_cat  = pd.read_sql("SELECT * FROM fact_category_inflows", conn)
df_cat["date"] = pd.to_datetime(df_cat["month_id"])

df_tx   = pd.read_sql("SELECT * FROM fact_transactions", conn)

df_folio = pd.read_sql("SELECT * FROM fact_folio_count ORDER BY month_id", conn)
df_folio["date"] = pd.to_datetime(df_folio["month_id"])

df_port = pd.read_sql("SELECT p.*,f.category FROM fact_portfolio p JOIN dim_fund f ON p.amfi_code=f.amfi_code", conn)
df_perf = pd.read_sql("SELECT p.*,f.scheme_name,f.sub_category FROM fact_performance p JOIN dim_fund f ON p.amfi_code=f.amfi_code WHERE f.plan='Direct'", conn)

print("Data loaded")

# ── Chart 1: NAV Trends (top 8 funds indexed) ─────────────
print("Generating Chart 1: NAV Trends...")
top_codes = df_perf.nlargest(8,"aum_crore")["amfi_code"].tolist()
nav_top = df_nav[df_nav["amfi_code"].isin(top_codes)].sort_values(["amfi_code","date"]).copy()
nav_top["nav_idx"] = nav_top.groupby("amfi_code")["nav"].transform(lambda x: x/x.iloc[0]*100)

fig, ax = plt.subplots(figsize=(14,6))
for i, code in enumerate(top_codes):
    fd = nav_top[nav_top["amfi_code"]==code]
    name = fd["scheme_name"].iloc[0].split(" - ")[0][:22]
    ax.plot(fd["date"], fd["nav_idx"], linewidth=1.5, label=name, color=COLORS[i])

ax.axvspan(pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31"),
           alpha=0.08, color="green", label="2023 Bull Run")
ax.axvspan(pd.Timestamp("2024-09-01"), pd.Timestamp("2024-12-31"),
           alpha=0.08, color="red", label="2024 Correction")
ax.set_ylabel("Indexed NAV (Base=100)")
ax.set_title("NAV Performance Indexed to 100 (Jan 2022)", fontsize=13)
ax.legend(fontsize=8, ncol=2)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
plt.xticks(rotation=30)
plt.tight_layout()
plt.savefig(CHARTS_DIR/"01_nav_trends.png", dpi=150)
plt.close()
print("  Saved 01_nav_trends.png")

# ── Chart 2: AUM Grouped Bar ───────────────────────────────
print("Generating Chart 2: AUM Growth...")
aum_yr = df_aum.groupby(["fund_house","year"])["aum_crore"].max().reset_index()
aum_pv = aum_yr.pivot(index="fund_house",columns="year",values="aum_crore").fillna(0)
aum_pv = aum_pv.sort_values(aum_pv.columns[-1], ascending=False)

fig, ax = plt.subplots(figsize=(14,6))
years = aum_pv.columns.tolist()
x = np.arange(len(aum_pv))
w = 0.18
bar_cols = ["#BBDEFB","#64B5F6","#1565C0","#0D47A1","#E3F2FD"]
for i, yr in enumerate(years):
    bars = ax.bar(x+i*w, aum_pv[yr]/1e5, w, label=str(yr),
                  color=bar_cols[i], edgecolor="white")
    if "SBI" in aum_pv.index[0]:
        bars[0].set_edgecolor("#FF5722"); bars[0].set_linewidth(2.5)

ax.set_xticks(x+w*2)
ax.set_xticklabels(aum_pv.index, rotation=30, ha="right", fontsize=9)
ax.set_ylabel("AUM (₹ Lakh Crore)")
ax.set_title("AUM Growth by Fund House 2022–2025\n(Orange border = SBI Mutual Fund ₹12.5L Cr)", fontsize=13)
ax.legend(title="Year")
plt.tight_layout()
plt.savefig(CHARTS_DIR/"02_aum_growth.png", dpi=150)
plt.close()
print("  Saved 02_aum_growth.png")

# ── Chart 3: SIP Time Series ───────────────────────────────
print("Generating Chart 3: SIP Trend...")
fig, ax1 = plt.subplots(figsize=(14,5))
ax2 = ax1.twinx()
ax1.fill_between(df_sip["date"], df_sip["sip_inflow_crore"],
                  alpha=0.25, color="#1565C0")
ax1.plot(df_sip["date"], df_sip["sip_inflow_crore"],
          color="#1565C0", linewidth=2, label="SIP Inflow (₹ Cr)")
ax2.plot(df_sip["date"], df_sip["active_sip_accounts_crore"],
          color="#FF9800", linewidth=1.8, linestyle="--", label="Active Accounts (Cr)")

ath = df_sip.loc[df_sip["sip_inflow_crore"].idxmax()]
ax1.annotate(f"ATH: ₹{ath['sip_inflow_crore']:,} Cr\nDec 2025",
             xy=(ath["date"], ath["sip_inflow_crore"]),
             xytext=(-80, -40), textcoords="offset points",
             arrowprops=dict(arrowstyle="->", color="#FF5722"),
             fontsize=10, color="#FF5722",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.9))

ax1.set_ylabel("SIP Inflow (₹ Crore)", color="#1565C0")
ax2.set_ylabel("Active Accounts (Crore)", color="#FF9800")
ax1.set_title("Monthly SIP Inflows & Active Accounts (Jan 2022 – Dec 2025)", fontsize=13)
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1+lines2, labels1+labels2, loc="upper left")
plt.xticks(rotation=30)
plt.tight_layout()
plt.savefig(CHARTS_DIR/"03_sip_trend.png", dpi=150)
plt.close()
print("  Saved 03_sip_trend.png")

# ── Chart 4: Category Heatmap ──────────────────────────────
print("Generating Chart 4: Category Heatmap...")
df_cat["month_label"] = df_cat["date"].dt.strftime("%b %y")
month_order = df_cat.sort_values("date")["month_label"].unique().tolist()
heat_pv = df_cat.pivot_table(index="category",columns="month_label",
                               values="net_inflow_crore",aggfunc="sum")
heat_pv = heat_pv[month_order]
heat_pv = heat_pv.sort_values(heat_pv.columns[-1], ascending=False)

fig, ax = plt.subplots(figsize=(16,7))
sns.heatmap(heat_pv, ax=ax, cmap="YlOrRd", fmt=".0f",
            annot=True, annot_kws={"size":7},
            linewidths=0.3, cbar_kws={"label":"Net Inflow (₹ Cr)"})
ax.set_title("Category-wise Net Inflows Heatmap (FY 2024-25)", fontsize=13, pad=15)
ax.set_xlabel("Month"); ax.set_ylabel("Fund Category")
plt.xticks(rotation=45, ha="right", fontsize=8)
plt.tight_layout()
plt.savefig(CHARTS_DIR/"04_category_heatmap.png", dpi=150)
plt.close()
print("  Saved 04_category_heatmap.png")

# ── Chart 5: Demographics ──────────────────────────────────
print("Generating Charts 5-6: Demographics...")
fig, axes = plt.subplots(1, 3, figsize=(18,6))
age_amt = df_tx.groupby("age_group")["amount_inr"].sum().sort_index()
axes[0].pie(age_amt, labels=age_amt.index, autopct="%1.1f%%",
            colors=COLORS[:len(age_amt)], startangle=90,
            wedgeprops=dict(edgecolor="white", linewidth=1.5))
axes[0].set_title("Investment by Age Group", fontsize=12, fontweight="bold")

sip_data = df_tx[df_tx["transaction_type"]=="SIP"].copy()
age_order = ["18-25","26-35","36-45","46-55","56+"]
sns.boxplot(data=sip_data, x="age_group", y="amount_inr",
            order=age_order, ax=axes[1], palette="Blues",
            flierprops=dict(marker="o", markersize=2))
axes[1].set_title("SIP Amount by Age Group", fontsize=12, fontweight="bold")
axes[1].set_xlabel("Age Group"); axes[1].set_ylabel("SIP Amount (INR)")

gender = df_tx.groupby("gender")["amount_inr"].sum()
axes[2].pie(gender, labels=gender.index, autopct="%1.1f%%",
            colors=["#42A5F5","#F48FB1"], startangle=90,
            wedgeprops=dict(edgecolor="white", linewidth=2))
axes[2].set_title("Investment by Gender", fontsize=12, fontweight="bold")
plt.suptitle("Investor Demographics", fontsize=14, fontweight="bold")
plt.tight_layout()
plt.savefig(CHARTS_DIR/"05_demographics.png", dpi=150)
plt.close()
print("  Saved 05_demographics.png")

# ── Chart 6: Geographic ────────────────────────────────────
print("Generating Charts 7-8: Geographic...")
fig, axes = plt.subplots(1, 2, figsize=(16,6))
state_amt = df_tx.groupby("state")["amount_inr"].sum().sort_values(ascending=True).tail(15)
bar_c = ["#FF5722" if v==state_amt.max() else "#42A5F5" for v in state_amt]
axes[0].barh(state_amt.index, state_amt.values/1e7, color=bar_c, edgecolor="white")
axes[0].set_xlabel("Total Investment (INR Crore)")
axes[0].set_title("Top 15 States by Investment Volume", fontsize=12, fontweight="bold")

tier = df_tx.groupby("city_tier")["amount_inr"].sum()
axes[1].pie(tier, labels=tier.index, autopct="%1.1f%%",
            colors=["#1565C0","#FF9800"], startangle=90,
            wedgeprops=dict(edgecolor="white", linewidth=2),
            textprops=dict(fontsize=12))
axes[1].set_title("T30 vs B30 City Tier Split", fontsize=12, fontweight="bold")
plt.suptitle("Geographic Distribution", fontsize=14, fontweight="bold")
plt.tight_layout()
plt.savefig(CHARTS_DIR/"07_geographic.png", dpi=150)
plt.close()
print("  Saved 07_geographic.png")

# ── Chart 7: Folio Growth ──────────────────────────────────
print("Generating Chart 9: Folio Growth...")
fig, ax = plt.subplots(figsize=(14,6))
ax.fill_between(df_folio["date"], df_folio["equity_folios_crore"],
                alpha=0.7, color="#1565C0", label="Equity")
ax.fill_between(df_folio["date"],
                df_folio["equity_folios_crore"],
                df_folio["equity_folios_crore"]+df_folio["hybrid_folios_crore"],
                alpha=0.7, color="#4CAF50", label="Hybrid")
ax.fill_between(df_folio["date"],
                df_folio["equity_folios_crore"]+df_folio["hybrid_folios_crore"],
                df_folio["total_folios_crore"],
                alpha=0.7, color="#FF9800", label="Debt+Others")
ax.plot(df_folio["date"], df_folio["total_folios_crore"],
        color="black", linewidth=2, label="Total")

for date_str, label in [("2022-01-01","13.26 Cr\nJan 2022"),("2025-12-01","26.12 Cr\nDec 2025")]:
    row = df_folio[df_folio["month_id"]==date_str]
    if not row.empty:
        y = row["total_folios_crore"].values[0]
        ax.annotate(label, xy=(pd.Timestamp(date_str), y),
                    xytext=(20, 10), textcoords="offset points",
                    arrowprops=dict(arrowstyle="->"),
                    fontsize=9,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7))

ax.set_ylabel("Folios (Crore)")
ax.set_title("Industry Folio Count Growth (2022–2025)\nDoubled from 13.26 Cr to 26.12 Cr", fontsize=13)
ax.legend(loc="upper left")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
plt.xticks(rotation=30)
plt.tight_layout()
plt.savefig(CHARTS_DIR/"09_folio_growth.png", dpi=150)
plt.close()
print("  Saved 09_folio_growth.png")

# ── Chart 8: Correlation Matrix ────────────────────────────
print("Generating Chart 10: Correlation Matrix...")
sel_codes = df_perf.nlargest(10,"aum_crore")["amfi_code"].tolist()
nav_sel = df_nav[df_nav["amfi_code"].isin(sel_codes)]
nav_pv  = nav_sel.pivot_table(index="date",columns="amfi_code",values="nav").sort_index()
returns = nav_pv.pct_change().dropna()
label_map = {}
for _, row in df_perf.nlargest(10, "aum_crore").iterrows():
    code = row["amfi_code"]
    name = row["scheme_name"]
    if isinstance(name, pd.Series):
        name = name.iloc[0]
    label_map[code] = str(name).split(" - ")[0][:16]
returns.columns = [label_map.get(c,str(c)) for c in returns.columns]
corr = returns.corr()
mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
fig, ax = plt.subplots(figsize=(12,9))
sns.heatmap(corr, ax=ax, annot=True, fmt=".2f", cmap="RdYlGn",
            vmin=0, vmax=1, mask=mask, linewidths=0.5,
            annot_kws={"size":8}, cbar_kws={"label":"Pearson Correlation"})
ax.set_title("Daily Return Correlation Matrix — Top 10 Equity Funds", fontsize=13, pad=15)
plt.xticks(rotation=40, ha="right", fontsize=8)
plt.yticks(fontsize=8)
plt.tight_layout()
plt.savefig(CHARTS_DIR/"10_correlation_matrix.png", dpi=150)
plt.close()
print("  Saved 10_correlation_matrix.png")

# ── Chart 9: Sector Donut ──────────────────────────────────
print("Generating Chart 11: Sector Donut...")
eq_port = df_port[df_port["category"]=="Equity"]
sec_wt  = eq_port.groupby("sector")["weight_pct"].sum().sort_values(ascending=False)
sec_pct = sec_wt / sec_wt.sum() * 100
fig, ax = plt.subplots(figsize=(10,8))
wedges, texts, autotexts = ax.pie(
    sec_pct, labels=sec_pct.index, autopct="%1.1f%%",
    colors=COLORS[:len(sec_pct)]+["#795548","#9E9E9E"],
    startangle=90, pctdistance=0.82,
    wedgeprops=dict(width=0.55, edgecolor="white", linewidth=2))
for at in autotexts: at.set_fontsize(8)
ax.set_title("Sector Allocation Across All Equity Funds", fontsize=13, fontweight="bold", pad=20)
plt.tight_layout()
plt.savefig(CHARTS_DIR/"11_sector_donut.png", dpi=150)
plt.close()
print("  Saved 11_sector_donut.png")

# ── Chart 10: Risk vs Return ───────────────────────────────
print("Generating Chart 12: Risk vs Return...")
eq_perf = df_perf[df_perf["sub_category"].isin(["Large Cap","Mid Cap","Small Cap","Flexi Cap"])]
fig, ax = plt.subplots(figsize=(12,7))
for cat, grp in eq_perf.groupby("sub_category"):
    sc = ax.scatter(grp["std_dev_ann_pct"], grp["return_3yr_pct"],
                    s=grp["aum_crore"]/200, label=cat,
                    alpha=0.8, edgecolors="white", linewidth=0.8)
    for _, row in grp.iterrows():
        ax.annotate(str(row["scheme_name"].iloc[0] if isinstance(row["scheme_name"], pd.Series) else row["scheme_name"]).split(" - ")[0][:14],
                    (row["std_dev_ann_pct"], row["return_3yr_pct"]),
                    textcoords="offset points", xytext=(5,4), fontsize=7, alpha=0.8)
ax.set_xlabel("Annualised Std Dev (%)"); ax.set_ylabel("3-Year Return (%)")
ax.set_title("Risk vs Return — Direct Equity Funds\n(Bubble size = AUM)", fontsize=13)
ax.legend()
plt.tight_layout()
plt.savefig(CHARTS_DIR/"12_risk_return.png", dpi=150)
plt.close()
print("  Saved 12_risk_return.png")

# ── Chart 13: SIP YoY ─────────────────────────────────────
print("Generating Chart 13: SIP YoY...")
df_yoy = df_sip.dropna(subset=["yoy_growth_pct"]).copy()
fig, ax = plt.subplots(figsize=(13,5))
bar_c = ["#4CAF50" if v>=0 else "#F44336" for v in df_yoy["yoy_growth_pct"]]
ax.bar(df_yoy["date"], df_yoy["yoy_growth_pct"], color=bar_c, width=20, edgecolor="white")
ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
ax.set_ylabel("YoY Growth (%)"); ax.set_title("SIP Inflow Year-on-Year Growth Rate", fontsize=13)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(CHARTS_DIR/"13_sip_yoy.png", dpi=150)
plt.close()
print("  Saved 13_sip_yoy.png")

# ── Chart 14: Expense vs Return ───────────────────────────
print("Generating Chart 14: Expense vs Return...")
eq_p = df_perf[df_perf["sub_category"].isin(["Large Cap","Mid Cap","Small Cap","Flexi Cap"])]
fig, ax = plt.subplots(figsize=(12,6))
for cat, grp in eq_p.groupby("sub_category"):
    ax.scatter(grp["expense_ratio_pct"], grp["return_3yr_pct"],
               label=cat, s=120, alpha=0.8, edgecolors="white")
    for _, row in grp.iterrows():
        ax.annotate(str(row["scheme_name"].iloc[0] if isinstance(row["scheme_name"], pd.Series) else row["scheme_name"]).split(" - ")[0][:14],
                    (row["expense_ratio_pct"], row["return_3yr_pct"]),
                    textcoords="offset points", xytext=(5,4), fontsize=7, alpha=0.8)
ax.set_xlabel("Expense Ratio (%)"); ax.set_ylabel("3-Year Return (%)")
ax.set_title("Expense Ratio vs 3-Year Return (Direct Equity Funds)", fontsize=13)
ax.legend()
plt.tight_layout()
plt.savefig(CHARTS_DIR/"14_expense_return.png", dpi=150)
plt.close()
print("  Saved 14_expense_return.png")

# ── Chart 15: Payment Mode ────────────────────────────────
print("Generating Chart 15: Payment & Transactions...")
fig, axes = plt.subplots(1, 2, figsize=(14,5))
pay = df_tx.groupby("payment_mode")["amount_inr"].sum().sort_values(ascending=False)
axes[0].bar(pay.index, pay.values/1e7, color=COLORS[:len(pay)], edgecolor="white")
axes[0].set_ylabel("Total Amount (INR Crore)")
axes[0].set_title("Investment by Payment Mode", fontsize=12, fontweight="bold")
axes[0].tick_params(axis="x", rotation=20)

df_tx["month"] = pd.to_datetime(df_tx["transaction_date"]).dt.to_period("M").dt.to_timestamp()
tx_grp = df_tx.groupby(["month","transaction_type"])["amount_inr"].sum().reset_index()
for ttype, grp in tx_grp.groupby("transaction_type"):
    axes[1].plot(grp["month"], grp["amount_inr"]/1e7, marker="o",
                 markersize=3, linewidth=1.5, label=ttype)
axes[1].set_ylabel("Amount (INR Crore)")
axes[1].set_title("Monthly Transaction Trend by Type", fontsize=12, fontweight="bold")
axes[1].legend()
axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
plt.xticks(rotation=30)
plt.tight_layout()
plt.savefig(CHARTS_DIR/"15_payment_tx.png", dpi=150)
plt.close()
print("  Saved 15_payment_tx.png")

conn.close()
charts = sorted(CHARTS_DIR.glob("*.png"))
print(f"\n All {len(charts)} charts saved to: {CHARTS_DIR}")
for c in charts:
    print(f"  {c.name}  ({os.path.getsize(c)//1024} KB)")
