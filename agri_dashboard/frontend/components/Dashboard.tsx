"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Daily = { day: number; soil_moisture: number; water_availability: number; drainage: number; irrigation_applied: number };
type Decision = { decision_day: number; irrigation_applied: number; horizon_fitness: number; horizon_budget?: number; budget_remaining: number };
type MethodResult = { method: string; summary: Record<string, number | string | null>; daily: Daily[]; decisions: Decision[] };
type CompareResult = {
  inputs: { initial_soil_moisture: number; budget_mm: number; weather_source: string };
  threshold: MethodResult;
  adaptive: MethodResult;
  assessment: { selected: string; label: string; headline: string; scores: { threshold: number; adaptive: number }; reasons: string[]; rule: string };
};

// Raw row shape exactly as it comes out of final_analysis_summary.csv via
// GET /research-results. Nothing here is invented client-side - every field
// is whatever the backend read from that file.
type ResearchCsvRow = {
  Budget: number; Method: string;
  Mean_Yield: number; Std_Yield: number | null;
  Mean_Irrigation: number; Std_Irrigation: number | null;
  Mean_WUE: number; Std_WUE: number | null;
  Mean_Availability: number; Std_Availability: number | null;
  Mean_Utilization: number; Std_Utilization: number | null;
  Baseline_Yield: number; Yield_Improvement_vs_Baseline_pct: number;
  JDE_minus_Vanilla_Yield: number;
};

type Defaults = {
  initial_soil_moisture: number; budget_mm: number;
  decision_interval_days: number; horizon_decisions: number;
  max_irrigation_per_decision: number; weather_source: string; hidden_seed: number;
};

function n(v: unknown, digits = 2) { return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "—"; }
function pct(v: unknown) { return typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(1)}%` : "—"; }
function metric(r: MethodResult, key: string) { return Number(r.summary[key] ?? 0); }

export default function Dashboard() {
  const [tab, setTab] = useState<"simulation" | "research">("simulation");
  const [initialSoil, setInitialSoil] = useState(180);
  const [budget, setBudget] = useState(150);
  const [budgetBounds, setBudgetBounds] = useState({ min: 50, max: 300 });
  const [data, setData] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [budgetView, setBudgetView] = useState<number | null>(null);

  const [research, setResearch] = useState<ResearchCsvRow[] | null>(null);
  const [researchError, setResearchError] = useState("");
  const [researchLoading, setResearchLoading] = useState(false);

  // Pull the project's actual configured defaults on load, instead of
  // guessing values in the frontend - what the user sees first is what
  // config.py actually says, not a placeholder.
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/defaults`);
        if (!res.ok) return;
        const d: Defaults = await res.json();
        setInitialSoil(d.initial_soil_moisture);
        setBudget(d.budget_mm);
        setBudgetBounds({ min: 10, max: Math.max(300, Math.round(d.budget_mm * 1.5)) });
      } catch {
        // Keep the hardcoded fallback values above if the backend isn't reachable yet.
      }
    })();
  }, []);

  async function loadResearch() {
    if (research || researchLoading) return;
    setResearchLoading(true); setResearchError("");
    try {
      const res = await fetch(`${API}/research-results`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || "Could not load research results.");
      const rows: ResearchCsvRow[] = json.rows;
      setResearch(rows);
      const budgets = Array.from(new Set(rows.map(r => r.Budget))).sort((a, b) => a - b);
      if (budgets.length) setBudgetView(budgets[budgets.length - 1]);
    } catch (e) {
      setResearchError(e instanceof Error ? e.message : "Could not load final_analysis_summary.csv.");
    } finally {
      setResearchLoading(false);
    }
  }

  useEffect(() => { if (tab === "research") loadResearch(); }, [tab]);

  async function runComparison() {
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API}/compare`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initial_soil_moisture: initialSoil, budget_mm: budget }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || "Simulation failed.");
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not connect to the Python backend.");
    } finally { setLoading(false); }
  }

  const timeline = useMemo(() => {
    if (!data) return [];
    const max = Math.max(data.threshold.daily.length, data.adaptive.daily.length);
    return Array.from({ length: max }, (_, i) => ({
      day: i,
      threshold: data.threshold.daily[i]?.soil_moisture ?? null,
      adaptive: data.adaptive.daily[i]?.soil_moisture ?? null,
    }));
  }, [data]);

  const irrigationTimeline = useMemo(() => {
    if (!data) return [];
    const max = Math.max(data.threshold.daily.length, data.adaptive.daily.length);
    return Array.from({ length: max }, (_, i) => ({
      day: i,
      Threshold: data.threshold.daily[i]?.irrigation_applied ?? 0,
      "Self-Adaptive DE": data.adaptive.daily[i]?.irrigation_applied ?? 0,
    }));
  }, [data]);

  const researchChart = (research ?? []).filter(r => r.Budget === budgetView);
  const availableBudgets = Array.from(new Set((research ?? []).map(r => r.Budget))).sort((a, b) => a - b);

  return <main className="min-h-screen">
    <header className="sticky top-0 z-10 border-b border-[#dce6dc] bg-[#f8faf7]/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] items-center justify-between px-6 pt-4">
        <div className="flex items-center gap-3"><div className="logo">🌱</div><div><div className="text-2xl font-black tracking-tight">AgriSmart</div><div className="text-xs text-[#6b7a70]">Adaptive irrigation decision-support simulator</div></div></div>
        <div className="hidden items-center gap-5 md:flex">
          <span className="status-note"><span className="status-dot status-dot--green"/>Closed-loop control</span>
          <span className="status-note" title="Historical daily weather from NASA's POWER project, via the existing project data layer"><span className="status-dot status-dot--blue"/>NASA POWER weather season</span>
        </div>
      </div>
      <div className="mx-auto max-w-[1400px] px-6 py-3">
        <div className="header-note">
          <span aria-hidden="true"></span>
          <p>Software simulation, not live farm hardware. Weather comes from historical NASA POWER records — soil moisture, irrigation decisions, and results shown are all simulated, not guaranteed real-world outcomes.</p>
        </div>
      </div>
    </header>

    <div className="grid-bg mx-auto min-h-[calc(100vh-73px)] max-w-[1500px] px-6 py-8">
      <div className="mx-auto max-w-[1400px]">
        <div className="mb-8 inline-flex rounded-2xl border border-[#dce6dc] bg-white p-1.5 shadow-sm">
          <button onClick={() => setTab("simulation")} className={`tab ${tab === "simulation" ? "active" : ""}`}>Interactive Simulation</button>
          <button onClick={() => setTab("research")} className={`tab ${tab === "research" ? "active" : ""}`}>Research Results</button>
        </div>

        {tab === "simulation" ? <>
          <section className="grid gap-6 lg:grid-cols-[390px_1fr]" key="sim-section">
            <div className="card p-6">
              <div className="eyebrow">Simple inputs</div>
              <h1 className="mt-2 text-4xl font-black tracking-tight">Simulate a field</h1>
              <p className="mt-3 text-sm leading-6 text-[#6b7a70]">Enter the conditions a normal user can understand. AgriSmart automatically compares the threshold method with the self-adaptive controller.</p>

              <label className="field-label">Initial soil moisture</label>
              <input className="number-input" type="number" min="0" step="1" value={initialSoil} onChange={e => setInitialSoil(Number(e.target.value))}/>
              <div className="hint">Starting water stored in the simulated soil profile.</div>

              <label className="field-label mt-7">Seasonal irrigation budget</label>
              <div className="flex items-center gap-3"><input className="w-full" type="range" min={budgetBounds.min} max={budgetBounds.max} step="10" value={budget} onChange={e => setBudget(Number(e.target.value))}/><div className="budget-value">{budget}<span>mm</span></div></div>
              <div className="hint">Maximum irrigation water available during the simulated season.</div>

              <div className="mt-6 rounded-2xl border border-[#dce6dc] bg-[#f5f9f4] p-4 text-sm leading-6 text-[#5e6e63]"><b>Weather stays the same for both strategies.</b><br/>The simulation uses the project's existing weather/data layer so the comparison is fair.</div>

              <button onClick={runComparison} disabled={loading} className="run-button mt-6">{loading ? "Running both strategies…" : "▶ Run AgriSmart"}</button>
              {error && <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-700">{error}</div>}
            </div>

            <div className="card p-6">
              <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start"><div><div className="eyebrow">Decision & control</div><h2 className="mt-2 text-3xl font-black tracking-tight">Same conditions. Two strategies.</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-[#6b7a70]">AgriSmart runs both controllers from the same starting state and weather. The adaptive controller repeatedly optimizes, executes the first decision, observes the new state, and optimizes again.</p></div>{data && <span className="pill green">Simulation complete</span>}</div>

              {!data ? <EmptyState/> : <>
                <div className="mt-6 grid gap-4 lg:grid-cols-2">
                  <MetricCard title="Threshold baseline" result={data.threshold}/>
                  <MetricCard title="Self-Adaptive DE (jDE)" result={data.adaptive} accent/>
                </div>

                <div className="mt-5 rounded-2xl bg-[#17301f] p-5 text-white">
                  <div className="text-xs font-black uppercase tracking-[.14em] text-[#b9d9c0]">🤖 AgriSmart assessment</div>
                  <div className="mt-2 flex flex-col justify-between gap-3 md:flex-row md:items-end"><div><div className="text-3xl font-black">{data.assessment.selected}</div><div className="mt-1 text-sm text-[#d5e4d8]">{data.assessment.label}</div></div><div className="rounded-xl bg-white/10 px-3 py-2 text-xs text-[#d5e4d8]">Score · Threshold {n(data.assessment.scores.threshold,3)} &nbsp;|&nbsp; jDE {n(data.assessment.scores.adaptive,3)}</div></div>
                  <p className="mt-4 text-sm leading-6 text-[#e7f0e8]">{data.assessment.headline}</p>
                  <div className="mt-4 grid gap-2 md:grid-cols-3">{data.assessment.reasons.map((r,i) => <div key={i} className="rounded-xl bg-white/10 p-3 text-xs leading-5 text-[#d5e4d8]">{r}</div>)}</div>
                </div>

                <div className="mt-5 rounded-2xl border border-[#dce6dc] bg-[#f8fbf7] p-4 text-xs leading-5 text-[#5e6e63]"><b>How the recommendation works:</b> the dashboard uses one fixed balanced rule for every simulation: 60% simulated yield and 40% water-use efficiency. You do not have to choose an objective. This is a transparent dashboard decision rule, not a claim that jDE is universally better.</div>

                <div className="mt-6 grid gap-6 lg:grid-cols-2">
                  <ChartCard title="Soil moisture over the season" subtitle="Both strategies receive the same weather sequence."><ResponsiveContainer width="100%" height="100%"><LineChart data={timeline}><CartesianGrid strokeDasharray="3 3" stroke="#e5ece5"/><XAxis dataKey="day" tick={{fontSize:11}}/><YAxis tick={{fontSize:11}}/><Tooltip/><Legend/><Line type="monotone" dataKey="threshold" name="Threshold" stroke="#8b6f47" strokeWidth={2.5} dot={false}/><Line type="monotone" dataKey="adaptive" name="Self-Adaptive DE" stroke="#287a46" strokeWidth={3} dot={false}/></LineChart></ResponsiveContainer></ChartCard>
                  <ChartCard title="Irrigation decisions" subtitle="Water actually applied during each simulated day."><ResponsiveContainer width="100%" height="100%"><BarChart data={irrigationTimeline}><CartesianGrid strokeDasharray="3 3" stroke="#e5ece5"/><XAxis dataKey="day" tick={{fontSize:11}}/><YAxis tick={{fontSize:11}}/><Tooltip/><Legend/><Bar dataKey="Threshold" fill="#8b6f47" radius={[5,5,0,0]}/><Bar dataKey="Self-Adaptive DE" fill="#287a46" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></ChartCard>
                </div>
              </>}
            </div>
          </section>
        </> : <ResearchTab
          loading={researchLoading}
          error={researchError}
          rows={research}
          availableBudgets={availableBudgets}
          budgetView={budgetView}
          setBudgetView={setBudgetView}
          chart={researchChart}
        />}
      </div>
    </div>
  </main>;
}

function EmptyState(){return <div className="mt-7 flex min-h-[430px] items-center justify-center rounded-2xl border border-dashed border-[#cbd8cc] bg-[#f8fbf7] text-center"><div><div className="text-5xl">🌾</div><div className="mt-4 text-lg font-black">Enter the field conditions and run AgriSmart</div><div className="mt-2 max-w-md text-sm leading-6 text-[#6b7a70]">The system will simulate both strategies on the same season, compare their results, and make one transparent balanced assessment.</div></div></div>}

function MetricCard({title,result,accent=false}:{title:string;result:MethodResult;accent?:boolean}){return <div className={`rounded-2xl p-5 ${accent?'bg-[#e7f3e9]':'bg-[#f4f7f2]'}`}><div className="text-sm font-black">{title}</div><div className="mt-4 grid grid-cols-2 gap-4"><SmallMetric label="Final yield" value={n(metric(result,'final_yield'))}/><SmallMetric label="Irrigation" value={`${n(metric(result,'total_irrigation_mm'))} mm`}/><SmallMetric label="Water-use efficiency" value={n(metric(result,'water_use_efficiency'),4)}/><SmallMetric label="Water availability" value={pct(metric(result,'mean_water_availability'))}/></div></div>}
function SmallMetric({label,value}:{label:string;value:string}){return <div><div className="text-[11px] font-bold text-[#6b7a70]">{label}</div><div className="mt-1 text-lg font-black">{value}</div></div>}
function ChartCard({title,subtitle,children}:{title:string;subtitle:string;children:React.ReactNode}){return <div className="rounded-2xl border border-[#dce6dc] bg-white p-4"><div className="mb-3"><div className="font-black">{title}</div><div className="text-xs text-[#6b7a70]">{subtitle}</div></div><div className="h-[300px]">{children}</div></div>}

function ResearchTab({loading,error,rows,availableBudgets,budgetView,setBudgetView,chart}:{
  loading:boolean; error:string; rows:ResearchCsvRow[]|null;
  availableBudgets:number[]; budgetView:number|null; setBudgetView:(n:number)=>void; chart:ResearchCsvRow[];
}){
  return <><section className="mb-6">
    <div className="eyebrow">Validated experiments</div>
    <h1 className="mt-2 text-4xl font-black tracking-tight">Research Results</h1>
    <p className="mt-2 max-w-3xl text-sm leading-6 text-[#6b7a70]">
      Read directly from <code>final_analysis_summary.csv</code>, the project&apos;s validated final analysis - nothing on this tab is computed by the dashboard itself.
      Optimizer rows are mean ± sample standard deviation across repeated runs; the threshold baseline is deterministic (no variation to report).
    </p>
  </section>

  {loading && <div className="card p-6 text-sm text-[#6b7a70]">Loading validated results…</div>}
  {error && <div className="card border-red-200 bg-red-50 p-6 text-sm text-red-700">{error}</div>}

  {!loading && !error && rows && rows.length > 0 && <>
    <section className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
      <div className="card p-6">
        <h2 className="font-black">Budget sensitivity</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {availableBudgets.map(b=><button key={b} onClick={()=>setBudgetView(b)} className={`rounded-xl px-4 py-2 text-xs font-black ${budgetView===b?'bg-[#287a46] text-white':'bg-[#f4f7f2] text-[#17301f]'}`}>{b} mm</button>)}
        </div>
        <div className="mt-6 h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart} margin={{left:5,right:15}}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5ece5"/>
              <XAxis dataKey="Method" tick={{fontSize:10}}/>
              <YAxis tick={{fontSize:11}}/>
              <Tooltip/>
              <Legend/>
              <Bar dataKey="Mean_Yield" name="Yield" fill="#287a46" radius={[5,5,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="card overflow-hidden">
        <div className="border-b border-[#dce6dc] p-6"><h2 className="font-black">Completed experiment summary</h2></div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-[#f4f7f2] text-xs uppercase tracking-wider text-[#6b7a70]">
              <tr><th className="px-4 py-3">Budget</th><th className="px-4 py-3">Method</th><th className="px-4 py-3">Yield</th><th className="px-4 py-3">Irrigation</th><th className="px-4 py-3">WUE</th><th className="px-4 py-3">Availability</th><th className="px-4 py-3">vs Baseline</th></tr>
            </thead>
            <tbody>
              {rows.map(r=><tr key={`${r.Budget}-${r.Method}`} className="border-t border-[#edf1ed]">
                <td className="px-4 py-3 font-bold">{r.Budget}</td>
                <td className="px-4 py-3">{r.Method}</td>
                <td className="px-4 py-3 font-black">{r.Mean_Yield.toFixed(2)} {r.Std_Yield ? <span className="text-xs font-normal text-[#6b7a70]">± {r.Std_Yield.toFixed(2)}</span> : null}</td>
                <td className="px-4 py-3">{r.Mean_Irrigation.toFixed(1)} mm</td>
                <td className="px-4 py-3">{r.Mean_WUE.toFixed(4)}</td>
                <td className="px-4 py-3">{(r.Mean_Availability*100).toFixed(1)}%</td>
                <td className="px-4 py-3">{r.Yield_Improvement_vs_Baseline_pct >= 0 ? "+" : ""}{r.Yield_Improvement_vs_Baseline_pct.toFixed(1)}%</td>
              </tr>)}
            </tbody>
          </table>
        </div>
      </div>
    </section>
    <section className="mt-6 card p-6">
      <h2 className="font-black">What the research view shows</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Info title="Baseline" text="A fixed threshold irrigation controller provides the non-optimized comparison."/>
        <Info title="Optimization" text="Vanilla DE is the optimizer baseline; self-adaptive DE (jDE) is the proposed adaptive variant."/>
        <Info title="Closed loop" text="The controller repeatedly uses the current simulated soil state and executes only the first horizon decision."/>
      </div>
    </section>
  </>}
  </>;
}
function Info({title,text}:{title:string;text:string}){return <div className="rounded-2xl bg-[#f4f7f2] p-5"><div className="font-black">{title}</div><p className="mt-2 text-sm leading-6 text-[#6b7a70]">{text}</p></div>}
