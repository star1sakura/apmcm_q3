"""
Lightweight calibration routines. The goal is to derive a consistent set of
Armington weights, demand scales, supply shifters, and initial technology/R&D
levels using available cleaned data; when data are missing the code falls back
to reasonable defaults encoded in ``config``.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import config
from classification import construct_us_region_flows, compute_alpha_and_asp_from_value_qty
from data_loader import preprocess_all


def calibrate_armington_shares(flows: Dict[Tuple[str, str, str], float]) -> Dict[Tuple[str, str, str], float]:
    """
    Build Armington weights beta_{origin, dest, chip} using observed trade
    shares when available; otherwise fall back to symmetric weights with a
    domestic bias.
    """
    beta: Dict[Tuple[str, str, str], float] = {}
    for dest in config.REGIONS:
        for s in config.CHIP_TYPES:
            # observed import shares into dest
            obs = {orig: flows.get((orig, dest, s), 0.0) for orig in config.REGIONS if orig != dest}
            total_obs = sum(obs.values())
            dom_share = config.DEFAULT_DOMESTIC_SHARE
            if total_obs > 0:
                for orig, val in obs.items():
                    beta[(orig, dest, s)] = val / total_obs * (1.0 - dom_share)
            else:
                for orig in config.REGIONS:
                    if orig == dest:
                        continue
                    beta[(orig, dest, s)] = (1.0 - dom_share) / (len(config.REGIONS) - 1)
            beta[(dest, dest, s)] = dom_share
    return beta


def calibrate_supply_and_demand(flows: Dict[Tuple[str, str, str], float], ipg_annual: Dict[int, float]) -> Dict[str, Any]:
    """
    Calibrate supply shifters gamma and demand scales A using trade flows as
    rough anchors. Prices are taken from ASP if available.
    """
    _, asp = compute_alpha_and_asp_from_value_qty()
    P_base_map = asp
    gamma: Dict[Tuple[str, str], float] = {}
    demand_A: Dict[Tuple[str, str], float] = {}
    production_guess: Dict[Tuple[str, str], float] = {}

    for i in config.REGIONS:
        for s in config.CHIP_TYPES:
            outward = sum(v for (o, d, ss), v in flows.items() if o == i and ss == s and d != i)
            inbound = sum(v for (o, d, ss), v in flows.items() if d == i and ss == s and o != i)
            base = outward + inbound
            if base <= 0:
                base = 1.0
            production_guess[(i, s)] = base

    # If IPG index is available, scale US production by annual mean (relative to 100)
    ipg_val = ipg_annual.get(config.BASE_YEAR)
    if ipg_val:
        scale = ipg_val / 100.0
        for s in config.CHIP_TYPES:
            production_guess[("US", s)] *= scale

    for i in config.REGIONS:
        for s in config.CHIP_TYPES:
            Q_prod = production_guess[(i, s)]
            eta = config.DEFAULT_SUPPLY_ELASTICITY[i][s]
            gamma[(i, s)] = Q_prod / ((P_base_map.get(s, 1.0)) ** eta)

    for j in config.REGIONS:
        for s in config.CHIP_TYPES:
            exports_out = sum(v for (o, d, ss), v in flows.items() if o == j and d != j and ss == s)
            imports_in = sum(v for (o, d, ss), v in flows.items() if d == j and o != j and ss == s)
            prod_j = production_guess.get((j, s), 1.0)
            domestic_use = max(prod_j - exports_out, 0.0)
            cons = domestic_use + imports_in
            if cons <= 0:
                cons = max(prod_j, 1.0)
            eps = config.DEFAULT_EPSILON[j][s]
            demand_A[(j, s)] = cons / ((P_base_map.get(s, 1.0)) ** (-eps))

    return {"gamma": gamma, "demand_A": demand_A, "production_guess": production_guess, "base_price": P_base_map}


def calibrate_rd_and_tech(production_guess: Dict[Tuple[str, str], float]) -> Dict[str, Any]:
    """
    Initialise R&D spending and technology levels at the base year.
    """
    RD: Dict[Tuple[str, str], float] = {}
    T: Dict[Tuple[str, str], float] = {}
    for i in config.REGIONS:
        for s in config.CHIP_TYPES:
            sales = production_guess.get((i, s), 1.0)
            rho = config.DEFAULT_RD_INTENSITY[i][s]
            RD[(i, s)] = rho * sales
            T[(i, s)] = config.TECH_INITIAL_LEVEL[i][s]
    return {"RD": RD, "T": T}


def run_full_calibration() -> Dict[str, Any]:
    """
    Convenience wrapper to build all calibration pieces.
    """
    data = preprocess_all()
    ipg_annual = data.get("ipg_annual", {})
    flows = construct_us_region_flows()
    beta = calibrate_armington_shares(flows)
    sd = calibrate_supply_and_demand(flows, ipg_annual)
    rd_tech = calibrate_rd_and_tech(sd["production_guess"])

    return {
        "beta": beta,
        "gamma": sd["gamma"],
        "A": sd["demand_A"],
        "production_guess": sd["production_guess"],
        "rd_initial": rd_tech["RD"],
        "tech_initial": rd_tech["T"],
        "sigma": config.DEFAULT_SIGMA,
        "epsilon": config.DEFAULT_EPSILON,
        "supply_eta": config.DEFAULT_SUPPLY_ELASTICITY,
        "rd_intensity": config.DEFAULT_RD_INTENSITY,
        "base_price": sd.get("base_price", {"H": 1.0, "M": 1.0, "L": 1.0}),
    }


__all__ = ["run_full_calibration"]
