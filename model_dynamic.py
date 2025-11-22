"""
Dynamic blocks: sales/R&D/technology updates, national security metrics, and a
simple welfare calculator.
"""

from __future__ import annotations

from math import log
from typing import Dict, Tuple

import config

PriceKey = Tuple[str, str]
TradeKey = Tuple[str, str, str]


def compute_sales(prices: Dict[PriceKey, float], Q_prod: Dict[PriceKey, float]) -> Dict[PriceKey, float]:
    return {(i, s): prices[(i, s)] * Q_prod[(i, s)] for (i, s) in Q_prod}


def update_rd_and_tech(prev_T, sales, rd_intensity, world_sales=None):
    new_T: Dict[PriceKey, float] = {}
    RD: Dict[PriceKey, float] = {}
    # Compute world sales per chip type for scaling
    world_sales_type: Dict[str, float] = {s: 0.0 for s in config.CHIP_TYPES}
    for (i, s), v in sales.items():
        world_sales_type[s] += v

    for i in config.REGIONS:
        for s in config.CHIP_TYPES:
            rho = rd_intensity[i][s]
            S_is = sales.get((i, s), 0.0)
            RD[(i, s)] = rho * S_is
            phi = config.TECH_PROGRESS_COEF[s]
            base = prev_T[(i, s)]
            denom = world_sales_type[s] + config.EPS
            new_T[(i, s)] = base * (1.0 + phi * RD[(i, s)] / denom)
    return {"T": new_T, "RD": RD}


def compute_supply_security(Q_trade: Dict[TradeKey, float], Q_cons: Dict[Tuple[str, str], float]) -> Dict[str, float]:
    SAF: Dict[str, float] = {}
    for s in config.CHIP_TYPES:
        risk_import = Q_trade.get(("CN", "US", s), 0.0)
        cons_us = Q_cons.get(("US", s), risk_import + config.EPS)
        SAF[s] = 1.0 - risk_import / cons_us
    return SAF


def compute_tech_gap(T: Dict[PriceKey, float]) -> float:
    return log((T[("US", "H")] + config.EPS) / (T[("CN", "H")] + config.EPS))


def compute_national_security_index(SAF: Dict[str, float], gap_H: float) -> float:
    nsi = 0.0
    for s in config.CHIP_TYPES:
        nsi += config.SECURITY_WEIGHTS[s] * SAF.get(s, 0.0)
    nsi += config.TECH_GAP_WEIGHT * gap_H
    return nsi


def compute_welfare(static_result, epsilon, supply_eta, subsidy_cost, rd_cost):
    # Consumer surplus approximation (isoelastic)
    CS = 0.0
    for (j, s), q in static_result["consumption"].items():
        p = static_result["consumption_price"][(j, s)]
        eps = epsilon[j][s]
        if eps > 1:
            CS += q * p / (eps - 1.0)
    # Producer surplus approximation from supply curve P = (Q/g)^{1/eta}
    PS = 0.0
    for (i, s), q in static_result["Q_prod"].items():
        p = static_result["prices"][(i, s)]
        eta = supply_eta[i][s]
        PS += (eta / (eta + 1.0)) * p * q

    gov_rev = static_result["gov_revenue"]
    W = CS + PS + gov_rev - subsidy_cost - rd_cost
    return W


__all__ = [
    "compute_sales",
    "update_rd_and_tech",
    "compute_supply_security",
    "compute_tech_gap",
    "compute_national_security_index",
    "compute_welfare",
]

