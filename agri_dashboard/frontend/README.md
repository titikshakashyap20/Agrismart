# AgriSmart Dashboard Frontend

## Run

```powershell
cd agri_dashboard\frontend
npm install
npm run dev
```

Open http://localhost:3000.

If the backend runs elsewhere, create `.env.local` from `.env.local.example` and set `NEXT_PUBLIC_API_URL`.

The Simulation tab is intentionally non-technical: it exposes only initial soil moisture and seasonal irrigation budget, both pre-filled from the backend's actual `config.py` defaults. It automatically compares Threshold vs Self-Adaptive DE and gives one fixed balanced 🤖 AgriSmart assessment. The Research Results tab reads the project's validated `final_analysis_summary.csv` (via the backend's `/research-results` endpoint) rather than showing any numbers baked into the frontend.
