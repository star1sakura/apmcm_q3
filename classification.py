"""
Utilities to classify HS items into high/mid/low chip buckets and derive rough
trade splits for the model.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import pandas as pd

import config
from data_loader import (
    load_cleaned_panels,
    load_dataweb_files,
    load_dataweb_value_qty,
    load_dataweb_partner_value_qty,
)

# Fraction of "other" 8542 lines assigned to mid-end when we lack finer
# information; the remainder goes to low-end.
OTHER_TO_MID_SHARE = 0.5
DEFAULT_ASP = {"H": 100.0, "M": 10.0, "L": 1.0}


def _parse_dataweb_values(path: Optional[str], year: int) -> Dict[str, float]:
    """
    Parse the DataWeb Excel (Query Results sheet) into a mapping
    {hs_code(str): customs_value}.
    """
    if not path:
        return {}
    xls = pd.read_excel(path, sheet_name="Query Results", header=None)
    # The sheet has a simple 5-column structure after the first header row.
    xls.columns = xls.iloc[0]
    df = xls.iloc[1:].copy()
    for col in ["Year", "Customs Value"]:
        if col not in df.columns:
            return {}
    df = df[df["Data Type"] == "Customs Value"]
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Customs Value"] = pd.to_numeric(df["Customs Value"], errors="coerce")
    df = df[df["Year"] == year]
    df["HTS Number"] = df["HTS Number"].astype(str).str.strip()
    values = (
        df.groupby("HTS Number")["Customs Value"]
        .sum()
        .to_dict()
    )
    return values


def estimate_chip_type_shares_from_dataweb(year: int = config.BASE_YEAR) -> Dict[str, float]:
    """
    Estimate alpha_H/M/L shares within HS8542 using DataWeb results if
    available; otherwise fall back to config.DEFAULT_ALPHA_HML.
    """
    paths = load_dataweb_files()
    export_path = paths.get("export")
    values = _parse_dataweb_values(str(export_path) if export_path else None, year)
    if not values:
        return config.DEFAULT_ALPHA_HML.copy()

    # Values for key HS6 lines
    v_231 = values.get("854231", 0.0)
    v_232 = values.get("854232", 0.0)
    v_other = sum(val for code, val in values.items() if str(code).startswith("8542") and code not in {"854231", "854232"})
    total = v_231 + v_232 + v_other
    if total <= 0:
        return config.DEFAULT_ALPHA_HML.copy()

    alpha_H = (v_231 + config.DEFAULT_HBM_SHARE * v_232) / total
    mid_from_mem = (1.0 - config.DEFAULT_HBM_SHARE) * v_232
    mid_from_other = OTHER_TO_MID_SHARE * v_other
    alpha_M = (mid_from_mem + mid_from_other) / total
    alpha_L = 1.0 - alpha_H - alpha_M

    return {"H": float(alpha_H), "M": float(alpha_M), "L": float(alpha_L)}


def compute_alpha_and_asp_from_value_qty(year: int = config.BASE_YEAR) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Use DataWeb value+quantity files (import/export) to compute:
      - alpha_H/M/L shares based on total value (import+export) for 854231/232/239
      - ASP (value/quantity) per chip type (average of import/export if both exist)
    """
    paths = load_dataweb_value_qty()
    if not paths:
        return config.DEFAULT_ALPHA_HML.copy(), DEFAULT_ASP.copy()

    def parse_file(path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
        df = pd.read_excel(path, sheet_name="Query Results", header=0)
        value_cols = [c for c in df.columns if "value" in str(c).lower() and "quantity" not in str(c).lower()]
        if not value_cols:
            raise ValueError(f"No value column found in {path}")
        val_col = value_cols[0]
        df_value = df[df["Data Type"].isin(["Customs Value", "FAS Value"])][["Data Type", "HTS Number", "Year", val_col]]
        df_value = df_value.rename(columns={val_col: "TradeValue"})
        df_qty = df[df["Data Type"].str.contains("Unit of Quantity", na=False)][["HTS Number", "Year", val_col]]
        df_qty = df_qty.rename(columns={val_col: "Quantity"})
        return df_value, df_qty

    values: Dict[str, float] = {"H": 0.0, "M": 0.0, "L": 0.0}
    qtys: Dict[str, float] = {"H": 0.0, "M": 0.0, "L": 0.0}

    for kind, path in paths.items():
        df_val, df_qty = parse_file(path)
        for hs, chip in [("854231", "H"), ("854232", "M"), ("854239", "L")]:
            v = df_val.loc[(df_val["HTS Number"] == int(hs)) & (df_val["Year"] == year), "TradeValue"].sum()
            q = df_qty.loc[(df_qty["HTS Number"] == int(hs)) & (df_qty["Year"] == year), "Quantity"].sum()
            values[chip] += float(v)
            qtys[chip] += float(q)

    total_value = sum(values.values())
    if total_value <= 0:
        alpha = config.DEFAULT_ALPHA_HML.copy()
    else:
        alpha = {k: (v / total_value) for k, v in values.items()}

    asp: Dict[str, float] = {}
    for chip in ["H", "M", "L"]:
        v = values[chip]
        q = qtys[chip]
        if q > 0:
            asp[chip] = v / q
        else:
            asp[chip] = DEFAULT_ASP[chip]
    return alpha, asp


def compute_partner_flows_and_asp(base_year: int = config.BASE_YEAR) -> Optional[Tuple[Dict[str, float], Dict[Tuple[str, str, str], float], Dict[str, float]]]:
    """
    Use partner-level value+quantity files to build:
      - alpha shares (H/M/L) based on total value
      - flows dict in quantities keyed by (origin, dest, chip_type)
      - ASP per chip_type (value/quantity)
    Partners are mapped to CN vs ROW.
    """
    paths = load_dataweb_partner_value_qty()
    if not paths:
        return None

    def parse_partner(path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
        df = pd.read_excel(path, sheet_name="Query Results", header=0)
        val_cols = [c for c in df.columns if "value" in str(c).lower() and "quantity" not in str(c).lower()]
        if not val_cols:
            raise ValueError(f"No value column in {path}")
        val_col = val_cols[0]
        df_val = df[df["Data Type"].str.contains("Value", na=False)][["Country", "Year", "HTS Number", val_col]]
        df_val = df_val.rename(columns={val_col: "TradeValue"})
        df_qty = df[df["Data Type"].str.contains("Unit of Quantity", na=False)][["Country", "Year", "HTS Number", val_col]]
        df_qty = df_qty.rename(columns={val_col: "Quantity"})
        return df_val, df_qty

    values = {"H": {}, "M": {}, "L": {}}
    qtys = {"H": {}, "M": {}, "L": {}}
    flows: Dict[Tuple[str, str, str], float] = {}

    def map_region(country: str) -> str:
        if isinstance(country, str) and country.lower().strip() == "china":
            return "CN"
        return "ROW"

    hs_to_chip = {"854231": "H", "854232": "M", "854239": "L"}

    for kind, path in paths.items():
        df_val, df_qty = parse_partner(path)
        df_val = df_val[df_val["Year"] == base_year]
        df_qty = df_qty[df_qty["Year"] == base_year]
        merge_df = pd.merge(df_val, df_qty, on=["Country", "Year", "HTS Number"], how="left")
        for _, row in merge_df.iterrows():
            hs = str(int(row["HTS Number"])).zfill(6)
            chip = hs_to_chip.get(hs)
            if chip is None:
                continue
            region = map_region(str(row["Country"]))
            val = float(row["TradeValue"])
            qty = float(row["Quantity"]) if pd.notna(row["Quantity"]) else 0.0
            values[chip][region] = values[chip].get(region, 0.0) + val
            qtys[chip][region] = qtys[chip].get(region, 0.0) + qty
            if kind == "import":
                key = (region, "US", chip)
            else:
                key = ("US", region, chip)
            if qty > 0:
                flows[key] = flows.get(key, 0.0) + qty

    # Compute alpha based on total value across regions
    total_value = sum(sum(v.values()) for v in values.values())
    if total_value <= 0:
        alpha = config.DEFAULT_ALPHA_HML.copy()
    else:
        alpha = {chip: sum(values[chip].values()) / total_value for chip in values}

    # Compute ASP per chip (using total value/qty)
    asp: Dict[str, float] = {}
    for chip in ["H", "M", "L"]:
        v = sum(values[chip].values())
        q = sum(qtys[chip].values())
        asp[chip] = v / q if q > 0 else DEFAULT_ASP[chip]

    return alpha, flows, asp


def split_trade_by_chip_type(trade_df: pd.DataFrame, value_col: str, alpha: Dict[str, float]) -> pd.DataFrame:
    """
    Split an aggregate trade dataframe into three chip types using share alpha.
    """
    records = []
    for _, row in trade_df.iterrows():
        for chip, share in alpha.items():
            rec = row.to_dict()
            rec["chip_type"] = chip
            rec[value_col] = row[value_col] * share
            records.append(rec)
    return pd.DataFrame.from_records(records)


def construct_us_region_flows(
    base_year: int = config.BASE_YEAR,
    use_sector: str = "electrical_equipment",
    asp: Optional[Dict[str, float]] = None,
) -> Dict[Tuple[str, str, str], float]:
    """
    Build a coarse mapping of trade flows (origin -> destination -> chip_type)
    using cleaned DataWeb panels.  Origin is restricted to the US; flows are
    split into CN and ROW partners.  This is primarily used to seed Armington
    weights; when missing, the calibration falls back to symmetric defaults.
    """
    cleaned = load_cleaned_panels()
    trade_export = cleaned["trade_export_panel"]
    trade_duty = cleaned["trade_duty_panel"]
    partner_result = compute_partner_flows_and_asp(base_year)
    if partner_result:
        alpha, flows_prefill, alpha_asp = partner_result
    else:
        alpha, alpha_asp = compute_alpha_and_asp_from_value_qty(base_year)
        flows_prefill = {}
    if asp is None:
        asp = alpha_asp

    flows: Dict[Tuple[str, str, str], float] = {}

    if partner_result:
        flows.update(flows_prefill)

    if not trade_export.empty and not partner_result:
        exp = trade_export.copy()
        exp = exp[exp["year"] == base_year]
        if use_sector and "sector_big" in exp.columns:
            exp = exp[exp["sector_big"] == use_sector]
        exp["partner_norm"] = exp["partner_name"].str.lower()
        exp["region_dest"] = exp["partner_norm"].apply(
            lambda x: "CN" if isinstance(x, str) and "china" in x else "ROW"
        )
        for (_, g) in exp.groupby("region_dest"):
            split = split_trade_by_chip_type(g, "export_fas", alpha)
            for _, r in split.iterrows():
                key = ("US", r["region_dest"], r["chip_type"])
                qty_val = float(r["export_fas"])
                q = qty_val / max(asp.get(r["chip_type"], 1.0), config.EPS)
                flows[key] = flows.get(key, 0.0) + q

    if not trade_duty.empty and not partner_result:
        imp = trade_duty.copy()
        imp = imp[imp["year"] == base_year]
        if use_sector and "sector_big" in imp.columns:
            imp = imp[imp["sector_big"] == use_sector]
        imp["partner_norm"] = imp["partner_name"].str.lower()
        imp["region_orig"] = imp["partner_norm"].apply(
            lambda x: "CN" if isinstance(x, str) and "china" in x else "ROW"
        )
        # Approximate import value from duty / ad valorem rate (guard against zero)
        mfn = imp.get("mfn_adval_hs2", pd.Series(0.05, index=imp.index)).fillna(0.05)
        imp_value = imp["import_duty"] / mfn.replace(0, 0.01)
        imp = imp.assign(import_value=imp_value)
        for (_, g) in imp.groupby("region_orig"):
            split = split_trade_by_chip_type(g, "import_value", alpha)
            for _, r in split.iterrows():
                key = (r["region_orig"], "US", r["chip_type"])
                qty_val = float(r["import_value"])
                q = qty_val / max(asp.get(r["chip_type"], 1.0), config.EPS)
                flows[key] = flows.get(key, 0.0) + q

    return flows


__all__ = [
    "estimate_chip_type_shares_from_dataweb",
    "split_trade_by_chip_type",
    "construct_us_region_flows",
]
