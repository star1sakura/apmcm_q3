# Semiconductor Policy Model – Problem 3

## What this project does
A partial-equilibrium model for APMCM Problem C (question 3) to assess U.S. semiconductor policies across high/mid/low-end chips and regions (US/CN/ROW), combining tariffs, subsidies, export controls, economic efficiency, and national security metrics.

## Data used (all local, no external fetch)
- `wash/output/`: cleaned panels (tariff_hs2/hs4, trade_export_panel, trade_duty_panel, exports_CN_sector, etc.).
- `external_data/USITC_DataWeb/hs6_value_qty/`: HS6 854231/232/239 total value+quantity.
- `external_data/USITC_DataWeb/hs6_value_qty_by_partner/`: HS6 854231/232/239 by country value+quantity (used to split CN vs ROW).
- `external_data/UN_Comtrade_semiconductor_trade/` (additional_csv): extra Comtrade CSVs (not core).
- `external_data/FRED … IPG3344S …/`: IPG index (optional).
- `external_data/…NAICS 3344…`: Census industry stats (not core in code).

## Key files
- `config.py`: paths, elasticities (USITC 1.7), R&D share (SIA 19.5%), defaults.
- `classification.py`: HS6-based H/M/L shares, ASP from value+qty, build flows (CN vs ROW).
- `calibration.py`: Armington weights, supply/demand shifters, R&D/tech init.
- `policy.py`: four scenarios (baseline, tariff_only, tariff_plus_subsidy, diff_by_chip) with time paths.
- `model_static.py`: single-period equilibrium solver.
- `model_dynamic.py`: R&D→tech, NSI, welfare.
- `simulate.py`: run scenarios, save CSV/plots; also sensitivity runner.
- `analysis_plots.py`: saves NSI/Welfare/GAP/US import share plots.
- `results/`: per-scenario CSVs and plots; `results/sensitivity_summary.csv` for sensitivity cases.

## How to run
```bash
python simulate.py
```
Outputs: CSVs in `results/` and PNG plots in `results/plots/`.

## Scenarios (four lines in plots)
- baseline: zero chip tariffs; high-end US→CN embargo proxy; baseline growth/feedback.
- tariff_only: global 10% + US↔CN tariffs escalating; demand stagnation; stronger tech feedback; US high-end R&D hit.
- tariff_plus_subsidy: CN tariffs 5/15/20 on H/M/L; subsidies ramp up; higher demand; R&D boost.
- diff_by_chip: high-end 0; CN mid/low tariffs ramp 10→20→30→40%; medium growth/feedback.

## Outputs to read
- `results/summary.csv`: discounted objectives.
- Per-scenario CSVs: NSI, Welfare, Obj_t, SAF_H/M/L, US_prod_*, US_import_from_CN_* and shares.
- Plots: NSI/Welfare/gap_H/import share (H/M/L) in `results/plots/`.
- `results/sensitivity_summary.csv`: two sensitivity cases (high/low tariff impact) vs four scenarios.

## Assumptions to disclose
- Policy paths (tariff/subsidy growth, demand growth, tech feedback, R&D penalties/bonuses) are scenario assumptions, not official timelines.
- Elasticities: Armington 1.7 (USITC NAICS 334413); others are reasonable defaults.
- R&D share 19.5% (SIA Factbook); H/M/L shares/ASP from HS6 value+qty; fallbacks only when data missing.
- Import value approximation in absence of prices: duty / MFN as a rough proxy.

## Caveats
- Numbers are for relative comparison; not calibrated to exact prices/cost curves.
- Gap_H may have limited separation under current settings; can be hidden or adjusted if needed.

## Next steps (optional)
- Use partner-level value+qty to refine CN vs ROW ASP and Armington weights further.
- Calibrate γ/A to match 2023 quantities/prices if more granular data available.
- Adjust policy paths/feedbacks per your narrative or run more sensitivity cases.
