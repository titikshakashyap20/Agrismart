"""
AgriSmart Review 2 - Member 3 Implementation
Decision & Control Layer + DE Optimizer Engine
Vanilla DE vs Self-Adaptive DE comparison

HOW TO USE:
- Run this file as-is right now (Step 3-5 below use a dummy test function).
- Once Member 1 gives you the real yield formula, replace `dummy_sphere`
  with their function.
- Once Member 2 gives you exact F_l, F_u, tau1, tau2 values, update them
  in the self_adaptive_de() call at the bottom.
"""

import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# STEP 1: Vanilla Differential Evolution (baseline, matches base paper)
# ============================================================
def differential_evolution(fitness_func, bounds, pop_size=30, F=0.5, CR=0.7,
                            max_gen=100, minimize=True):
    dim = len(bounds)
    lower = np.array([b[0] for b in bounds])
    upper = np.array([b[1] for b in bounds])
    sign = 1 if minimize else -1  # flip sign so we can always "minimize" internally

    pop = lower + np.random.rand(pop_size, dim) * (upper - lower)
    fitness = np.array([sign * fitness_func(ind) for ind in pop])

    best_history = []

    for gen in range(max_gen):
        for i in range(pop_size):
            idxs = [idx for idx in range(pop_size) if idx != i]
            a, b, c = pop[np.random.choice(idxs, 3, replace=False)]

            mutant = np.clip(a + F * (b - c), lower, upper)

            trial = np.copy(pop[i])
            for j in range(dim):
                if np.random.rand() < CR:
                    trial[j] = mutant[j]

            trial_fit = sign * fitness_func(trial)
            if trial_fit < fitness[i]:
                pop[i] = trial
                fitness[i] = trial_fit

        best_history.append(sign * fitness.min())

    best_idx = fitness.argmin()
    return pop[best_idx], sign * fitness[best_idx], best_history


# ============================================================
# STEP 2: Self-Adaptive DE (our proposed work - jDE style)
# Each individual carries its own F_i, CR_i, which mutate over time.
# ============================================================
def self_adaptive_de(fitness_func, bounds, pop_size=30, max_gen=100,
                      F_l=0.1, F_u=0.9, tau1=0.1, tau2=0.1, minimize=True):
    dim = len(bounds)
    lower = np.array([b[0] for b in bounds])
    upper = np.array([b[1] for b in bounds])
    sign = 1 if minimize else -1

    pop = lower + np.random.rand(pop_size, dim) * (upper - lower)
    fitness = np.array([sign * fitness_func(ind) for ind in pop])
    F = np.full(pop_size, 0.5)
    CR = np.full(pop_size, 0.9)

    best_history = []

    for gen in range(max_gen):
        for i in range(pop_size):
            # self-adapt this individual's own F and CR
            if np.random.rand() < tau1:
                F[i] = F_l + np.random.rand() * F_u
            if np.random.rand() < tau2:
                CR[i] = np.random.rand()

            idxs = [idx for idx in range(pop_size) if idx != i]
            a, b, c = pop[np.random.choice(idxs, 3, replace=False)]
            mutant = np.clip(a + F[i] * (b - c), lower, upper)

            trial = np.copy(pop[i])
            for j in range(dim):
                if np.random.rand() < CR[i]:
                    trial[j] = mutant[j]

            trial_fit = sign * fitness_func(trial)
            if trial_fit < fitness[i]:
                pop[i] = trial
                fitness[i] = trial_fit
                # F[i], CR[i] are kept as-is since they just produced an improvement

        best_history.append(sign * fitness.min())

    best_idx = fitness.argmin()
    return pop[best_idx], sign * fitness[best_idx], best_history


# ============================================================
# STEP 3: Dummy test function - use this RIGHT NOW, no need to wait
# ============================================================
def dummy_sphere(x):
    """Placeholder only. Swap for Member 1's real yield formula later."""
    return sum(xi ** 2 for xi in x)


# ============================================================
# STEP 4 + 5: Run both algorithms + make the comparison plot
# ============================================================
if __name__ == "__main__":
    bounds = [(-5, 5)] * 3  # 3 dummy "resource" variables for now

    best1, fit1, hist1 = differential_evolution(dummy_sphere, bounds, minimize=True)
    best2, fit2, hist2 = self_adaptive_de(dummy_sphere, bounds, minimize=True)

    print("Vanilla DE best fitness:      ", fit1)
    print("Self-Adaptive DE best fitness:", fit2)

    plt.plot(hist1, label="Vanilla DE")
    plt.plot(hist2, label="Self-Adaptive DE")
    plt.xlabel("Generation")
    plt.ylabel("Best Fitness (lower = better, on dummy function)")
    plt.title("Convergence Comparison (dummy function - swap in real yield function later)")
    plt.legend()
    plt.savefig("comparison_plot.png")
    print("Saved comparison_plot.png")