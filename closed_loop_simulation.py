"""
AgriSmart Review 2 - FINAL CLOSED-LOOP / RECEDING-HORIZON SIMULATION
(Decision & Control Layer, Member 3)

Implements the MPC loop:
    Data Layer -> Yield Estimation -> Optimization -> Decision & Control -> loop

At every decision point:
  1. Read the CURRENT real soil-moisture state.
  2. Optimize a short future horizon using DAILY weather/ET.
  3. Execute ONLY best_x[0].
  4. Advance the REAL soil state day-by-day using the REAL weather.
  5. Use the resulting state as the seed for the next optimization.
  6. Repeat.

IMPORTANT:
The optimizer's candidate-plan simulation and the real controller now use
the SAME timing convention.  A decision variable represents irrigation
applied on the FIRST DAY of its 5-day decision interval.  The remaining
days receive zero irrigation from that decision.

SEASONAL-BUDGET FIX:
The local MPC horizon no longer sees the entire remaining seasonal budget
as immediately spendable.  At each decision point, only the proportional
share of the remaining seasonal budget that belongs to the current horizon
is feasible.  This prevents a short 20-day optimizer from spending water
that should remain available for later decision points.
"""

import numpy as np
import pandas as pd

import config
from data_layer import get_weather
from soil_water_model import step, water_availability
from yield_function import (
    make_fitness,
    crop_coefficient_curve,
    Y_MAX,
    K,
)
from de_optimizer_engine import differential_evolution, self_adaptive_de


def _optimize_and_execute_one_decision(
    optimizer,
    soil_moisture,
    budget_remaining,
    rain_full,
    et_full,
    day,
    n_days,
    verbose,
):
    """
    ONE decision point of the receding horizon.

    The optimization horizon is represented at DAILY resolution, while the
    decision variables are one value per decision interval.  For example,
    with a 5-day interval and a 20-day horizon:

        x = [x0, x1, x2, x3]

    means irrigation x0 on day 0, x1 on day 5, x2 on day 10, x3 on day 15
    of the local horizon.

    Returns:
        (applied_irrigation, horizon_best_fitness, interval_len)
    """

    # -----------------------------------------------------------
    # STEP 1: CURRENT STATE
    # -----------------------------------------------------------
    # soil_moisture is supplied by the REAL simulation state.

    # -----------------------------------------------------------
    # STEP 2: BUILD DAILY OPTIMIZATION HORIZON
    # -----------------------------------------------------------
    window_days = min(
        config.HORIZON_DECISIONS * config.DECISION_INTERVAL_DAYS,
        n_days - day,
    )

    # IMPORTANT: pass DAILY weather/ET to make_fitness.
    # Do NOT aggregate them into 5-day totals.
    rain_window = np.asarray(
        rain_full[day : day + window_days],
        dtype=float,
    )
    et_window = np.asarray(
        et_full[day : day + window_days],
        dtype=float,
    )

    n_dec = int(
        np.ceil(window_days / config.DECISION_INTERVAL_DAYS)
    )

    # -----------------------------------------------------------
    # SEASONAL-BUDGET PACING
    # -----------------------------------------------------------
    # The horizon should only be allowed to consume its proportional share
    # of the remaining seasonal budget.  Example: if 20 days are optimized
    # out of 100 days remaining, at most 20% of the remaining budget is
    # allocated to that local horizon.  The next MPC call receives the
    # updated remaining budget and computes a new share.
    remaining_days = max(n_days - day, 1)
    horizon_budget = budget_remaining * (window_days / remaining_days)
    horizon_budget = float(np.clip(horizon_budget, 0.0, budget_remaining))

    fitness_fn = make_fitness(
        initial_soil_moisture=soil_moisture,
        rain_series=rain_window,
        et_series=et_window,
        budget_remaining=budget_remaining,
        horizon_budget=horizon_budget,
        decision_interval=config.DECISION_INTERVAL_DAYS,
    )

    # Per-decision physical limit plus the horizon-level budget constraint.
    upper = min(
        config.I_MAX_PER_DECISION,
        max(horizon_budget, 0.0),
        max(budget_remaining, 0.0),
    )
    bounds = [(0.0, upper)] * n_dec

    # -----------------------------------------------------------
    # RUN THE SELECTED OPTIMIZER
    # -----------------------------------------------------------
    if optimizer == "vanilla":
        best_x, best_fit, _ = differential_evolution(
            fitness_fn,
            bounds,
            pop_size=config.POP_SIZE,
            F=config.F,
            CR=config.CR,
            max_gen=config.MAX_GEN,
            minimize=False,
        )
    elif optimizer == "jde":
        best_x, best_fit, _ = self_adaptive_de(
            fitness_fn,
            bounds,
            pop_size=config.POP_SIZE,
            max_gen=config.MAX_GEN,
            F_l=config.F_L,
            F_u=config.F_U,
            tau1=config.TAU1,
            tau2=config.TAU2,
            minimize=False,
        )
    else:
        raise ValueError("optimizer must be 'vanilla' or 'jde'")

    # -----------------------------------------------------------
    # STEP 3: EXECUTE ONLY THE FIRST DECISION
    # -----------------------------------------------------------
    applied_irrigation = float(
        np.clip(
            best_x[0],
            0.0,
            max(budget_remaining, 0.0),
        )
    )

    discarded_future_decisions = best_x[1:]

    if verbose:
        print(
            f"[{optimizer}] day {day:3d}: "
            f"state soil_moisture={soil_moisture:6.2f} -> "
            f"horizon_budget={horizon_budget:.2f}, "
            f"optimized horizon={list(np.round(best_x, 2))}, "
            f"executing only best_x[0]={applied_irrigation:.2f} "
            f"(discarding {len(discarded_future_decisions)} future entries)"
        )

    interval_len = min(
        config.DECISION_INTERVAL_DAYS,
        n_days - day,
    )

    return applied_irrigation, best_fit, interval_len, horizon_budget


def run_closed_loop(optimizer="jde", seed=config.RANDOM_SEED, verbose=True):
    """
    optimizer: "vanilla" or "jde"

    Returns:
        {
            "daily": DataFrame,
            "decisions": DataFrame,
            "summary": dict
        }
    """

    weather = get_weather()
    n_days = len(weather)

    rain = weather["rain_mm"].values
    et0 = weather["et0_mm"].values

    kc = crop_coefficient_curve(n_days)
    et = et0 * kc

    # CURRENT REAL STATE
    soil_moisture = config.INITIAL_SOIL_MOISTURE
    budget_remaining = config.BUDGET

    day = 0
    decision_log = []
    daily_log = []

    np.random.seed(seed)

    while day < n_days:

        # -------------------------------------------------------
        # STEPS 1-3:
        # Read current state -> optimize -> execute first decision
        # -------------------------------------------------------
        (
            applied_irrigation,
            best_fit,
            interval_len,
            horizon_budget,
        ) = _optimize_and_execute_one_decision(
            optimizer,
            soil_moisture,
            budget_remaining,
            rain,
            et,
            day,
            n_days,
            verbose,
        )

        # -------------------------------------------------------
        # STEP 4:
        # ADVANCE THE REAL ENVIRONMENT DAY-BY-DAY
        # -------------------------------------------------------
        for i in range(interval_len):

            new_moisture, drainage = step(
                soil_moisture,
                rain[day + i],
                applied_irrigation if i == 0 else 0.0,
                et[day + i],
            )

            avail = water_availability(new_moisture)

            daily_log.append(
                {
                    "day": day + i,
                    "soil_moisture": new_moisture,
                    "water_availability": avail,
                    "drainage": drainage,
                    "irrigation_applied": (
                        applied_irrigation if i == 0 else 0.0
                    ),
                }
            )

            # ---------------------------------------------------
            # STEP 5:
            # resulting real state becomes next decision's state
            # ---------------------------------------------------
            soil_moisture = new_moisture

        budget_remaining -= applied_irrigation

        decision_log.append(
            {
                "decision_day": day,
                "irrigation_applied": applied_irrigation,
                "horizon_fitness": best_fit,
                "horizon_budget": horizon_budget,
                "budget_remaining": budget_remaining,
            }
        )

        # -------------------------------------------------------
        # STEP 6: NEXT RECEDING-HORIZON DECISION
        # -------------------------------------------------------
        day += interval_len

    daily_df = pd.DataFrame(daily_log)

    total_irrigation = daily_df["irrigation_applied"].sum()
    mean_stress = daily_df["water_availability"].mean()

    potential_yield = Y_MAX * (
        1 - np.exp(-K * total_irrigation)
    )
    final_yield = potential_yield * mean_stress

    wue = (
        final_yield / total_irrigation
        if total_irrigation > 0
        else float("nan")
    )

    unused_budget = max(float(config.BUDGET) - float(total_irrigation), 0.0)
    budget_utilization = (
        float(total_irrigation) / float(config.BUDGET)
        if float(config.BUDGET) > 0 else float("nan")
    )

    summary = {
        "optimizer": optimizer,
        "final_yield": final_yield,
        "total_irrigation_mm": total_irrigation,
        "water_use_efficiency": wue,
        "mean_water_availability": mean_stress,
        "num_decision_points": len(decision_log),
        "unused_budget_mm": unused_budget,
        "budget_utilization": budget_utilization,
    }

    return {
        "daily": daily_df,
        "decisions": pd.DataFrame(decision_log),
        "summary": summary,
    }


def run_threshold_baseline(weather=None):
    """
    Simple, non-optimized baseline: irrigate a fixed amount whenever water
    availability drops below a threshold.

    No DE is involved.
    """
    weather = weather if weather is not None else get_weather()

    n_days = len(weather)
    rain = weather["rain_mm"].values
    et0 = weather["et0_mm"].values

    kc = crop_coefficient_curve(n_days)
    et = et0 * kc

    soil_moisture = config.INITIAL_SOIL_MOISTURE
    budget_remaining = config.BUDGET
    daily_log = []

    for day in range(n_days):

        avail = water_availability(soil_moisture)
        irrigation = 0.0

        if (
            avail < config.THRESHOLD_AVAILABILITY
            and budget_remaining > 0
        ):
            irrigation = min(
                config.THRESHOLD_IRRIGATION_AMOUNT,
                budget_remaining,
            )

        soil_moisture, drainage = step(
            soil_moisture,
            rain[day],
            irrigation,
            et[day],
        )

        budget_remaining -= irrigation

        daily_log.append(
            {
                "day": day,
                "soil_moisture": soil_moisture,
                "water_availability": water_availability(soil_moisture),
                "drainage": drainage,
                "irrigation_applied": irrigation,
            }
        )

    daily_df = pd.DataFrame(daily_log)

    total_irrigation = daily_df["irrigation_applied"].sum()
    mean_stress = daily_df["water_availability"].mean()

    potential_yield = Y_MAX * (
        1 - np.exp(-K * total_irrigation)
    )
    final_yield = potential_yield * mean_stress

    wue = (
        final_yield / total_irrigation
        if total_irrigation > 0
        else float("nan")
    )

    summary = {
        "optimizer": "threshold_baseline",
        "final_yield": final_yield,
        "total_irrigation_mm": total_irrigation,
        "water_use_efficiency": wue,
        "mean_water_availability": mean_stress,
    }

    return {
        "daily": daily_df,
        "summary": summary,
    }


if __name__ == "__main__":
    result = run_closed_loop(optimizer="jde")
    print(result["summary"])
