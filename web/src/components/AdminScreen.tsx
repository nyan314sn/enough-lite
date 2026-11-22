import { useCallback, useEffect, useRef, useState } from "react";
import { TIERS, VERDICT_WORDS, buildExport, clearBefore, diffRow, loadBefore, pool, rowFacts, saveBefore, summarize, type Change, type Metrics, type Saved } from "../admin";
import { usd } from "../format";
import { LEVEL_ICON, basicsLevel, type Level } from "../shortfall";
import type { Api, ModelCompare, Plan, Sample } from "../types";

// Admin mode (the hidden path /admin): pick sample households, open one in the app, build its plan, or build them all and compare with an earlier run.

type Result = { status: "running" } | { status: "done"; metrics: Metrics } | { status: "error"; message: string };
const AT_ONCE = 3;
const SAME: Change = { dir: "same", good: null, diff: 0 };

function Mark({ c, what }: { c: Change; what: string }) {
  if (c.dir === "same") return null;
  return (
    <span className={`adm-chg ${c.good ? "good" : "bad"}`}>
      <span aria-hidden="true">{c.dir === "up" ? "▲" : "▼"}</span>
      <span className="sr-only">{what} {c.dir === "up" ? "up" : "down"}, {c.good ? "better" : "worse"}: </span>
    </span>
  );
}

function Cell({ before, after, c, what, tone = "ok" }: { before: string | null; after: string; c: Change; what: string; tone?: Level }) {
  const mark = tone !== "ok" ? <span aria-hidden="true">{LEVEL_ICON[tone]} </span> : null;
  if (before == null) return <td className={`num${tone !== "ok" ? ` cell-${tone}` : ""}`}>{mark}{after}</td>;
  return (
    <td className={`num adm-pair${c.dir === "same" ? "" : c.good ? " adm-better" : " adm-worse"}${tone !== "ok" ? ` cell-${tone}` : ""}`}>
      <span className="adm-was"><span className="adm-lab">Before</span> {before}</span>
      <span className="adm-now"><span className="adm-lab">After</span> <Mark c={c} what={what} />{mark}{after}</span>
    </td>
  );
}

const WIN_MARK: Record<string, string> = { Tie: "= ", Haiku: "✓ ", "gpt-6-luna": "✓ " };

/** The model comparison: one compact table (winner in words, with a mark), the recommendation, cost, and the caveats behind an expander. */
function ModelCompareTable({ c }: { c: ModelCompare }) {
  const [a, b] = c.models;
  return (
    <>
      <div className="table-scroll" role="region" aria-label="Model comparison table" tabIndex={0}>
        <table className="adm-table adm-cmp">
          <caption className="sr-only">{a} against {b}: each measure, both results, the number of cases, and the winner</caption>
          <thead><tr><th scope="col">Metric</th><th scope="col">{a}</th><th scope="col">{b}</th><th scope="col">n</th><th scope="col">Winner</th></tr></thead>
          <tbody>
            {c.rows.map((r) => (
              <tr key={r.metric}>
                <th scope="row">{r.metric}</th>
                <td className="num">{r.haiku}</td>
                <td className="num">{r.gpt}</td>
                <td className="num">{r.n}</td>
                <td className={`adm-win${r.winner === "Tie" ? " tie" : ""}`}><span aria-hidden="true">{WIN_MARK[r.winner] ?? ""}</span>{r.winner === "Tie" ? "Tie" : `Winner: ${r.winner}`}{r.note ? <span className="small muted"> ({r.note})</span> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="adm-rec" data-testid="model-rec"><strong>Recommendation.</strong> {c.recommendation}</p>
      <p className="small muted">{c.date ? `Run ${c.date}. ` : ""}{c.cost_usd != null ? `The comparison cost about $${c.cost_usd.toFixed(2)}.` : ""}</p>
      {c.caveats.length > 0 && (
        <details className="adm-cav">
          <summary>Caveats</summary>
          <ul>{c.caveats.map((t) => <li key={t}>{t}</li>)}</ul>
        </details>
      )}
    </>
  );
}

const money = (n: number | null | undefined) => (n == null ? "n/a" : usd(n));
const word = (v: string | null | undefined) => (v ? VERDICT_WORDS[v] ?? v : "n/a");

export default function AdminScreen({ api, onOpen, onBuild }: { api: Api; onOpen: (s: Sample) => void; onBuild: (s: Sample) => void }) {
  const [samples, setSamples] = useState<Sample[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, Result>>({});
  const [running, setRunning] = useState(false);
  const [before, setBefore] = useState<Saved | null>(() => loadBefore());
  const [compare, setCompare] = useState<ModelCompare | null | "none">(null);
  const stop = useRef(false);
  const ctl = useRef<AbortController | null>(null);

  useEffect(() => { api.samples().then(setSamples).catch((e) => setErr((e as Error).message || "The sample households could not be loaded.")); }, [api]);

  useEffect(() => { let live = true; (api.modelCompare ? api.modelCompare() : Promise.reject(new Error("none"))).then((c) => { if (live) setCompare(c); }).catch(() => { if (live) setCompare("none"); }); return () => { live = false; }; }, [api]);

  const runOne = useCallback(async (s: Sample, signal: AbortSignal) => {
    setResults((r) => ({ ...r, [s.id]: { status: "running" } }));
    let plan: Plan | null = null;
    let message: string | null = null;
    try {
      await api.plan(s.intake.profile, (e) => {
        if (e.type === "plan") plan = e.plan;
        else if (e.type === "error") message = e.message;
      }, signal);
    } catch (e) { message = (e as Error).message || "The plan failed."; }
    if (signal.aborted) { setResults((r) => { const rest = { ...r }; delete rest[s.id]; return rest; }); return; }
    const done: Result = plan ? { status: "done", metrics: summarize(plan, s.intake.profile.retire_age) } : { status: "error", message: message ?? "No plan came back." };
    setResults((r) => ({ ...r, [s.id]: done }));
  }, [api]);

  async function runAll() {
    if (!samples || running) return;
    stop.current = false;
    const c = new AbortController();
    ctl.current = c;
    setResults({});
    setRunning(true);
    await pool(samples, AT_ONCE, (s) => runOne(s, c.signal), () => stop.current);
    setRunning(false);
  }
  function cancel() { stop.current = true; ctl.current?.abort(); }

  const finished = Object.values(results).filter((r) => r.status !== "running").length;
  const doneMetrics: Record<string, Metrics> = {};
  for (const [id, r] of Object.entries(results)) if (r.status === "done") doneMetrics[id] = r.metrics;
  const haveResults = Object.keys(doneMetrics).length > 0;

  function download() {
    if (!samples) return;
    const blob = new Blob([JSON.stringify(buildExport(samples, doneMetrics, before), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `enough-results-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-")}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  if (err) return <div className="alert" role="alert"><p>{err}</p></div>;
  if (!samples) return <p className="muted" role="status">Loading the sample households…</p>;

  const buttons = (s: Sample) => (
    <div className="adm-btns">
      <button type="button" className="btn btn-quiet btn-small adm-btn" onClick={() => onOpen(s)}>Open in app<span className="sr-only">: {s.name}</span></button>
      <button type="button" className="btn btn-primary btn-small adm-btn" onClick={() => onBuild(s)}>Build plan<span className="sr-only">: {s.name}</span></button>
    </div>
  );

  return (
    <section className="adm" aria-labelledby="adm-h">
      <h2 id="adm-h" className="h-screen">Admin <span className="muted">sample households</span></h2>
      <p className="muted">Open a household in the app to check or change it, build its plan, or build them all and compare with an earlier run.</p>

      <div className="card adm-run">
        <div className="adm-bar">
          <button type="button" className="btn btn-primary btn-big" disabled={running} onClick={() => void runAll()}>{running ? "Running…" : "Run all"}</button>
          {running && <button type="button" className="btn btn-quiet btn-big" onClick={cancel}>Stop</button>}
          <button type="button" className="btn btn-quiet btn-big" disabled={running || !haveResults} onClick={() => setBefore(saveBefore(doneMetrics))}>Save as before</button>
          <button type="button" className="btn btn-quiet btn-big" disabled={!haveResults} onClick={download}>Download results</button>
          {before && <button type="button" className="btn btn-quiet btn-big" onClick={() => { clearBefore(); setBefore(null); }}>Clear before</button>}
        </div>
        {(running || finished > 0) && (
          <>
            <div className="meter-bar big" role="progressbar" aria-label="Plans finished" aria-valuemin={0} aria-valuemax={samples.length} aria-valuenow={finished}><span style={{ width: `${(finished / samples.length) * 100}%` }} /></div>
            <p className="small muted num" role="status">{finished} of {samples.length} plans finished{running ? `, up to ${AT_ONCE} at a time` : ""}.</p>
          </>
        )}
        <p className="small muted">
          {before ? `Before run saved ${new Date(before.savedAt).toLocaleString()}. Run all again to see what changed.` : "No before run saved. Run all, then Save as before, change something, and run again."}
        </p>
      </div>

      {TIERS.map((t) => {
        const list = samples.filter((s) => s.tier === t.key);
        return (
          <section key={t.key} className="adm-tier" aria-labelledby={`adm-${t.key}`}>
            <h3 id={`adm-${t.key}`} className="adm-h">{t.label} <span className="muted">{list.length} households</span></h3>
            <div className="table-scroll" role="region" aria-label={`${t.label} households`} tabIndex={0}>
              <table className="adm-table">
                <caption className="sr-only">{t.label} households: ages, pay, savings, spending and state</caption>
                <thead><tr><th scope="col">Household</th><th scope="col">Age</th><th scope="col">Pay</th><th scope="col">Savings</th><th scope="col">Spending</th><th scope="col">State</th><th scope="col">Actions</th></tr></thead>
                <tbody>
                  {list.map((s) => {
                    const f = rowFacts(s.intake.profile);
                    return (
                      <tr key={s.id}>
                        <th scope="row" className="adm-name"><span>{s.name}</span><span className="small muted">{s.description}</span></th>
                        <td className="num">{f.ages}</td>
                        <td className="num">{usd(f.pay)}</td>
                        <td className="num">{usd(f.savings)}</td>
                        <td className="num">{f.spending == null ? "n/a" : usd(f.spending)}</td>
                        <td>{f.state}</td>
                        <td>{buttons(s)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}

      {(running || finished > 0) && (
        <section className="adm-results" aria-labelledby="adm-res">
          <h3 id="adm-res" className="adm-h">Results {before ? <span className="muted">before and after</span> : null}</h3>
          <div className="table-scroll" role="region" aria-label="Results" tabIndex={0}>
            <table className="adm-table adm-res-table">
              <caption className="sr-only">Plan results for each household{before ? ", with the saved before run beside each figure" : ""}</caption>
              <thead><tr>
                <th scope="col">Tier</th><th scope="col">Household</th><th scope="col">Verdict</th><th scope="col">Basics paid, of 100</th>
                <th scope="col">Can count on, a year</th><th scope="col">Short of goal, a year</th><th scope="col">Savings at retirement</th><th scope="col">Actions</th>
              </tr></thead>
              <tbody>
                {samples.map((s) => {
                  const r = results[s.id];
                  const m = r?.status === "done" ? r.metrics : null;
                  const b = before?.results[s.id] ?? null;
                  const d = m && b ? diffRow(b, m) : null;
                  return (
                    <tr key={s.id}>
                      <td>{TIERS.find((t) => t.key === s.tier)?.label}</td>
                      <th scope="row" className="adm-name">{s.name}</th>
                      {!r && <td colSpan={5} className="muted">Not run yet</td>}
                      {r?.status === "running" && <td colSpan={5} className="muted">Building…</td>}
                      {r?.status === "error" && <td colSpan={5} className="adm-fail">Failed: {r.message}</td>}
                      {m && (
                        <>
                          <Cell before={b && d ? word(b.verdict) : null} after={word(m.verdict)} c={d?.verdict ?? SAME} what="Verdict" tone={m.verdict === "falls_short" || m.verdict === "below_goal" ? "short" : m.verdict === "close" ? "close" : "ok"} />
                          <Cell before={b && d ? String(b.basics_of_100) : null} after={String(m.basics_of_100)} c={d?.basics ?? SAME} what="Basics paid" tone={basicsLevel(m.basics_of_100)} />
                          <Cell before={b && d ? money(b.count_on) : null} after={money(m.count_on)} c={d?.count_on ?? SAME} what="Can count on" />
                          <Cell before={b && d ? money(b.gap) : null} after={money(m.gap)} c={d?.gap ?? SAME} what="Short of goal" tone={(m.gap ?? 0) > 0 ? (m.verdict === "close" ? "close" : "short") : "ok"} />
                          <Cell before={b && d ? money(b.savings_at_retire) : null} after={money(m.savings_at_retire)} c={d?.savings ?? SAME} what="Savings at retirement" />
                        </>
                      )}
                      <td>{buttons(s)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {before && haveResults && <p className="small muted">Against the run saved {new Date(before.savedAt).toLocaleString()}. ▲ is up, ▼ is down; green is better and amber is worse.</p>}
        </section>
      )}
      <section className="adm-compare" aria-labelledby="adm-model" data-testid="model-compare">
        <h3 id="adm-model" className="adm-h">Model comparison {compare && compare !== "none" && <span className="muted">{compare.models.join(" and ")}{compare.date ? `, run ${compare.date}` : ""}</span>}</h3>
        {compare === null && <p className="muted" role="status">Loading the comparison…</p>}
        {compare === "none" && <p className="muted">No comparison run yet.</p>}
        {compare && compare !== "none" && <ModelCompareTable c={compare} />}
      </section>
    </section>
  );
}
