"""
Data loading and lightweight preprocessing utilities.

The loader prefers the cleaned CSV outputs in ``wash/output``. When available,
it will also read supporting raw files (DataWeb HS6 exports/imports, IPG index,
Comtrade 8542 flows) from ``external_data`` (excluding the reports folder) to
enrich calibration; all of these paths are resolved robustly via substring
matching to cope with non-ASCII folder names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd

import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_path_with_keyword(base: Path, keywords: Iterable[str], suffix: Optional[str] = None) -> Optional[Path]:
    """
    Locate a child path whose name contains all substrings in ``keywords``.
    Optionally enforce a suffix (file extension).
    """
    if not base.exists():
        return None
    for p in base.iterdir():
        name_lower = p.name.lower()
        if all(k.lower() in name_lower for k in keywords):
            if suffix is None or name_lower.endswith(suffix.lower()):
                return p
    return None


# ---------------------------------------------------------------------------
# Cleaned data loaders
# ---------------------------------------------------------------------------

def load_cleaned_panels(data_dir: Path = config.CLEAN_DATA_DIR) -> Dict[str, pd.DataFrame]:
    """
    Load the cleaned CSV artifacts produced by ``wash/datawash.py``.
    """
    files = {
        "tariff_hs4_panel": "tariff_hs4_panel.csv",
        "tariff_hs2_panel": "tariff_hs2_panel.csv",
        "trade_export_panel": "trade_export_panel.csv",
        "trade_duty_panel": "trade_duty_panel.csv",
        "exports_CN_sector": "exports_CN_sector.csv",
        "duty_total_year": "duty_total_year.csv",
    }
    out: Dict[str, pd.DataFrame] = {}
    for key, fname in files.items():
        fpath = data_dir / fname
        if fpath.exists():
            out[key] = pd.read_csv(fpath)
        else:
            out[key] = pd.DataFrame()
    return out


# ---------------------------------------------------------------------------
# Raw supporting data (best-effort)
# ---------------------------------------------------------------------------

def load_ipg_index(raw_dir: Path = config.RAW_DATA_DIR) -> pd.DataFrame:
    """
    Load the FRED IPG3344S monthly index; returns empty DF if not found.
    """
    fred_dir = None
    for p in raw_dir.iterdir():
        if "fred" in p.name.lower():
            fred_dir = p
            break
    if fred_dir:
        ipg_path = fred_dir / "IPG3344S.csv"
        if ipg_path.exists():
            return pd.read_csv(ipg_path)
    return pd.DataFrame()


def load_ipg_annual_mean(ipg_df: pd.DataFrame) -> Dict[int, float]:
    """
    Compute annual mean values of IPG index if available.
    """
    if ipg_df.empty:
        return {}
    df = ipg_df.copy()
    # Expect columns: DATE, IPG3344S
    date_col = None
    value_col = None
    for c in df.columns:
        if "date" in c.lower():
            date_col = c
        if "ipg" in c.lower():
            value_col = c
    if date_col is None or value_col is None:
        return {}
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=[date_col, value_col])
    df["year"] = df[date_col].dt.year
    annual = df.groupby("year")[value_col].mean().to_dict()
    return {int(k): float(v) for k, v in annual.items()}


def load_dataweb_files(raw_dir: Path = config.RAW_DATA_DIR) -> Dict[str, Path]:
    """
    Locate DataWeb export/import Excel files under the raw data directory.
    """
    base = None
    for p in raw_dir.iterdir():
        if "dataweb" in p.name.lower():
            base = p
            break
    if base is None or not base.exists():
        return {}
    export_path = _find_path_with_keyword(base, ["export"], suffix=".xlsx")
    import_path = _find_path_with_keyword(base, ["import"], suffix=".xlsx")
    out: Dict[str, Path] = {}
    if export_path:
        out["export"] = export_path
    if import_path:
        out["import"] = import_path
    return out


def load_comtrade_files(raw_dir: Path = config.RAW_DATA_DIR) -> Dict[str, Path]:
    """
    Locate UN Comtrade CSV files (the ones containing 'TradeData_').
    """
    target_dir = None
    for p in raw_dir.iterdir():
        if "comtrade" in p.name.lower():
            target_dir = p
            break
    if target_dir is None:
        return {}
    paths = list(target_dir.glob("TradeData_*.csv"))
    return {p.name: p for p in paths}


# ---------------------------------------------------------------------------
# Combined preprocessing
# ---------------------------------------------------------------------------

def preprocess_all() -> Dict[str, object]:
    """
    Aggregate all readily available data sources into a single dictionary:
      - cleaned panels from wash/output
      - IPG index (if found)
      - IPG annual mean (if found)
      - DataWeb file handles (if found)
      - Comtrade file handles (if found)
    """
    cleaned = load_cleaned_panels()
    ipg = load_ipg_index()
    ipg_annual = load_ipg_annual_mean(ipg)
    dataweb_paths = load_dataweb_files()
    comtrade_paths = load_comtrade_files()

    return {
        "clean": cleaned,
        "ipg": ipg,
        "ipg_annual": ipg_annual,
        "dataweb_paths": dataweb_paths,
        "comtrade_paths": comtrade_paths,
    }


__all__ = [
    "preprocess_all",
    "load_cleaned_panels",
    "load_ipg_index",
    "load_dataweb_files",
    "load_comtrade_files",
    "load_dataweb_value_qty",
    "load_dataweb_partner_value_qty",
]


def load_dataweb_value_qty(raw_dir: Path = config.RAW_DATA_DIR) -> Dict[str, Path]:
    """
    Locate DataWeb HS6 value+quantity files under the unified USITC_DataWeb folder.
    """
    base = raw_dir / "USITC_DataWeb" / "hs6_value_qty"
    paths: Dict[str, Path] = {}
    if base.is_dir():
        imp = base / "DataWeb_Import_85423x_value_qty.xlsx"
        exp = base / "DataWeb_Export_85423x_value_qty.xlsx"
        if imp.exists():
            paths["import"] = imp
        if exp.exists():
            paths["export"] = exp
    return paths


def load_dataweb_partner_value_qty(raw_dir: Path = config.RAW_DATA_DIR) -> Dict[str, Path]:
    """
    Locate partner-level DataWeb HS6 value+quantity files (import/export).
    Expected folder: external_data/USITC_DataWeb/hs6_value_qty_by_partner
    """
    base = raw_dir / "USITC_DataWeb" / "hs6_value_qty_by_partner"
    paths: Dict[str, Path] = {}
    if base.is_dir():
        imp = base / "DataWeb_Import_by_country_85423x.xlsx"
        exp = base / "DataWeb_Export_by_country_85423x.xlsx"
        if imp.exists():
            paths["import"] = imp
        if exp.exists():
            paths["export"] = exp
    return paths
