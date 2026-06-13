# Mutual Fund Analytics Platform
**Bluestock Fintech — Individual Capstone Project**
Author: Shahin Shafi | June 2026

A full-stack data platform ingesting Indian Mutual Fund data (AMFI, mfapi.in),
processing it through a Python ETL pipeline, loading into SQLite, and exposing
insights via dashboards and Python analytics notebooks.

---

## Folder Structure

```
mutual_fund_platform/
├── data/
│   ├── raw/               ← original 10 CSV files
│   ├── processed/         ← cleaned, merged CSVs (git-ignored, regeneratable)
│   └── db/                ← bluestock_mf.db SQLite (git-ignored, use schema.sql)
├── notebooks/
│   ├── 03_eda_analysis.ipynb
│   ├── 04_performance_analytics.ipynb
│   └── 05_advanced_analytics.ipynb
├── scripts/
│   ├── etl_pipeline.py       ← clean all 10 CSVs
│   ├── live_nav_fetch.py     ← fetch live NAV from mfapi.in
│   ├── compute_metrics.py    ← CAGR, Sharpe, Alpha, Beta, Scorecard
│   └── generate_charts.py    ← all EDA charts
├── sql/
│   ├── schema.sql            ← full star schema DDL
│   └── queries.sql           ← 10 analytical queries
├── dashboard/
│   └── bluestock_mf.pbix     ← Power BI dashboard
├── reports/
│   ├── charts/               ← exported PNG charts
│   ├── data_dictionary.md
│   ├── Final_Report.pdf      ← Day 7
│   └── Presentation.pptx     ← Day 7
└── README.md
```

## Setup

```bash
git clone https://github.com/Shahinshafi1717/mutual-fund-platform.git
cd mutual_fund_platform
pip install -r requirements.txt
```

## Run Order

```bash
# 1. Clean all CSVs
python scripts/etl_pipeline.py

# 2. Load into SQLite
python db_load.py

# 3. Generate charts
python scripts/generate_charts.py

# 4. Compute performance metrics
python scripts/compute_metrics.py

# 5. Fetch live NAV (requires internet)
python scripts/live_nav_fetch.py
```

## 7-Day Roadmap

| Day | Focus | Status |
|-----|-------|--------|
| 1 | Data Ingestion & Quality Validation | ✅ Done |
| 2 | SQLite Schema & ETL Pipeline | ✅ Done |
| 3 | Exploratory Data Analysis | ✅ Done |
| 4 | Risk Metrics & Performance Analytics | ✅ Done |
| 5 | BI Dashboard (Power BI) | 🔲 |
| 6 | Advanced Analytics | 🔲 |
| 7 | Final Report & Wrap-up | 🔲 |

## Tech Stack
- **Language**: Python 3.14
- **Libraries**: Pandas, NumPy, SciPy, SQLAlchemy, Matplotlib, Seaborn, Plotly
- **Database**: SQLite3 (schema in sql/schema.sql)
- **BI**: Power BI
- **Environment**: VS Code, Git/GitHub
