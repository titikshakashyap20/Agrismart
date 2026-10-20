"""
AgriSmart Review 2 - Member 2
Optimization Layer: proving the self-adaptive DE mechanism actually works.

This does NOT use AgriSmart's yield function - it tests the algorithm on
two standard benchmark functions from the optimization literature (the
same kind of functions Brest et al., 2006 used to validate jDE). That
keeps this fully independent of Member 1 and Member 3: this file proves
the MATH and ALGORITHM are correct in isolation, before anyone plugs in
the real problem.

HOW TO USE THIS ON ITS OWN:
    python de_algorithm_validation.py
Produces algorithm_validation.png comparing vanilla DE vs self-adaptive DE
on two textbook problems.
"""

import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# Standard benchmark functions (both minimized at x = 0)
# ============================================================
def sphere(x):
    """Simplest possible test: smooth bowl shape."""
    return np.sum(np.array(x) ** 2)


def rastrigin(x):
    """Harder test: many local optima - a much tougher search landscape."""
    x = np.array(x)
    n = len(x)
    return 10 * n + np.sum(x**2 - 10 * np.cos(2 * np.pi * x))


# ============================================================
# Vanilla DE (fixed F, CR) - the base paper's approach
# ============================================================
def vanilla_de(fitness_func, bounds, pop_size=30, F=0.5, CR=0.7, max_gen=150):
    dim = len(bounds)
    lower = np.array([b[0] for b in bounds])
    upper = np.array([b[1] for b in bounds])

    pop = lower + np.random.rand(pop_size, dim) * (upper - lower)
    fitness = np.array([fitness_func(ind) for ind in pop])
    history = []

    for gen in range(max_gen):
        for i in range(pop_size):
            idxs = [j for j in range(pop_size) if j != i]
            a, b, c = pop[np.random.choice(idxs, 3, replace=False)]
            mutant = np.clip(a + F * (b - c), lower, upper)

            trial = np.copy(pop[i])
            for j in range(dim):
                if np.random.rand() < CR:
                    trial[j] = mutant[j]

            trial_fit = fitness_func(trial)
            if trial_fit < fitness[i]:
                pop[i] = trial
                fitness[i] = trial_fit

        history.append(fitness.min())

    return pop[fitness.argmin()], fitness.min(), history


# ============================================================
# Self-Adaptive DE (jDE-style, Brest et al. 2006) - our proposed work
# ============================================================
def self_adaptive_de(fitness_func, bounds, pop_size=30, max_gen=150,
                      F_l=0.1, F_u=0.9, tau1=0.1, tau2=0.1):
    dim = len(bounds)
    lower = np.array([b[0] for b in bounds])
    upper = np.array([b[1] for b in bounds])

    pop = lower + np.random.rand(pop_size, dim) * (upper - lower)
    fitness = np.array([fitness_func(ind) for ind in pop])
    F = np.full(pop_size, 0.5)
    CR = np.full(pop_size, 0.9)
    history = []

    for gen in range(max_gen):
        for i in range(pop_size):
            # --- self-adaptation step: the core of the proposed work ---
            if np.random.rand() < tau1:
                F[i] = F_l + np.random.rand() * F_u
            if np.random.rand() < tau2:
                CR[i] = np.random.rand()

            idxs = [j for j in range(pop_size) if j != i]
            a, b, c = pop[np.random.choice(idxs, 3, replace=False)]
            mutant = np.clip(a + F[i] * (b - c), lower, upper)

            trial = np.copy(pop[i])
            for j in range(dim):
                if np.random.rand() < CR[i]:
                    trial[j] = mutant[j]

            trial_fit = fitness_func(trial)
            if trial_fit < fitness[i]:
                pop[i] = trial
                fitness[i] = trial_fit
                # F[i], CR[i] are kept - they earned their place by improving fitness

        history.append(fitness.min())

    return pop[fitness.argmin()], fitness.min(), history


# ============================================================
# Run validation on both benchmark problems
# ============================================================
if __name__ == "__main__":
    np.random.seed(42)  # fixed seed = same numbers every time you re-run this

    problems = {
        "Sphere (easy)": (sphere, [(-5, 5)] * 5),
        "Rastrigin (hard, many local optima)": (rastrigin, [(-5.12, 5.12)] * 5),
    }

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, (name, (func, bounds)) in zip(axes, problems.items()):
        _, f1, h1 = vanilla_de(func, bounds)
        _, f2, h2 = self_adaptive_de(func, bounds)

        ax.plot(h1, label="Vanilla DE")
        ax.plot(h2, label="Self-Adaptive DE")
        ax.set_title(name)
        ax.set_xlabel("Generation")
        ax.set_ylabel("Best Fitness (lower = better)")
        ax.legend()

        print(f"{name}:")
        print(f"  Vanilla DE final fitness:       {f1:.6f}")
        print(f"  Self-Adaptive DE final fitness: {f2:.6f}")

    plt.tight_layout()
    plt.savefig("algorithm_validation.png")
    print("Saved algorithm_validation.png")