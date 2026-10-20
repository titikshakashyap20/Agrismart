"""AgriSmart dashboard API.

The dashboard is a presentation layer over the validated AgriSmart model.
It runs the existing closed-loop controller and threshold baseline directly;
it does not reimplement the agricultural model or optimizers.
"""
from __future__ import annotations

import math
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from closed_loop_simulation import run_closed_loop, run_threshold_baseline  # noqa: E402

# The validated final research CSV is treated as project data, not something
# the dashboard computes or invents. It is looked for in a couple of
# reasonable places so this keeps working whether it's dropped at the
# project root (alongside config.py) or next to this backend file.
_RESEARCH_CSV_CANDIDATES = [
    PROJECT_ROOT / "final_analysis_summary.csv",
    Path(__file__).resolve().parent / "final_analysis_summary.csv",
]

app = FastAPI(title="AgriSmart Dashboard API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SimulationRequest(BaseModel):
    initial_soil_moisture: Optional[float] = Field(default=None, ge=0)
    budget_mm: Optional[float] = Field(default=None, ge=0, le=5000)


@contextmanager
def temporary_config(initial_soil_moisture: float | None, budget_mm: float | None):
    old_initial = config.INITIAL_SOIL_MOISTURE
    old_budget = config.BUDGET
    try:
        if initial_soil_moisture is not None:
            config.INITIAL_SOIL_MOISTURE = float(initial_soil_moisture)
        if budget_mm is not None:
            config.BUDGET = float(budget_mm)
        yield
    finally:
        config.INITIAL_SOIL_MOISTURE = old_initial
        config.BUDGET = old_budget


def clean(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 6)
    return value


def df_records(df):
    return [{k: clean(v) for k, v in row.items()} for row in df.to_dict("records")]


def pack_result(name: str, result: dict):
    return {
        "method": name,
        "summary": {k: clean(v) for k, v in result["summary"].items()},
        "daily": df_records(result["daily"]),
        "decisions": df_records(result.get("decisions")) if result.get("decisions") is not None else [],
    }


def _direction_word(recommended_value: float, other_value: float, tol_pct: float = 1.0) -> str:
    """Describes recommended_value relative to other_value in plain words.
    tol_pct is the percentage difference below which the two are called
    'about the same' rather than forcing a higher/lower call on noise."""
    denom = max(abs(other_value), 1e-9)
    pct_diff = (recommended_value - other_value) / denom * 100.0
    if abs(pct_diff) < tol_pct:
        return "about the same"
    return "higher" if pct_diff > 0 else "lower"


def assess_strategies(threshold: dict, adaptive: dict):
    """Apply one fixed, user-independent balanced assessment.

    The dashboard does not ask users to choose an optimization objective.
    Yield is given 60% of the internal score and WUE 40%. Both metrics are
    normalized only between the two strategies in the current simulation.
    This is a dashboard decision rule, not a claim that jDE is universally
    superior - the wording below is generated from whichever strategy
    actually wins in THIS run, in either direction.
    """
    t = threshold["summary"]
    a = adaptive["summary"]
    y_t, y_a = float(t["final_yield"]), float(a["final_yield"])
    w_t, w_a = float(t["water_use_efficiency"]), float(a["water_use_efficiency"])
    irr_t, irr_a = float(t["total_irrigation_mm"]), float(a["total_irrigation_mm"])
    avail_t, avail_a = float(t["mean_water_availability"]), float(a["mean_water_availability"])

    def pair_norm(x, y):
        lo, hi = min(x, y), max(x, y)
        if abs(hi - lo) < 1e-12:
            return 0.5, 0.5
        return (x - lo) / (hi - lo), (y - lo) / (hi - lo)

    ny_t, ny_a = pair_norm(y_t, y_a)
    nw_t, nw_a = pair_norm(w_t, w_a)
    score_t = 0.60 * ny_t + 0.40 * nw_t
    score_a = 0.60 * ny_a + 0.40 * nw_a
    jde_selected = score_a >= score_t
    selected = "Self-Adaptive DE (jDE)" if jde_selected else "Threshold Baseline"
    other = "Threshold Baseline" if jde_selected else "Self-Adaptive DE (jDE)"

    # Values for whichever strategy was actually selected vs. the other one,
    # so the sentence below is honest in either direction rather than
    # always being written from jDE's point of view.
    rec_y, oth_y = (y_a, y_t) if jde_selected else (y_t, y_a)
    rec_irr, oth_irr = (irr_a, irr_t) if jde_selected else (irr_t, irr_a)
    rec_avail, oth_avail = (avail_a, avail_t) if jde_selected else (avail_t, avail_a)

    yield_dir = _direction_word(rec_y, oth_y)
    avail_dir = _direction_word(rec_avail, oth_avail)

    headline = (
        f"Under these conditions, the {selected} strategy produced a {yield_dir} simulated yield "
        f"({rec_y:.2f} vs {oth_y:.2f}) and {avail_dir} water availability "
        f"({rec_avail * 100:.1f}% vs {oth_avail * 100:.1f}%) than the {other} strategy. "
        f"It used {rec_irr:.1f} mm of irrigation compared with {oth_irr:.1f} mm for {other}."
    )

    yield_change = ((y_a - y_t) / y_t * 100.0) if y_t else 0.0
    irrigation_change = ((irr_a - irr_t) / irr_t * 100.0) if irr_t else 0.0
    wue_change = ((w_a - w_t) / w_t * 100.0) if w_t else 0.0

    reasons = [
        f"jDE simulated yield: {y_a:.2f} vs {y_t:.2f} ({yield_change:+.1f}% vs threshold).",
        f"jDE water-use efficiency: {w_a:.4f} vs {w_t:.4f} ({wue_change:+.1f}% vs threshold).",
        f"jDE irrigation use: {irr_a:.2f} mm vs {irr_t:.2f} mm ({irrigation_change:+.1f}% vs threshold).",
    ]

    return {
        "selected": selected,
        "label": "Recommended under the fixed balanced objective",
        "headline": headline,
        "scores": {"threshold": round(score_t, 4), "adaptive": round(score_a, 4)},
        "reasons": reasons,
        "rule": "Internal balanced assessment: 60% simulated yield + 40% water-use efficiency, normalized between the two strategies for this run. The same rule is used for every user; no optimizer settings or seed are exposed.",
    }


@app.get("/health")
def health():
    return {"ok": True, "service": "AgriSmart Dashboard API", "version": "3.0.0"}


@app.get("/defaults")
def defaults():
    return {
        "initial_soil_moisture": float(config.INITIAL_SOIL_MOISTURE),
        "budget_mm": float(config.BUDGET),
        "decision_interval_days": int(config.DECISION_INTERVAL_DAYS),
        "horizon_decisions": int(config.HORIZON_DECISIONS),
        "max_irrigation_per_decision": float(config.I_MAX_PER_DECISION),
        "weather_source": "NASA POWER historical weather (project data layer)",
        "hidden_seed": int(config.RANDOM_SEED),
    }


def _find_research_csv() -> Path:
    for candidate in _RESEARCH_CSV_CANDIDATES:
        if candidate.exists():
            return candidate
    raise HTTPException(
        status_code=404,
        detail=(
            "final_analysis_summary.csv was not found. Place the validated "
            f"results CSV at {_RESEARCH_CSV_CANDIDATES[0]} (project root) "
            "or next to dashboard_api.py."
        ),
    )


@app.get("/research-results")
def research_results():
    """Serves the validated final research CSV as-is - the dashboard does
    not compute, estimate, or invent any of these numbers, it only reads
    and formats the file the project already produced."""
    csv_path = _find_research_csv()
    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read {csv_path.name}: {exc}") from exc

    rows = [{k: clean(v) for k, v in row.items()} for row in df.to_dict("records")]
    return {"source_file": csv_path.name, "rows": rows}


@app.post("/compare")
def compare(request: SimulationRequest):
    try:
        with temporary_config(request.initial_soil_moisture, request.budget_mm):
            # The seed remains an implementation detail for reproducible demos.
            adaptive = run_closed_loop(optimizer="jde", seed=config.RANDOM_SEED, verbose=False)
            threshold = run_threshold_baseline()
            assessment = assess_strategies(threshold, adaptive)

            return {
                "inputs": {
                    "initial_soil_moisture": float(config.INITIAL_SOIL_MOISTURE),
                    "budget_mm": float(config.BUDGET),
                    "weather_source": "NASA POWER weather season / existing project data layer",
                },
                "threshold": pack_result("Threshold Baseline", threshold),
                "adaptive": pack_result("Self-Adaptive DE (jDE)", adaptive),
                "assessment": assessment,
            }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/simulate")
def simulate(request: SimulationRequest):
    # Backward-compatible endpoint: returns the same side-by-side comparison.
    return compare(request)
