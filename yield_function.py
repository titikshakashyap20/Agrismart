"""
AgriSmart Review 2 - Yield Estimation Layer (Member 1), extended

WHAT CHANGED FROM THE STATIC VERSION:
The original fitness() below depends only on sum(x) - irrigation timing had
zero effect on the score, so a closed-loop / receding-horizon controller
couldn't demonstrate anything (any reshuffling of the same total was
equally "optimal"). make_fitness() fixes that by simulating the candidate
irrigation plan at DAILY resolution.

IMPORTANT CLOSED-LOOP DETAIL:
x[i] is the irrigation amount for decision interval i.  During fitness
evaluation, x[i] is applied on the FIRST DAY of that interval and zero is
applied on the remaining days.  This matches the actual controller in
closed_loop_simulation.py, which executes only best_x[0] at the current
decision point and then advances the real environment day-by-day.

Final yield = potential_yield(total_irrigation) * seasonal_water_stress_factor
  - potential_yield: unchanged Mitscherlich curve (original model)
  - seasonal_water_stress_factor: mean of the daily 0-1 water-availability
    trajectory over the simulated window.

The original static fitness()/BUDGET are KEPT EXACTLY AS BEFORE so
run_final_results.py's original static demo still runs unchanged.
"""

import numpy as np
import config
from soil_water_model import simulate_season

# ---------------------------------------------------------------
# ORIGINAL STATIC MODEL - unchanged
# ---------------------------------------------------------------
Y_MAX = config.Y_MAX
K = config.K
PRICE_PER_UNIT = config.PRICE_PER_UNIT
LAMBDA_WEIGHT = config.LAMBDA_WEIGHT
BUDGET = config.BUDGET


def yield_estimate(total_resource):
    """Mitscherlich-type diminishing-returns potential-yield curve. Unchanged."""
    return Y_MAX * (1 - np.exp(-K * total_resource))


def cost_estimate(total_resource):
    return PRICE_PER_UNIT * total_resource


def fitness(x):
    """ORIGINAL static fitness - depends only on sum(x). Preserved exactly;
    used only by the static demo in run_final_results.py, NOT by the
    closed-loop simulation."""
    x = np.clip(np.asarray(x, dtype=float), 0, None)
    total_resource = np.sum(x)
    y = yield_estimate(total_resource)
    c = cost_estimate(total_resource)
    score = y - LAMBDA_WEIGHT * c
    if total_resource > BUDGET:
        score -= 5 * (total_resource - BUDGET)
    return score


# ---------------------------------------------------------------
# NEW: crop coefficient curve (simplified FAO-56 3-stage Kc)
# ---------------------------------------------------------------
def crop_coefficient_curve(n_days):
    """
    Piecewise-linear Kc: rises from KC_INITIAL to KC_MID over the first
    third of the season, holds at KC_MID through mid-season, then eases
    down to KC_LATE over the last third.
    """
    t = np.linspace(0, 1, n_days)
    kc = np.piecewise(
        t,
        [t < 1 / 3, (t >= 1 / 3) & (t < 2 / 3), t >= 2 / 3],
        [
            lambda t: config.KC_INITIAL
            + (config.KC_MID - config.KC_INITIAL) * (t / (1 / 3)),
            lambda t: config.KC_MID,
            lambda t: config.KC_MID
            + (config.KC_LATE - config.KC_MID) * ((t - 2 / 3) / (1 / 3)),
        ],
    )
    return kc


def seasonal_stress_factor(water_availability_series):
    """Mean daily water availability over the window, clipped to [0,1]."""
    if len(water_availability_series) == 0:
        return 1.0
    return float(np.clip(np.mean(water_availability_series), 0.0, 1.0))


# ---------------------------------------------------------------
# NEW: fitness factory for the closed-loop system
# ---------------------------------------------------------------
def make_fitness(
    initial_soil_moisture,
    rain_series,
    et_series,
    budget_remaining,
    price_per_unit=PRICE_PER_UNIT,
    lambda_weight=LAMBDA_WEIGHT,
    y_max=Y_MAX,
    k=K,
    decision_interval=config.DECISION_INTERVAL_DAYS,
    horizon_budget=None,
):
    """
    Returns a function of x only, so it drops directly into the existing
    DE/jDE engine with ZERO changes to that file.

    x[i] = irrigation amount applied on the FIRST DAY of decision interval i.

    rain_series and et_series are DAILY series for the entire optimization
    horizon.  Candidate x is expanded to daily irrigation internally:

        x[0], 0, 0, 0, 0, x[1], 0, 0, 0, 0, x[2], ...

    for a 5-day decision interval.

    This is deliberately the same execution rule used by the real
    closed-loop controller: only the first decision is executed now, then
    the environment advances day-by-day.
    """
    rain_series = np.asarray(rain_series, dtype=float)
    et_series = np.asarray(et_series, dtype=float)

    if rain_series.ndim != 1 or et_series.ndim != 1:
        raise ValueError("rain_series and et_series must be 1-D arrays")
    if len(rain_series) != len(et_series):
        raise ValueError("rain_series and et_series must have the same length")
    if decision_interval <= 0:
        raise ValueError("decision_interval must be positive")

    budget_remaining = max(float(budget_remaining), 0.0)
    n_days = len(rain_series)
    expected_decisions = int(np.ceil(n_days / decision_interval))

    # In receding-horizon control, the seasonal budget is larger than the
    # local horizon.  `horizon_budget` is therefore the portion of the
    # remaining seasonal budget that this local optimization is allowed to
    # allocate.  This is a HARD feasibility limit, not a soft penalty.
    if horizon_budget is None:
        horizon_budget = budget_remaining
    horizon_budget = float(np.clip(horizon_budget, 0.0, budget_remaining))

    def fitness_fn(x):
        x = np.clip(np.asarray(x, dtype=float), 0.0, None)

        if len(x) != expected_decisions:
            raise ValueError(
                f"Expected {expected_decisions} decision variables for "
                f"{n_days} daily horizon days with a {decision_interval}-day "
                f"decision interval, got {len(x)}"
            )

        total_irrigation = float(np.sum(x))

        # The optimizer must respect the budget assigned to this horizon.
        # A large negative score makes infeasible candidates unambiguously
        # worse than every feasible candidate while leaving the DE engine
        # unchanged.
        if total_irrigation > horizon_budget + 1e-9:
            excess = total_irrigation - horizon_budget
            return float(-1e12 - 1e6 * excess)

        # Expand decision-level irrigation into the DAILY schedule actually
        # used by the controller: each decision is applied only on the first
        # day of its interval.
        daily_irrigation = np.zeros(n_days, dtype=float)
        decision_days = np.arange(0, n_days, decision_interval)
        daily_irrigation[decision_days] = x

        sim = simulate_season(
            initial_soil_moisture,
            rain_series,
            et_series,
            daily_irrigation,
        )
        stress = seasonal_stress_factor(sim["water_availability"])

        potential_yield = y_max * (1 - np.exp(-k * total_irrigation))
        actual_yield = potential_yield * stress
        cost = price_per_unit * total_irrigation

        score = actual_yield - lambda_weight * cost

        # `horizon_budget` already enforces the seasonal-budget constraint.
        # Keep a tiny numerical guard for floating-point drift.
        if total_irrigation > horizon_budget + 1e-9:
            return float(-1e12)

        return float(score)

    return fitness_fn


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    example_plan = np.full(5, BUDGET / 5)
    print("Static model sanity check (unchanged from original):")
    print("  Example plan:", example_plan, " Fitness:", fitness(example_plan))

    resources = np.linspace(0, 200, 200)
    yields = [yield_estimate(r) for r in resources]
    plt.plot(resources, yields)
    plt.axvline(BUDGET, color="red", linestyle="--", label="Budget limit")
    plt.xlabel("Total Resource Applied")
    plt.ylabel("Estimated Potential Yield")
    plt.title("Yield Estimation Layer - Diminishing Returns Curve (unchanged)")
    plt.legend()
    plt.savefig("yield_curve.png")
    print("Saved yield_curve.png")
