"""
Single-period partial equilibrium solver for the chip trade model.

We use a damped fixed-point iteration on prices: given prices, compute supply,
CES demand, Armington allocation, and adjust prices proportional to the supply
surplus/shortage until markets clear.
"""

from __future__ import annotations

from typing import Dict, Tuple, Any

import numpy as np

import config

PriceKey = Tuple[str, str]          # (region, chip_type)
TradeKey = Tuple[str, str, str]     # (origin, dest, chip_type)


def _prices_with_tariff(prices: Dict[PriceKey, float], tau: Dict[Tuple[str, str, str], float]) -> Dict[TradeKey, float]:
    out: Dict[TradeKey, float] = {}
    for i in config.REGIONS:
        for j in config.REGIONS:
            for s in config.CHIP_TYPES:
                base_p = prices[(i, s)]
                t = tau.get((j, s, i), 0.0)
                out[(i, j, s)] = base_p * (1.0 + t)
    return out


def _ces_consumption_price(beta: Dict[Tuple[str, str, str], float], sigma: Dict[str, float], prices_with_tau: Dict[TradeKey, float]) -> Dict[Tuple[str, str], float]:
    P_cons: Dict[Tuple[str, str], float] = {}
    for j in config.REGIONS:
        for s in config.CHIP_TYPES:
            sig = sigma[s]
            agg = 0.0
            for i in config.REGIONS:
                b = beta.get((i, j, s), 0.0)
                pij = prices_with_tau[(i, j, s)]
                agg += b * (pij ** (1.0 - sig))
            P_cons[(j, s)] = agg ** (1.0 / (1.0 - sig))
    return P_cons


def _compute_consumption(A: Dict[Tuple[str, str], float], epsilon: Dict[str, Dict[str, float]], P_cons: Dict[Tuple[str, str], float]) -> Dict[Tuple[str, str], float]:
    Q_cons: Dict[Tuple[str, str], float] = {}
    for j in config.REGIONS:
        for s in config.CHIP_TYPES:
            eps = epsilon[j][s]
            A_js = A[(j, s)]
            p = P_cons[(j, s)]
            Q_cons[(j, s)] = A_js * (p ** (-eps))
    return Q_cons


def _allocate_armington(beta: Dict[Tuple[str, str, str], float], sigma: Dict[str, float], Q_cons: Dict[Tuple[str, str], float], prices_with_tau: Dict[TradeKey, float]) -> Dict[TradeKey, float]:
    flows: Dict[TradeKey, float] = {}
    for j in config.REGIONS:
        for s in config.CHIP_TYPES:
            sig = sigma[s]
            denom = 0.0
            weight: Dict[str, float] = {}
            for i in config.REGIONS:
                b = beta.get((i, j, s), 0.0)
                pij = prices_with_tau[(i, j, s)]
                weight[i] = b * (pij ** (1.0 - sig))
                denom += weight[i]
            for i in config.REGIONS:
                share = 0.0 if denom == 0 else weight[i] / denom
                flows[(i, j, s)] = share * Q_cons[(j, s)]
    return flows


def solve_static_equilibrium(params: Dict[str, Any], policy_t: Dict[str, Any], max_iter: int = 200, tol: float = 1e-4) -> Dict[str, Any]:
    """
    Solve for prices, production, trade flows, and implied consumption given
    parameters and a policy (tariffs + optional subsidies).
    """
    tau = policy_t.get("tau", {})
    subsidy = policy_t.get("subsidy", {})

    beta = params["beta"]
    sigma = params["sigma"]
    A = params["A"]
    epsilon = params["epsilon"]
    gamma = params["gamma"]
    eta = params["supply_eta"]

    base_price = params.get("base_price", {"H": 1.0, "M": 1.0, "L": 1.0})
    prices: Dict[PriceKey, float] = {(i, s): base_price.get(s, 1.0) for i in config.REGIONS for s in config.CHIP_TYPES}

    for _ in range(max_iter):
        prices_tau = _prices_with_tariff(prices, tau)
        P_cons = _ces_consumption_price(beta, sigma, prices_tau)
        Q_cons = _compute_consumption(A, epsilon, P_cons)
        Q_trade = _allocate_armington(beta, sigma, Q_cons, prices_tau)

        # Supply
        Q_prod: Dict[PriceKey, float] = {}
        for i in config.REGIONS:
            for s in config.CHIP_TYPES:
                g = gamma[(i, s)]
                sub = subsidy.get((i, s), 0.0)
                e = eta[i][s]
                Q_prod[(i, s)] = g * ((prices[(i, s)] + sub) ** e)

        # Market clearing gap
        max_gap = 0.0
        new_prices = prices.copy()
        for i in config.REGIONS:
            for s in config.CHIP_TYPES:
                exports = sum(v for (o, d, ss), v in Q_trade.items() if o == i and ss == s)
                gap = Q_prod[(i, s)] - exports
                rel_gap = gap / (Q_prod[(i, s)] + config.EPS)
                max_gap = max(max_gap, abs(rel_gap))
                # Price update (damped)
                step = 0.3
                new_prices[(i, s)] = max(0.05, prices[(i, s)] * (1.0 - step * rel_gap))
        prices = new_prices
        if max_gap < tol:
            break

    # Final recompute with converged prices
    prices_tau = _prices_with_tariff(prices, tau)
    P_cons = _ces_consumption_price(beta, sigma, prices_tau)
    Q_cons = _compute_consumption(A, epsilon, P_cons)
    Q_trade = _allocate_armington(beta, sigma, Q_cons, prices_tau)
    Q_prod = {}
    for i in config.REGIONS:
        for s in config.CHIP_TYPES:
            g = gamma[(i, s)]
            sub = subsidy.get((i, s), 0.0)
            e = eta[i][s]
            Q_prod[(i, s)] = g * ((prices[(i, s)] + sub) ** e)

    gov_rev = 0.0
    for (i, j, s), q in Q_trade.items():
        if i == j:
            continue
        t = tau.get((j, s, i), 0.0)
        gov_rev += t * prices[(i, s)] * q

    return {
        "prices": prices,
        "prices_with_tariff": prices_tau,
        "consumption_price": P_cons,
        "Q_prod": Q_prod,
        "Q_trade": Q_trade,
        "consumption": Q_cons,
        "gov_revenue": gov_rev,
    }


__all__ = ["solve_static_equilibrium"]
