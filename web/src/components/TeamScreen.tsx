import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import AskBox, { type WhatIfEntry } from "./AskBox";
import PlanCard from "./PlanCard";
import TeamPanel, { ROSTER, nodeState, type RunView, type ScenarioView } from "./TeamPanel";
import ScenarioTabs, { PANEL_ID } from "./ScenarioTabs";
import CompareTable, { type Col } from "./CompareTable";
import { MAX_WHATIFS, changeLine } from "./WhatIf";
import { scrollBehavior } from "../format";
import { emptyTeam, teamReducer } from "../sse";
import { addAsk, noAsk, type AskUse } from "./CostBlock";
import type { Api, CostSummary, PlanEvent, Plan, Profile, Tokens } from "../types";

// Screen 2. Left: the plan (a calm placeholder while the advisers work), then the chat. Right: "Your advisory team".
// Scenario tabs above the plan: Baseline, one tab per What If, "+ What if…" and Compare. Every What If is built on the baseline only
// (the chat always sends the baseline profile and plan), and each tab shows the full plan view. The team panel follows the selected tab.

type Action = PlanEvent | { type: "reset" };
const reducer = (s: typeof emptyTeam, e: Action) => (e.type === "reset" ? emptyTeam : teamReducer(s, e));

/** The usual wait, and the time so far. The server stops the AI at about 25 seconds and fills in from its own tools. */
export const WAIT_TEXT = "A plan usually takes 10 to 30 seconds.";
export function WaitTime() {
  const [s, setS] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setS((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return <p className="small muted num">{WAIT_TEXT}{s > 0 ? ` ${s} s so far.` : ""}</p>;
}

export default function TeamScreen({ api, profile, model, onBack, stale = false, canRebuild = true, onRebuild, onProfileChange, onPlan }: {
  api: Api; profile: Profile; model: string; onBack: () => void; stale?: boolean; canRebuild?: boolean; onRebuild?: () => void; onProfileChange?: (p: Profile) => void; onPlan?: (p: Plan | null) => void;
}) {
  const [team, dispatch] = useReducer(reducer, emptyTeam);
  const [ask, setAsk] = useState<AskUse>(noAsk);
  const [session, setSession] = useState<CostSummary | null>(null);
  const [run, setRun] = useState(0);
  const [whatifs, setWhatifs] = useState<WhatIfEntry[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [comparing, setComparing] = useState(false);
  const [focusTab, setFocusTab] = useState<{ id: number | null; n: number } | null>(null);
  const [cleared, setCleared] = useState(false);   // the What Ifs were dropped because a correction changed the baseline
  const count = useRef(0);
  const [rerun, setRerun] = useState<string[]>([]);
  const [composing, setComposing] = useState(false);   // "+ What if" was pressed: the plan is dimmed and the What If section is in focus
  const next = useRef(1);
  const initial = useRef(profile);                       // the answers this run was built from; a later correction does not restart it
  const [fixed, setFixed] = useState<Plan | null>(null);   // a plan rebuilt after a correction in the chat: it replaces the baseline
  const top = useRef<HTMLDivElement>(null);
  // a What If's own run of the team, streamed like the plan's: live while it works, then kept with its tab
  const [live, setLive] = useState<RunView | null>(null);
  const liveRef = useRef<RunView | null>(null);
  const [runs, setRuns] = useState<Record<number, RunView>>({});
  const onRunEvent = useCallback((e: PlanEvent, name: string) => {
    let r = liveRef.current;
    if (e.type === "whatif_start") r = { label: name, estimate: e.estimate, team: emptyTeam, working: true };
    else if (r) r = { ...r, team: teamReducer(r.team, e) };
    else return;
    liveRef.current = r;
    setLive(r);
  }, []);
  const onRunEnd = useCallback(() => { liveRef.current = null; setLive(null); }, []);

  useEffect(() => {
    const ctl = new AbortController();
    dispatch({ type: "reset" });
    setAsk(noAsk); setSession(null);
    setWhatifs([]); setActive(null); setFixed(null); setComparing(false); setCleared(false);
    api.plan(initial.current, (e) => { if (!ctl.signal.aborted) dispatch(e); }, ctl.signal)
      .catch((err) => { if (!ctl.signal.aborted) dispatch({ type: "error", message: (err as Error).message || "Something went wrong." }); });
    return () => ctl.abort();
  }, [api, run]);

  const addCost = useCallback((usd: number, tokens?: Tokens | number | null) => setAsk((x) => addAsk(x, usd, tokens)), []);
  const onWhatIf = useCallback((e: Omit<WhatIfEntry, "id">) => {
    if (count.current >= MAX_WHATIFS) return null;   // the chat says to remove one first
    const id = next.current++;
    const r = liveRef.current;
    if (r) setRuns((m) => ({ ...m, [id]: { ...r, working: false } }));
    setComposing(false);
    count.current += 1;
    setWhatifs((w) => [...w, { ...e, id }]);
    setActive(id);
    setComparing(false);
    requestAnimationFrame(() => top.current?.scrollIntoView?.({ block: "start", behavior: scrollBehavior() }));
    return id;
  }, []);
  const open = (id: number | null) => {
    setActive(id);
    setComparing(false);
    requestAnimationFrame(() => top.current?.scrollIntoView?.({ block: "start", behavior: scrollBehavior() }));
  };

  // the session total from the server, once the plan is done and again after each question or What If
  useEffect(() => {
    if (!team.done || !api.costs) return;
    let live = true;
    api.costs().then((c) => { if (live) setSession(c); }).catch(() => { /* the run total still shows */ });
    return () => { live = false; };
  }, [api, team.done, ask.calls, run]);

  const plan = fixed ?? team.plan;
  useEffect(() => { onPlan?.(plan ?? null); }, [plan]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { count.current = whatifs.length; }, [whatifs.length]);
  const onChange = useCallback((p: Profile, pl: Plan) => {
    setCleared(count.current > 0); setFixed(pl); setWhatifs([]); setActive(null); setComparing(false); onProfileChange?.(p);
  }, [onProfileChange]);
  const remove = (id: number) => {
    const i = whatifs.findIndex((w) => w.id === id);
    if (i < 0) return;
    const left = whatifs[i - 1]?.id ?? null;   // the tab to the left, or the baseline
    const rest = whatifs.filter((w) => w.id !== id);
    setWhatifs(rest);
    if (rest.length === 0) setComparing(false);
    if (active === id) { setActive(left); setFocusTab({ id: left, n: Date.now() }); }
    else setFocusTab({ id: comparing && rest.length > 0 ? null : active, n: Date.now() });
  };
  const newWhatIf = () => {
    setComposing(true);
    const el = document.getElementById("ask-input") as HTMLInputElement | null;
    el?.scrollIntoView?.({ block: "center", behavior: scrollBehavior() });
    el?.focus();
  };
  const cancelCompose = () => { setComposing(false); requestAnimationFrame(() => document.getElementById("scen-add")?.focus()); };
  useEffect(() => {
    if (!composing) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") cancelCompose(); };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [composing]);
  const dim = composing || rerun.length > 0;
  const working = !team.done;
  const doneN = ROSTER.filter((r) => nodeState(team, r.key) === "done").length;
  const cur = whatifs.find((w) => w.id === active) ?? null;
  const shownCur = comparing ? null : cur;
  const view: ScenarioView | null = shownCur ? { label: shownCur.name, text: shownCur.text, tokens: shownCur.tokens, usd: shownCur.cost_usd } : null;
  const panelRun = live ?? (shownCur ? runs[shownCur.id] ?? null : null);
  const status = live ? `Working on: ${live.label}` : rerun.length ? "Starting your advisers on this What If…" : view ? (panelRun ? `Showing the What If “${view.label}”. Select an adviser to read their work on it.` : `Showing the What If “${view.label}”. The advisers' notes are from the baseline run.`) : working ? `Each adviser checks one part of your plan, using ${model}.` : team.error ? "The team stopped." : "Done. Select an adviser to read their work.";
  const cols: Col[] = plan ? [{ key: "base", label: "Baseline", plan, retire: plan.already_retired ? null : profile.retire_age ?? null }, ...whatifs.map((w) => ({ key: String(w.id), label: w.name, full: w.q, plan: w.plan, retire: plan.already_retired ? null : w.retireAfter ?? profile.retire_age ?? null }))] : [];

  return (
    <div className="plan-screen">
      <div className="plan-main" ref={top}>
        {stale && plan && (
          <div className="stale" role="status">
            <span><strong>Your answers changed.</strong> This plan is out of date.</span>
            <button type="button" className="btn btn-primary btn-small" onClick={onRebuild}>{canRebuild ? "Rebuild plan" : "Finish your answers"}</button>
          </div>
        )}
        {!plan && !team.error && (
          <section className="card placeholder" aria-busy="true" aria-labelledby="ph-h">
            <h2 id="ph-h" className="h-screen">Your advisers are working…</h2>
            <p className="muted">They check your money, your family and the rules, then pass the results to the lead adviser.</p>
            <div className="meter-bar big" role="progressbar" aria-label="Advisers finished" aria-valuemin={0} aria-valuemax={ROSTER.length} aria-valuenow={doneN}><span style={{ width: `${(doneN / ROSTER.length) * 100}%` }} /></div>
            <p className="small muted num" role="status">{doneN} of {ROSTER.length} advisers finished</p>
            <WaitTime />
          </section>
        )}
        {team.error && (
          <div className="alert" role="alert">
            <p>{team.error}</p>
            <div className="row">
              <button type="button" className="btn btn-primary" onClick={() => setRun((r) => r + 1)}>Try again</button>
              <button type="button" className="btn btn-quiet" onClick={onBack}>Change my answers</button>
            </div>
          </div>
        )}
        {plan && (
          <>
            <ScenarioTabs items={whatifs} active={active} comparing={comparing} onSelect={open} onRemove={remove} onNew={newWhatIf} onCompare={() => { setComparing((c) => !c); requestAnimationFrame(() => top.current?.scrollIntoView?.({ block: "start", behavior: scrollBehavior() })); }} focusTab={focusTab} />
            {whatifs.length > 0 && stale && <p className="small muted scen-note" role="status" data-testid="scen-stale">Rebuilding the plan clears these What Ifs, because they were built on your old answers.</p>}
            {cleared && whatifs.length === 0 && <p className="small muted scen-note" role="status" data-testid="scen-cleared">Your What Ifs were cleared, because they were built on your old answers.</p>}
            <div id={PANEL_ID} role="tabpanel" aria-labelledby={comparing ? undefined : `tab-${cur?.id ?? "base"}`} aria-label={comparing ? "Compare" : undefined} tabIndex={-1} className={`scen-panel${dim ? " dimmed" : ""}`} aria-hidden={dim || undefined} {...(dim ? ({ inert: "" } as object) : {})}>
              {comparing
                ? <CompareTable cols={cols} onOpen={(k) => open(k === "base" ? null : Number(k))} />
                : cur
                  ? <PlanCard key={cur.id} plan={cur.plan} retireAge={cur.retireAfter ?? profile.retire_age} scenario={{ name: cur.name, baseline: plan, change: changeLine(cur.q, plan, profile.retire_age, cur.retireAfter), text: cur.text, citations: cur.citations }} />
                  : <PlanCard plan={plan} retireAge={profile.retire_age} />}
            </div>
          </>
        )}
        {plan && <AskBox api={api} profile={profile} plan={plan} onCost={addCost} onWhatIf={onWhatIf} onOpen={open} onAsking={(a) => { if (a.length) setComposing(false); setRerun(a); }} onChange={onChange} stale={stale} canRebuild={canRebuild} onRebuild={onRebuild} whatifIds={whatifs.map((w) => w.id)} onRunEvent={onRunEvent} onRunEnd={onRunEnd} composing={composing} onCancel={cancelCompose} full={whatifs.length >= MAX_WHATIFS} />}
      </div>
      <TeamPanel team={team} rerun={rerun} ask={ask} session={session} status={status} scenario={view} run={panelRun} />
    </div>
  );
}
