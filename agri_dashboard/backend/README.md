# AgriSmart Dashboard Backend

This backend is a presentation/API layer over the existing AgriSmart project. It does not reimplement the agricultural model, the soil-water simulation, or the optimizers.

## Run from the project root

The project root is the folder that already contains your `config.py`, `closed_loop_simulation.py`, `yield_function.py`, `soil_water_model.py`, `de_optimizer_engine.py`, and `data_layer.py`. Place the `agri_dashboard/` folder inside that same directory (as a sibling of those files), then run:

```powershell
python -m pip install -r agri_dashboard\backend\requirements.txt
python -m uvicorn agri_dashboard.backend.dashboard_api:app --reload --port 8000
```

Run this command from the project root itself (the folder one level above `agri_dashboard\`), not from inside `agri_dashboard\backend\`.

The API imports `config.py`, `closed_loop_simulation.py`, and the other existing project modules directly from the project root - it resolves that root automatically from its own file location, so it does not matter what you name the top-level project folder.

## Validated research results CSV

Place your final validated `final_analysis_summary.csv` at the project root (next to `config.py`) or directly inside `agri_dashboard\backend\`. `GET /research-results` reads this file as-is and serves it to the Research Results tab - if the file isn't found there, that endpoint returns a 404 explaining where to put it. The dashboard never computes or invents these numbers itself.

## Endpoints

- `GET /health` - basic liveness check.
- `GET /defaults` - the project's actual configured defaults (`config.INITIAL_SOIL_MOISTURE`, `config.BUDGET`, etc.), so the frontend's starting values always match your real configuration instead of guessing.
- `GET /research-results` - the validated CSV above, as JSON rows.
- `POST /compare` - runs **both** the threshold baseline and the self-adaptive DE closed-loop controller using the same user-supplied initial soil moisture and seasonal irrigation budget. The optimizer seed is deliberately hidden and fixed internally for reproducible demonstrations.

The dashboard uses one fixed balanced assessment rule (60% yield, 40% WUE) rather than asking a non-technical user to choose an optimization objective, and reports whichever strategy actually wins under the given inputs - it does not hardcode jDE as the winner.
