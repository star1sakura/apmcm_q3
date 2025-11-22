"""
Policy scenario definitions: tariff schedules, subsidies, and export-control
proxies.
"""

from __future__ import annotations

from typing import Dict, Tuple

import config

ScenarioName = str
TariffKey = Tuple[str, str, str]  # (importer, chip_type, exporter)


def scenario_baseline(year: int) -> Dict[TariffKey, float]:
    """
    Baseline: MFN=0 on chips, existing high-end embargo (approximated by a
    prohibitive tariff on US->CN high-end).
    """
    tau: Dict[TariffKey, float] = {}
    for j in config.REGIONS:
        for i in config.REGIONS:
            if i == j:
                continue
            for s in config.CHIP_TYPES:
                tau[(j, s, i)] = 0.0
    tau[("CN", "H", "US")] = config.VERY_LARGE_TARIFF
    return tau


def scenario_tariff_only(year: int) -> Dict[TariffKey, float]:
    """
    Reciprocal tariffs replace subsidies with an escalating path on US<->CN:
      - 10% baseline on everyone
      - US<->CN starts at 30% (2023/2024) and adds +10pp per year from 2025, capped at 80%
      - Stronger friction intended to widen high-end tech gap under de-risking
    """
    tau: Dict[TariffKey, float] = {}
    extra_cn = 0.20  # 20% means 30% total (base 10 + extra 20)
    if year >= 2025:
        extra_cn += 0.10 * (year - 2024)
        extra_cn = min(extra_cn, 0.70)  # extra 70% + base 10% = 80% cap
    for j in config.REGIONS:
        for i in config.REGIONS:
            if i == j:
                continue
            for s in config.CHIP_TYPES:
                base = 0.10
                extra = 0.0
                if (j == "US" and i == "CN") or (j == "CN" and i == "US"):
                    extra = extra_cn
                tau[(j, s, i)] = base + extra
    return tau


def scenario_tariff_plus_subsidy(year: int) -> Dict[str, object]:
    """
    Keep subsidies and add moderate tariffs to China on mid/low-end imports.
    """
    tau = scenario_baseline(year)
    # Moderate tariff on CN mid/low, mild on high-end to reflect targeted friction
    tau[("US", "H", "CN")] = 0.05
    tau[("US", "M", "CN")] = 0.15
    tau[("US", "L", "CN")] = 0.20
    # Ramp subsidies over time to reflect CHIPS disbursement (stronger ramps for high-end)
    if year >= 2027:
        subsidy_h, subsidy_m = 0.15, 0.08
    elif year >= 2025:
        subsidy_h, subsidy_m = 0.12, 0.07
    else:
        subsidy_h, subsidy_m = 0.10, 0.06
    subsidy: Dict[Tuple[str, str], float] = {("US", "H"): subsidy_h, ("US", "M"): subsidy_m}
    return {"tau": tau, "subsidy": subsidy}


def scenario_diff_by_chip_type(year: int) -> Dict[TariffKey, float]:
    """
    Zero tariffs on high-end (preserve supply chains with allies), higher
    tariffs on Chinese mid/low-end to strengthen legacy supply security.
    """
    tau: Dict[TariffKey, float] = {}
    # Mid/low CN tariffs ramp from 10% -> 40% over time
    if year >= 2027:
        ramp = 0.30  # extra, base=0, so 30%
    elif year >= 2025:
        ramp = 0.20
    else:
        ramp = 0.10
    if year >= 2029:
        ramp = 0.40
    for j in config.REGIONS:
        for i in config.REGIONS:
            if i == j:
                continue
            for s in config.CHIP_TYPES:
                if s == "H":
                    tau[(j, s, i)] = 0.0
                else:
                    extra = ramp if (j == "US" and i == "CN") else 0.0
                    tau[(j, s, i)] = extra
    return tau


SCENARIO_FUNC_MAP = {
    "baseline": scenario_baseline,
    "tariff_only": scenario_tariff_only,
    "tariff_plus_subsidy": scenario_tariff_plus_subsidy,
    "diff_by_chip": scenario_diff_by_chip_type,
    "subsidy_only": lambda year: scenario_tariff_plus_subsidy(year) | {"tau": scenario_baseline(year)},
}


__all__ = ["SCENARIO_FUNC_MAP"]
