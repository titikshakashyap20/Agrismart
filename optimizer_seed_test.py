"""
AgriSmart Review 2 - Optimizer Seed Diagnostic

Tests Vanilla DE and self-adaptive DE DIRECTLY on the real agricultural
fitness function used by the closed-loop controller.

Run:
    python optimizer_seed_test.py
"""

import csv
import random
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

import config
from data_layer import get_weather
from yield_function import make_fitness, crop_coefficient_curve
from de_optimizer_engine import differential_evolution, self_adaptive_de


SEEDS = list(range(1, 11))


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)


def build_real_fitness():
    """
    Build the SAME day-0 optimization problem used by
    closed_loop_simulation.py.

    This is intentionally not a toy objective.
    """
    weather = get_weather()
    n_days = len(weather)

    rain = weather["rain_mm"].values.astype(float)
    et0 = weather["et0_mm"].values.astype(float)

    kc = crop_coefficient_curve(n_days)
    et = et0 * kc

    # Match the first closed-loop decision point.
    day = 0
    soil_moisture = config.INITIAL_SOIL_MOISTURE
    budget_remaining = float(config.BUDGET)

    window_days = min(
        config.HORIZON_DECISIONS * config.DECISION_INTERVAL_DAYS,
        n_days - day,
    )

    rain_window = rain[day:day + window_days]
    et_window = et[day:day + window_days]

    n_dec = int(
        np.ceil(window_days / config.DECISION_INTERVAL_DAYS)
    )

    # Match the horizon-budget calculation in closed_loop_simulation.py.
    remaining_days = max(n_days - day, 1)
    horizon_budget = budget_remaining * (
        window_days / remaining_days
    )
    horizon_budget = float(
        np.clip(horizon_budget, 0.0, budget_remaining)
    )

    fitness_fn = make_fitness(
        initial_soil_moisture=soil_moisture,
        rain_series=rain_window,
        et_series=et_window,
        budget_remaining=budget_remaining,
        horizon_budget=horizon_budget,
        decision_interval=config.DECISION_INTERVAL_DAYS,
    )

    upper = min(
        config.I_MAX_PER_DECISION,
        max(horizon_budget, 0.0),
        max(budget_remaining, 0.0),
    )

    bounds = [(0.0, upper)] * n_dec

    return fitness_fn, bounds, horizon_budget, window_days


def run():
    fitness_fn, bounds, horizon_budget, window_days = build_real_fitness()

    print("=" * 70)
    print("REAL AGRICULTURAL FITNESS - OPTIMIZER SEED DIAGNOSTIC")
    print("=" * 70)
    print(f"Seeds: {SEEDS}")
    print(f"Optimization window: {window_days} days")
    print(f"Decision variables: {len(bounds)}")
    print(f"Decision interval: {config.DECISION_INTERVAL_DAYS} days")
    print(f"Horizon budget: {horizon_budget:.4f} mm")
    print(f"Bounds per decision: {bounds[0]}")
    print()

    rows = []

    for optimizer_name in ("vanilla", "jde"):
        print(f"--- {optimizer_name.upper()} ---")

        for seed in SEEDS:
            set_seed(seed)

            if optimizer_name == "vanilla":
                best_x, best_fit, history = differential_evolution(
                    fitness_fn,
                    bounds,
                    pop_size=config.POP_SIZE,
                    F=config.F,
                    CR=config.CR,
                    max_gen=config.MAX_GEN,
                    minimize=False,
                )
            else:
                best_x, best_fit, history = self_adaptive_de(
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

            total = float(np.sum(best_x))

            row = {
                "optimizer": optimizer_name,
                "seed": seed,
                "best_fitness": float(best_fit),
                "total_horizon_irrigation": total,
                "first_decision": float(best_x[0]),
                "best_x": ",".join(f"{v:.6f}" for v in best_x),
                "final_history_value": float(history[-1]),
            }
            rows.append(row)

            print(
                f"Seed {seed:2d} | "
                f"Fitness={best_fit:.6f} | "
                f"Total horizon irrigation={total:.4f} | "
                f"First decision={best_x[0]:.4f} | "
                f"x={np.round(best_x, 3)}"
            )

        print()

    return rows


def save_results(rows):
    csv_path = Path("optimizer_seed_test.csv")

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved: {csv_path}")


def print_diagnostic(rows):
    print("\n" + "=" * 70)
    print("DIAGNOSTIC")
    print("=" * 70)

    for optimizer in ("vanilla", "jde"):
        subset = [
            r for r in rows
            if r["optimizer"] == optimizer
        ]

        fits = np.array([r["best_fitness"] for r in subset])
        first = np.array([r["first_decision"] for r in subset])
        totals = np.array(
            [r["total_horizon_irrigation"] for r in subset]
        )

        print(f"\n{optimizer.upper()}")
        print(f"  Fitness mean ± std: {fits.mean():.6f} ± {fits.std():.6f}")
        print(f"  Fitness min/max:    {fits.min():.6f} / {fits.max():.6f}")
        print(f"  First decision std: {first.std():.6f}")
        print(f"  Horizon total std:  {totals.std():.6f}")

        if np.isclose(fits.std(), 0.0) and np.isclose(first.std(), 0.0):
            print("  -> Essentially identical across seeds.")
        else:
            print("  -> Seed-dependent behaviour is present.")

    print(
        "\nInterpretation: if the direct optimizer varies across seeds but "
        "the closed-loop runs do not, the closed-loop objective/controller "
        "is collapsing the optimizer's stochastic differences. If the "
        "direct optimizer itself is identical across seeds, investigate "
        "the DE implementation or objective next."
    )


def make_plot(rows):
    plt.figure(figsize=(8, 5))

    for optimizer, label in (
        ("vanilla", "Vanilla DE"),
        ("jde", "Self-Adaptive DE"),
    ):
        subset = [
            r for r in rows
            if r["optimizer"] == optimizer
        ]
        seeds = [r["seed"] for r in subset]
        fitness = [r["best_fitness"] for r in subset]
        plt.plot(seeds, fitness, marker="o", label=label)

    plt.xlabel("Random Seed")
    plt.ylabel("Best Agricultural Fitness")
    plt.title("Direct Optimizer Response to Random Seeds")
    plt.xticks(SEEDS)
    plt.legend()
    plt.tight_layout()
    plt.savefig("optimizer_seed_test.png", dpi=300)
    plt.close()

    print("Saved: optimizer_seed_test.png")


if __name__ == "__main__":
    rows = run()
    save_results(rows)
    print_diagnostic(rows)
    make_plot(rows)

    print("\n" + "=" * 70)
    print("OPTIMIZER SEED DIAGNOSTIC COMPLETE")
    print("=" * 70)
