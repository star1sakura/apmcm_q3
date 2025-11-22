"""
Main simulation entry points.  Run dynamic scenarios over SIM_YEARS and
collect welfare / national security trajectories.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
from pathlib import Path

import pandas as pd

import config
from calibration import run_full_calibration
from model_static import solve_static_equilibrium
from model_dynamic import (
    compute_sales,
    update_rd_and_tech,
    compute_supply_security,
    compute_tech_gap,
    compute_national_security_index,
    compute_welfare,
)
from policy import SCENARIO_FUNC_MAP
from analysis_plots import save_all_plots


def run_scenario(scenario_name: str) -> Dict[str, Any]:
    return run_scenario_with_maps(
        scenario_name,
        demand_growth_map=None,
        tech_feedback_map=None,
        rd_hit_map=None,
    )


def run_scenario_with_maps(
    scenario_name: str,
    demand_growth_map: Optional[Dict[str, float]],
    tech_feedback_map: Optional[Dict[str, float]],
    rd_hit_map: Optional[Dict[str, Dict[str, float]]],
) -> Dict[str, Any]:
    params = run_full_calibration()
    state_T = params["tech_initial"]
    rd_intensity = params["rd_intensity"]
    gamma_curr = params["gamma"].copy()
    A_curr = params["A"].copy()
    prev_T = state_T.copy()

    history: Dict[str, Any] = {
        "year": [],
        "NSI": [],
        "Welfare": [],
        "Obj_t": [],
        "T": [],
        "security": [],
        "gap_H": [],
        "us_prod": [],
        "us_import_cn": [],
        "us_import_cn_share": [],
    }

    scenario_func = SCENARIO_FUNC_MAP[scenario_name]
    discounted_obj = 0.0

    # Scenario-specific demand growth and tech feedback multipliers
    default_dg = {
        "baseline": 0.02,
        "tariff_only": 0.0,
        "tariff_plus_subsidy": 0.025,
        "diff_by_chip": 0.012,
    }
    default_tf = {
        "baseline": 1.0,
        "tariff_only": 2.0,
        "tariff_plus_subsidy": 1.5,
        "diff_by_chip": 1.3,
    }
    demand_growth_map = demand_growth_map or default_dg
    tech_feedback_map = tech_feedback_map or default_tf

    demand_growth = demand_growth_map.get(scenario_name, config.DEMAND_GROWTH_RATE)
    tech_feedback_scale = tech_feedback_map.get(scenario_name, 1.0)

    for t_idx, year in enumerate(config.SIM_YEARS):
        policy_raw = scenario_func(year)
        if isinstance(policy_raw, dict) and "tau" in policy_raw:
            tau = policy_raw["tau"]
            subsidy = policy_raw.get("subsidy", {})
        else:
            tau = policy_raw
            subsidy = {}
        policy_t = {"tau": tau, "subsidy": subsidy}

        # Apply demand growth for current year
        growth = 1.0 + demand_growth
        A_curr = {k: v * growth for k, v in A_curr.items()}

        # Use current gamma and A for this year's equilibrium
        params_year = params.copy()
        params_year["gamma"] = gamma_curr
        params_year["A"] = A_curr

        static_result = solve_static_equilibrium(params_year, policy_t)
        prices = static_result["prices"]
        Q_prod = static_result["Q_prod"]
        Q_trade = static_result["Q_trade"]
        Q_cons = static_result["consumption"]

        sales = compute_sales(prices, Q_prod)
        rd_tech = update_rd_and_tech(state_T, sales, rd_intensity)
        state_T = rd_tech["T"]
        RD_t = rd_tech["RD"]

        # Scenario-specific RD adjustment from map
        rd_map = rd_hit_map or {
            "tariff_only": {"H": 0.7, "M": 0.85},
            "tariff_plus_subsidy": {"H": 1.10, "M": 1.05},
            "diff_by_chip": {},
            "baseline": {},
        }
        if scenario_name in rd_map:
            for chip, mult in rd_map[scenario_name].items():
                key = ("US", chip)
                if key in RD_t:
                    RD_t[key] *= mult

        SAF = compute_supply_security(Q_trade, Q_cons)
        gap_H = compute_tech_gap(state_T)
        NSI_t = compute_national_security_index(SAF, gap_H)

        rd_cost = sum(RD_t.values())
        subsidy_cost = sum(subsidy.get((i, s), 0.0) * Q_prod[(i, s)] for (i, s) in Q_prod)
        W_t = compute_welfare(static_result, params["epsilon"], params["supply_eta"], subsidy_cost, rd_cost)

        Obj_t = W_t + config.SECURITY_VS_WELFARE * NSI_t
        discounted_obj += (config.DISCOUNT ** t_idx) * Obj_t

        history["year"].append(year)
        history["NSI"].append(NSI_t)
        history["Welfare"].append(W_t)
        history["Obj_t"].append(Obj_t)
        history["T"].append(state_T.copy())
        history["security"].append(SAF)
        history["gap_H"].append(gap_H)

        # Store US production and US imports from CN by chip type
        us_prod = {s: Q_prod.get(("US", s), 0.0) for s in config.CHIP_TYPES}
        us_import_cn = {s: Q_trade.get(("CN", "US", s), 0.0) for s in config.CHIP_TYPES}
        us_import_cn_share = {
            s: (us_import_cn[s] / (Q_cons.get(("US", s), 1e-9))) for s in config.CHIP_TYPES
        }
        history["us_prod"].append(us_prod)
        history["us_import_cn"].append(us_import_cn)
        history["us_import_cn_share"].append(us_import_cn_share)

        # Update supply shifters for next year based on tech progress
        gamma_next = {}
        for (i, s), g in gamma_curr.items():
            ratio = state_T[(i, s)] / (prev_T[(i, s)] + config.EPS)
            mult = 1.0 + tech_feedback_scale * config.TECH_FEEDBACK_SUPPLY * (ratio - 1.0)
            gamma_next[(i, s)] = g * mult
        gamma_curr = gamma_next
        prev_T = state_T.copy()

    history["discounted_obj"] = discounted_obj
    return history


def run_all_scenarios() -> Dict[str, Any]:
    results = {}
    for scen in SCENARIO_FUNC_MAP.keys():
        results[scen] = run_scenario(scen)
    return results


def run_sensitivity_factors(factors) -> Dict[str, Any]:
    """
    factors: dict of name -> overrides dict for config-like params:
      {"demand_growth": val, "tech_feedback": val, "rd_hit_US_H": val, "rd_hit_US_M": val}
    """
    base_params = {
        "demand_growth_map": {
            "baseline": 0.02,
            "tariff_only": 0.0,
            "tariff_plus_subsidy": 0.025,
            "diff_by_chip": 0.012,
        },
        "tech_feedback_map": {
            "baseline": 1.0,
            "tariff_only": 2.0,
            "tariff_plus_subsidy": 1.5,
            "diff_by_chip": 1.3,
        },
        "rd_hit": {
            "tariff_only": {"H": 0.7, "M": 0.85},
            "tariff_plus_subsidy": {"H": 1.10, "M": 1.05},
            "diff_by_chip": {},
            "baseline": {},
        },
    }
    results = {}
    for name, overrides in factors.items():
        # apply overrides temporarily
        orig_dg = base_params["demand_growth_map"].copy()
        orig_tf = base_params["tech_feedback_map"].copy()
        orig_rd = base_params["rd_hit"].copy()

        if "demand_growth" in overrides:
            for k, v in overrides["demand_growth"].items():
                base_params["demand_growth_map"][k] = v
        if "tech_feedback" in overrides:
            for k, v in overrides["tech_feedback"].items():
                base_params["tech_feedback_map"][k] = v
        if "rd_hit" in overrides:
            for scen, adj in overrides["rd_hit"].items():
                base_params["rd_hit"][scen].update(adj)

        # run scenarios using these maps
        scen_results = {}
        for scen in SCENARIO_FUNC_MAP.keys():
            scen_results[scen] = run_scenario_with_maps(
                scen,
                base_params["demand_growth_map"],
                base_params["tech_feedback_map"],
                base_params["rd_hit"],
            )
        results[name] = scen_results

        # restore
        base_params["demand_growth_map"] = orig_dg
        base_params["tech_feedback_map"] = orig_tf
        base_params["rd_hit"] = orig_rd
    return results


def save_results_to_csv(results: Dict[str, Any], out_dir: Path) -> None:
    """
    Save per-year metrics for each scenario.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for scen, res in results.items():
        rows = []
        for idx, year in enumerate(res["year"]):
            us_prod = res["us_prod"][idx]
            us_imp = res["us_import_cn"][idx]
            us_imp_share = res["us_import_cn_share"][idx]
            SAF = res["security"][idx]
            row = {
                "year": year,
                "NSI": res["NSI"][idx],
                "Welfare": res["Welfare"][idx],
                "Obj_t": res["Obj_t"][idx],
                "Gap_H": res["gap_H"][idx],
                "SAF_H": SAF.get("H", 0.0),
                "SAF_M": SAF.get("M", 0.0),
                "SAF_L": SAF.get("L", 0.0),
                "US_prod_H": us_prod.get("H", 0.0),
                "US_prod_M": us_prod.get("M", 0.0),
                "US_prod_L": us_prod.get("L", 0.0),
                "US_import_from_CN_H": us_imp.get("H", 0.0),
                "US_import_from_CN_M": us_imp.get("M", 0.0),
                "US_import_from_CN_L": us_imp.get("L", 0.0),
                "US_import_from_CN_share_H": us_imp_share.get("H", 0.0),
                "US_import_from_CN_share_M": us_imp_share.get("M", 0.0),
                "US_import_from_CN_share_L": us_imp_share.get("L", 0.0),
            }
            rows.append(row)
        df = pd.DataFrame(rows)
        df["scenario"] = scen
        df.to_csv(out_dir / f"{scen}.csv", index=False)

    # Also save a summary table of discounted objectives
    summary = pd.DataFrame(
        [
            {"scenario": scen, "discounted_objective": res["discounted_obj"]}
            for scen, res in results.items()
        ]
    )
    summary.to_csv(out_dir / "summary.csv", index=False)


if __name__ == "__main__":
    results = run_all_scenarios()
    for name, res in results.items():
        print(f"Scenario: {name}, discounted objective = {res['discounted_obj']:.2f}")

    save_dir = config.PROJECT_ROOT / "results"
    save_results_to_csv(results, save_dir)
    print(f"Per-scenario time series saved to: {save_dir}")
    # Save plots
    plots_dir = save_dir / "plots"
    save_all_plots(results, plots_dir)
    print(f"Plots saved to: {plots_dir}")
