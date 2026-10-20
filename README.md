# AgriSmart: Agricultural Optimization & Decision Support Dashboard

A full-stack agricultural optimization project combining a Python-based irrigation and crop-yield simulation engine with a FastAPI backend and a Next.js dashboard.

AgriSmart explores how optimization algorithms and soil-water modelling can support irrigation planning under limited water budgets. The project includes simulation experiments, budget sensitivity analysis, algorithm validation, and visualizations for evaluating agricultural outcomes.

## Key Features

- **Closed-loop irrigation simulation:** Simulates irrigation decisions over a growing season using a receding-horizon optimization approach.
- **Differential Evolution optimization:** Implements optimization logic and validation experiments for differential evolution and jDE-related parameters.
- **Soil-water modelling:** Models soil moisture using field capacity, wilting point, and irrigation inputs.
- **Crop-yield modelling:** Uses a Mitscherlich-based yield function with configurable parameters.
- **Budget-constrained optimization:** Evaluates irrigation strategies under a limited seasonal water budget.
- **Simulation analysis:** Generates CSV results and plots for comparing yield, water-use efficiency, water availability, irrigation, and budget utilization.
- **Full-stack dashboard:** Includes a Next.js frontend and a FastAPI backend for the dashboard application.

## Technology Stack

| Component | Technologies |
|---|---|
| Optimization and simulation | Python |
| Data processing | pandas |
| Backend API | FastAPI, Uvicorn, Pydantic |
| Frontend | Next.js, React, TypeScript |
| Styling | Tailwind CSS |
| Visualization | Recharts, generated analysis plots |
| Package management | pip, npm |

## Project Structure

```text
CN_Project/
├── agri_dashboard/
│   ├── backend/
│   │   ├── dashboard_api.py
│   │   ├── requirements.txt
│   │   └── README.md
│   └── frontend/
│       ├── app/
│       ├── components/
│       ├── package.json
│       ├── package-lock.json
│       └── .env.local.example
├── csv result/
│   ├── final_analysis_summary.csv
│   ├── fair_budget_summary.csv
│   └── ...
├── image results/
│   ├── final_comparison_plot.png
│   ├── final_yield_vs_budget.png
│   └── ...
├── closed_loop_simulation.py
├── config.py
├── data_layer.py
├── de_algorithm_validation.py
├── de_optimizer_engine.py
├── final_analysis.py
├── optimizer_seed_test.py
├── soil_water_model.py
├── yield_function.py
└── README.md
```

## Getting Started

### 1. Clone the repository


```bash
git clone https://github.com/titikshakashyap20/Agrismart.git
cd agrismart-dashboard
```

### 2. Set up the Python environment

From the repository root, create and activate a virtual environment.

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies for the optimization engine and analysis scripts:

```powershell
pip install -r requirements.txt
```

### 3. Start the FastAPI backend

Open a terminal at the repository root and run:

```powershell
pip install -r agri_dashboard/backend/requirements.txt
python -m uvicorn dashboard_api:app --reload --app-dir agri_dashboard/backend --host 127.0.0.1 --port 8000
```

The API should be available at `http://127.0.0.1:8000`. If enabled, interactive API documentation is available at `http://127.0.0.1:8000/docs`.

### 4. Start the Next.js frontend

Open a second terminal at the repository root and run:

```powershell
cd agri_dashboard/frontend
npm ci
Copy-Item .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000` in your browser.

The frontend uses `NEXT_PUBLIC_API_URL` to locate the backend. The supplied example points to `http://localhost:8000`.

Keep both the backend and frontend running while testing API-dependent dashboard features.

### 5. Run the optimization engine

Open another terminal at the repository root. Activate the virtual environment if necessary, then run:

```powershell
python closed_loop_simulation.py
```

Other available analysis scripts include:

- `de_algorithm_validation.py` — differential evolution validation experiments
- `optimizer_seed_test.py` — random-seed experiments
- `final_analysis.py` — final analysis and result generation

Run scripts individually and inspect their source code for expected inputs and output paths before starting experiments. Some scripts may take time to complete or regenerate result files.


## Configuration

The root `config.py` centralizes simulation parameters, including:

- Simulation location and season dates
- Soil-water model parameters
- Crop coefficient values
- Irrigation limits and seasonal budget
- Receding-horizon decision settings
- Differential Evolution and jDE parameters
- Yield-model constants
- Random seed for reproducibility

Review `config.py` before running experiments. Changing parameters may affect the simulation results.

## Results and Visualizations

The `csv result/` directory contains tabular outputs from the simulation and analysis experiments.

The `image results/` directory contains plots generated for analysis and comparison, including:

- Yield versus irrigation budget
- Water-use efficiency
- Water availability and irrigation patterns
- Budget utilization
- Algorithm validation
- Results across different random seeds

These outputs can be used to examine the behaviour of the optimization framework and compare experimental scenarios.

## Reproducibility

A random seed is configured in `config.py`. For reproducible experiments, keep the configuration fixed and ensure that all relevant sources of randomness are controlled by the implementation.

Record configuration changes when comparing experimental runs.

## Future Improvements

Potential extensions include:

- Expanded dashboard reporting and interactive comparisons
- More extensive evaluation across seasons and locations
- Additional optimization baselines
- Automated experiment tracking
- Improved deployment and testing workflows

## Contributing

Contributions, suggestions, and improvements are welcome. For substantial changes, document the experimental setup and explain how the changes affect the simulation or dashboard.


