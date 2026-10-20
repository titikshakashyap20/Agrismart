"""
AgriSmart Review 2 - Final Results Analysis

Reads the already-generated budget_sensitivity_results.csv and creates
the final tables and figures for Review 2.

NO OPTIMIZATION IS RUN HERE.
This is analysis/visualization only.

Input:
    budget_sensitivity_results.csv

Outputs:
    final_analysis_summary.csv
    final_yield_vs_budget.png
    final_wue_vs_budget.png
    final_availability_vs_budget.png
    final_budget_utilization.png
    final_yield_improvement_vs_baseline.png
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


INPUT_FILE = "budget_sensitivity_results.csv"


# ============================================================
# LOAD RESULTS
# ============================================================

def load_results():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Could not find {INPUT_FILE} in the current folder."
        )

    df = pd.read_csv(INPUT_FILE)

    print("=" * 80)
    print("AGRISMART FINAL RESULTS ANALYSIS")
    print("=" * 80)
    print(f"Loaded: {INPUT_FILE}")
    print(f"Rows: {len(df)}")
    print()

    print("Columns found:")
    print(list(df.columns))
    print()

    return df


# ============================================================
# COLUMN NORMALIZATION
# ============================================================

def find_column(df, candidates):
    """
    Find a column using several possible names.
    """
    lower_map = {c.lower().strip(): c for c in df.columns}

    for candidate in candidates:
        key = candidate.lower().strip()
        if key in lower_map:
            return lower_map[key]

    for c in df.columns:
        cl = c.lower().strip()
        for candidate in candidates:
            if candidate.lower().strip() in cl:
                return c

    return None


def normalize_columns(df):
    """
    Identify the important columns without changing the source data.
    """

    budget_col = find_column(
        df,
        [
            "budget",
            "budget_mm",
            "budget (mm)",
            "irrigation_budget",
        ],
    )

    method_col = find_column(
        df,
        [
            "method",
            "optimizer",
            "strategy",
            "approach",
        ],
    )

    yield_col = find_column(
        df,
        [
            "yield",
            "final_yield",
        ],
    )

    irrigation_col = find_column(
        df,
        [
            "irrigation",
            "irrigation_used",
            "total_irrigation_mm",
            "irrigation_mm",
        ],
    )

    wue_col = find_column(
        df,
        [
            "wue",
            "water_use_efficiency",
        ],
    )

    availability_col = find_column(
        df,
        [
            "availability",
            "mean_water_availability",
            "water_availability",
        ],
    )

    utilization_col = find_column(
        df,
        [
            "utilization",
            "budget_utilization",
            "budget_usage",
        ],
    )

    mapping = {
        "budget": budget_col,
        "method": method_col,
        "yield": yield_col,
        "irrigation": irrigation_col,
        "wue": wue_col,
        "availability": availability_col,
        "utilization": utilization_col,
    }

    print("Detected columns:")
    for key, value in mapping.items():
        print(f"  {key:15s}: {value}")

    print()

    missing = [
        key
        for key, value in mapping.items()
        if value is None and key in
        ["budget", "method", "yield", "irrigation", "wue", "availability"]
    ]

    if missing:
        raise ValueError(
            "Could not identify required columns: "
            + ", ".join(missing)
        )

    return mapping


# ============================================================
# STANDARDIZE METHOD NAMES
# ============================================================

def standardize_method(value):
    text = str(value).strip().lower()

    if "threshold" in text:
        return "Threshold Baseline"

    if "vanilla" in text:
        return "Vanilla DE"

    if "jde" in text or "self" in text:
        return "Self-Adaptive DE (jDE)"

    return str(value)


# ============================================================
# CREATE ANALYSIS DATA
# ============================================================

def prepare_data(df, cols):

    data = pd.DataFrame()

    data["Budget"] = pd.to_numeric(
        df[cols["budget"]], errors="coerce"
    )

    data["Method"] = df[cols["method"]].apply(
        standardize_method
    )

    data["Yield"] = pd.to_numeric(
        df[cols["yield"]], errors="coerce"
    )

    data["Irrigation"] = pd.to_numeric(
        df[cols["irrigation"]], errors="coerce"
    )

    data["WUE"] = pd.to_numeric(
        df[cols["wue"]], errors="coerce"
    )

    data["Availability"] = pd.to_numeric(
        df[cols["availability"]], errors="coerce"
    )

    if cols["utilization"] is not None:
        data["Utilization"] = pd.to_numeric(
            df[cols["utilization"]], errors="coerce"
        )
    else:
        data["Utilization"] = (
            data["Irrigation"] / data["Budget"]
        )

    data = data.dropna(
        subset=[
            "Budget",
            "Method",
            "Yield",
            "Irrigation",
            "WUE",
            "Availability",
        ]
    )

    return data


# ============================================================
# FINAL SUMMARY
# ============================================================

def create_summary(data):

    grouped = (
        data.groupby(["Budget", "Method"], as_index=False)
        .agg(
            Mean_Yield=("Yield", "mean"),
            Std_Yield=("Yield", "std"),
            Mean_Irrigation=("Irrigation", "mean"),
            Std_Irrigation=("Irrigation", "std"),
            Mean_WUE=("WUE", "mean"),
            Std_WUE=("WUE", "std"),
            Mean_Availability=("Availability", "mean"),
            Std_Availability=("Availability", "std"),
            Mean_Utilization=("Utilization", "mean"),
            Std_Utilization=("Utilization", "std"),
        )
    )

    # Threshold baseline yield at each budget.
    baseline = grouped[
        grouped["Method"] == "Threshold Baseline"
    ][["Budget", "Mean_Yield"]].copy()

    baseline = baseline.rename(
        columns={"Mean_Yield": "Baseline_Yield"}
    )

    grouped = grouped.merge(
        baseline,
        on="Budget",
        how="left"
    )

    grouped["Yield_Improvement_vs_Baseline_pct"] = (
        (
            grouped["Mean_Yield"]
            - grouped["Baseline_Yield"]
        )
        / grouped["Baseline_Yield"]
        * 100
    )

    # Difference between Vanilla DE and jDE.
    vanilla = grouped[
        grouped["Method"] == "Vanilla DE"
    ][["Budget", "Mean_Yield"]].copy()

    vanilla = vanilla.rename(
        columns={"Mean_Yield": "Vanilla_Yield"}
    )

    jde = grouped[
        grouped["Method"] == "Self-Adaptive DE (jDE)"
    ][["Budget", "Mean_Yield"]].copy()

    jde = jde.rename(
        columns={"Mean_Yield": "JDE_Yield"}
    )

    comparison = vanilla.merge(
        jde,
        on="Budget",
        how="inner"
    )

    comparison["JDE_minus_Vanilla_Yield"] = (
        comparison["JDE_Yield"]
        - comparison["Vanilla_Yield"]
    )

    grouped = grouped.merge(
        comparison[
            [
                "Budget",
                "JDE_minus_Vanilla_Yield",
            ]
        ],
        on="Budget",
        how="left"
    )

    return grouped


# ============================================================
# PLOTTING
# ============================================================

def plot_metric(
    summary,
    metric,
    ylabel,
    title,
    filename,
    include_error=True,
):
    plt.figure(figsize=(8, 5))

    methods = [
        "Threshold Baseline",
        "Vanilla DE",
        "Self-Adaptive DE (jDE)",
    ]

    for method in methods:

        subset = summary[
            summary["Method"] == method
        ].sort_values("Budget")

        if subset.empty:
            continue

        x = subset["Budget"].to_numpy()
        y = subset[f"Mean_{metric}"].to_numpy()

        if include_error:
            error = subset[
                f"Std_{metric}"
            ].fillna(0).to_numpy()

            plt.errorbar(
                x,
                y,
                yerr=error,
                marker="o",
                linewidth=2,
                capsize=4,
                label=method,
            )
        else:
            plt.plot(
                x,
                y,
                marker="o",
                linewidth=2,
                label=method,
            )

    plt.xlabel("Seasonal irrigation budget (mm)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    plt.close()

    print(f"Saved: {filename}")


def plot_utilization(summary):

    plt.figure(figsize=(8, 5))

    methods = [
        "Threshold Baseline",
        "Vanilla DE",
        "Self-Adaptive DE (jDE)",
    ]

    for method in methods:

        subset = summary[
            summary["Method"] == method
        ].sort_values("Budget")

        if subset.empty:
            continue

        plt.plot(
            subset["Budget"],
            subset["Mean_Utilization"],
            marker="o",
            linewidth=2,
            label=method,
        )

    plt.xlabel("Seasonal irrigation budget (mm)")
    plt.ylabel("Budget utilization")
    plt.title("Budget Utilization vs Irrigation Budget")
    plt.ylim(0, 1.1)
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()

    filename = "final_budget_utilization.png"
    plt.savefig(filename, dpi=300)
    plt.close()

    print(f"Saved: {filename}")


# ============================================================
# YIELD IMPROVEMENT PLOT
# ============================================================

def plot_yield_improvement(summary):

    plt.figure(figsize=(8, 5))

    methods = [
        "Vanilla DE",
        "Self-Adaptive DE (jDE)",
    ]

    for method in methods:

        subset = summary[
            summary["Method"] == method
        ].sort_values("Budget")

        if subset.empty:
            continue

        plt.plot(
            subset["Budget"],
            subset[
                "Yield_Improvement_vs_Baseline_pct"
            ],
            marker="o",
            linewidth=2,
            label=method,
        )

    plt.axhline(
        0,
        linestyle="--",
        linewidth=1,
    )

    plt.xlabel("Seasonal irrigation budget (mm)")
    plt.ylabel("Yield improvement vs threshold baseline (%)")
    plt.title("Yield Improvement Relative to Threshold Baseline")
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()

    filename = "final_yield_improvement_vs_baseline.png"
    plt.savefig(filename, dpi=300)
    plt.close()

    print(f"Saved: {filename}")


# ============================================================
# PRINT FINAL TABLE
# ============================================================

def print_final_table(summary):

    print()
    print("=" * 100)
    print("FINAL REVIEW 2 RESULTS")
    print("=" * 100)

    display_cols = [
        "Budget",
        "Method",
        "Mean_Yield",
        "Std_Yield",
        "Mean_WUE",
        "Std_WUE",
        "Mean_Availability",
        "Std_Availability",
        "Yield_Improvement_vs_Baseline_pct",
    ]

    table = summary[display_cols].copy()

    print(
        table.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}"
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    df = load_results()

    cols = normalize_columns(df)

    data = prepare_data(df, cols)

    print("Methods detected:")
    for method in sorted(data["Method"].unique()):
        print(f"  - {method}")

    print()

    summary = create_summary(data)

    # Save final numerical summary.
    summary_file = "final_analysis_summary.csv"
    summary.to_csv(summary_file, index=False)

    print(f"Saved: {summary_file}")

    # Generate final figures.
    plot_metric(
        summary,
        metric="Yield",
        ylabel="Final yield",
        title="Final Yield vs Seasonal Irrigation Budget",
        filename="final_yield_vs_budget.png",
    )

    plot_metric(
        summary,
        metric="WUE",
        ylabel="Water-use efficiency (yield/mm)",
        title="Water-Use Efficiency vs Seasonal Irrigation Budget",
        filename="final_wue_vs_budget.png",
    )

    plot_metric(
        summary,
        metric="Availability",
        ylabel="Mean water availability",
        title="Mean Water Availability vs Seasonal Irrigation Budget",
        filename="final_availability_vs_budget.png",
    )

    plot_utilization(summary)

    plot_yield_improvement(summary)

    print_final_table(summary)

    print()
    print("=" * 100)
    print("FINAL ANALYSIS COMPLETE")
    print("=" * 100)
    print("No optimizer or simulation was executed.")
    print("All values were calculated from budget_sensitivity_results.csv.")


if __name__ == "__main__":
    main()