"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
Day 1: Live NAV Fetcher
File   : live_nav_fetch.py
Author : <Your Name>
Date   : 2026-06
============================================================
Purpose:
  Fetch live/historical NAV data from mfapi.in (free public API)
  for specified AMFI scheme codes.  Saves each scheme as a CSV
  in data/raw/ and produces a combined multi-scheme CSV.

API Reference:
  Base URL : https://api.mfapi.in
  Endpoints:
    GET /mf/{scheme_code}          → Full NAV history + metadata
    GET /mf/{scheme_code}/latest   → Only the most recent NAV
    GET /mf                        → Full AMFI scheme list

Usage:
  python live_nav_fetch.py

Output files (in data/raw/):
  live_nav_{scheme_code}.csv  — per-scheme NAV history
  live_nav_combined.csv       — all schemes stacked
============================================================
"""

import time
import json
import logging
from pathlib import Path

import requests
import pandas as pd

# ──────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────
BASE_URL  = "https://api.mfapi.in/mf"
BASE_DIR  = Path(__file__).resolve().parent
RAW_DIR   = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Polite delay between API requests (seconds)
# mfapi.in is a free community API — don't hammer it
REQUEST_DELAY = 1.0

# HTTP timeout (seconds)
TIMEOUT = 15

# ──────────────────────────────────────────────────────────
# SCHEMES TO FETCH
# Task 4: HDFC Top 100 Direct (125497)
# Task 5: 5 key large-cap schemes
# ──────────────────────────────────────────────────────────
SCHEMES = {
    125497: "HDFC Top 100 Fund - Direct Plan",      # Task 4 (demo scheme)
    119551: "SBI Bluechip Fund - Regular",
    120503: "ICICI Pru Bluechip Fund - Direct",
    118632: "Nippon India Large Cap - Direct",
    119092: "Axis Bluechip Fund - Direct",
    120841: "Kotak Bluechip Fund - Direct",
}

# ──────────────────────────────────────────────────────────
# LOGGING SETUP
# ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# CORE FUNCTIONS
# ──────────────────────────────────────────────────────────

def fetch_scheme(scheme_code: int, scheme_name: str) -> pd.DataFrame | None:
    """
    Fetch full NAV history for a single scheme from mfapi.in.

    Returns a cleaned DataFrame with columns:
        amfi_code | scheme_name | date | nav

    Returns None on any network / parse error.

    JSON response structure from mfapi.in:
    {
      "meta": {
        "fund_house": "...",
        "scheme_type": "...",
        "scheme_category": "...",
        "scheme_code": 119551,
        "scheme_name": "..."
      },
      "data": [
        {"date": "29-05-2026", "nav": "54.3856"},
        ...
      ],
      "status": "SUCCESS"
    }
    """
    url = f"{BASE_URL}/{scheme_code}"
    log.info(f"Fetching  [{scheme_code}] {scheme_name}  →  {url}")

    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()                   # Raises on 4xx/5xx
    except requests.exceptions.ConnectionError:
        log.error(f"  Connection failed — check internet connectivity")
        return None
    except requests.exceptions.Timeout:
        log.error(f"  Request timed out after {TIMEOUT}s")
        return None
    except requests.exceptions.HTTPError as e:
        log.error(f"  HTTP error: {e}")
        return None

    # ── Parse JSON ───────────────────────────────────────
    try:
        payload = response.json()
    except json.JSONDecodeError:
        log.error(f"  Invalid JSON in response")
        return None

    if payload.get("status") != "SUCCESS":
        log.warning(f"  API returned status: {payload.get('status')}")
        return None

    nav_records = payload.get("data", [])
    if not nav_records:
        log.warning(f"  No NAV data in response")
        return None

    # ── Build DataFrame ──────────────────────────────────
    df = pd.DataFrame(nav_records)           # columns: date, nav (as strings)

    # Convert date: API returns "DD-MM-YYYY", we standardise to "YYYY-MM-DD"
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    # Convert NAV to float (API returns string)
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

    # Drop any rows where NAV couldn't be parsed
    bad_rows = df["nav"].isna().sum()
    if bad_rows:
        log.warning(f"  Dropped {bad_rows} rows with unparseable NAV")
    df = df.dropna(subset=["nav"])

    # Add identifier columns
    df.insert(0, "amfi_code",    scheme_code)
    df.insert(1, "scheme_name",  scheme_name)

    # Sort ascending by date
    df = df.sort_values("date").reset_index(drop=True)

    log.info(
        f"  ✅ {len(df):,} NAV records | "
        f"{df['date'].min()} → {df['date'].max()}"
    )
    return df


def save_scheme_csv(df: pd.DataFrame, scheme_code: int) -> Path:
    """Save per-scheme NAV history to data/raw/."""
    out_path = RAW_DIR / f"live_nav_{scheme_code}.csv"
    df.to_csv(out_path, index=False)
    log.info(f"  💾 Saved → {out_path.name}")
    return out_path


def print_nav_summary(df: pd.DataFrame) -> None:
    """Print a human-readable summary of fetched NAV data."""
    print(f"\n  Scheme  : {df['scheme_name'].iloc[0]}")
    print(f"  Code    : {df['amfi_code'].iloc[0]}")
    print(f"  Records : {len(df):,}")
    print(f"  Range   : {df['date'].iloc[0]} → {df['date'].iloc[-1]}")
    print(f"  NAV now : ₹{df['nav'].iloc[-1]:.4f}")
    print(f"  NAV min : ₹{df['nav'].min():.4f}  (on {df.loc[df['nav'].idxmin(),'date']})")
    print(f"  NAV max : ₹{df['nav'].max():.4f}  (on {df.loc[df['nav'].idxmax(),'date']})")

    # Simple point-to-point return
    nav_start = df["nav"].iloc[0]
    nav_end   = df["nav"].iloc[-1]
    total_ret = ((nav_end / nav_start) - 1) * 100
    print(f"  Return  : {total_ret:+.2f}% (inception to latest)")


# ──────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 60)
    print("  BLUESTOCK FINTECH — LIVE NAV FETCHER")
    print("=" * 60)
    print(f"  API      : {BASE_URL}")
    print(f"  Schemes  : {len(SCHEMES)}")
    print(f"  Output   : {RAW_DIR}")

    all_frames = []
    success_count = 0

    for code, name in SCHEMES.items():
        print(f"\n{'─'*60}")
        df = fetch_scheme(code, name)

        if df is not None:
            save_scheme_csv(df, code)
            print_nav_summary(df)
            all_frames.append(df)
            success_count += 1
        else:
            print(f"  ❌ Failed to fetch {code} — {name}")
            print("     Check your internet connection and retry.")

        # Be polite to the free public API
        if code != list(SCHEMES.keys())[-1]:
            time.sleep(REQUEST_DELAY)

    # ── Combined CSV ─────────────────────────────────────
    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
        combined_path = RAW_DIR / "live_nav_combined.csv"
        combined.to_csv(combined_path, index=False)

        print(f"\n{'='*60}")
        print(f"  ✅ Fetched {success_count}/{len(SCHEMES)} schemes successfully")
        print(f"  📦 Combined CSV: {combined_path.name}")
        print(f"  📐 Shape: {combined.shape[0]:,} rows × {combined.shape[1]} columns")
        print(f"\n  Breakdown by scheme:")
        print(combined.groupby("scheme_name")["nav"].count()
                       .rename("nav_records").to_string())
    else:
        print("\n  ❌ No data fetched. All API calls failed.")
        print("     Run this script from your local machine with internet access.")

    print(f"\n{'='*60}")
    print("  Live NAV fetch complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
