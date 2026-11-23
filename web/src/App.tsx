import { useEffect, useRef, useState } from "react";
import { scrollBehavior } from "./format";
import IntakeScreen from "./components/IntakeScreen";
import TeamScreen from "./components/TeamScreen";
import AdminScreen from "./components/AdminScreen";
import HowItWorks, { HowSummary, markHowSeen, seenHow } from "./components/HowItWorks";
import ThemeToggle from "./components/ThemeToggle";
import { useTheme } from "./theme";
import { adminFromUrl, markAdminSession } from "./admin";
import type { Api, Health, IntakeResponse, Plan, Profile, Sample } from "./types";

export const prettyModel = (m?: string | null) => (!m || /haiku-5-5/.test(m) ? "Claude Haiku 5.5" : m);

/** Anything the app may have saved in the browser. Start over clears all of it. */
export const DRAFT_KEYS = ["enough-lite-draft"];

export default function App({ api, mock = false, admin = adminFromUrl() }: { api: Api; mock?: boolean; admin?: boolean }) {
  const [theme, toggleTheme] = useTheme();
  useState(() => { if (admin) markAdminSession(); });
  const [health, setHealth] = useState<Health | null>(null);
  const [healthErr, setHealthErr] = useState(false);
  const [stage, setStage] = useState<"admin" | "intake" | "team">(admin ? "admin" : "intake");
  const [built, setBuilt] = useState<Profile | null>(null);          // the answers the plan was built from
  const [live, setLive] = useState<{ profile: Profile; canBuild: boolean } | null>(null); // the answers now, on page 1
  const [runId, setRunId] = useState(0);
  const [patch, setPatch] = useState<{ id: number; profile: Profile } | null>(null); // a correction made in the plan chat, for page 1
  const [planSS, setPlanSS] = useState<Plan["ss_basis"]>(null);   // the plan's Social Security start, for the panel on page 1
  const [load, setLoad] = useState<{ id: number; intake: IntakeResponse; name: string } | null>(null); // admin: a sample household for page 1
  const [epoch, setEpoch] = useState(0);
  const [returned, setReturned] = useState(0);   // times the person came back from the plan to change answers
  const [confirm, setConfirm] = useState(false);
  const [how, setHow] = useState(() => !admin && !seenHow());   // open once for a first-time visitor
  const main = useRef<HTMLElement>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealthErr(true));
  }, [api]);

  const go = (s: "admin" | "intake" | "team", fromAdmin = false) => {
    // from the admin list into the app, add a history entry so the browser's Back button returns to /admin
    if (fromAdmin && admin && typeof window !== "undefined") { try { window.history.pushState({ enough: "app" }, "", "/"); } catch { /* no history */ } }
    setStage(s);
    window.scrollTo({ top: 0, behavior: scrollBehavior() });
    requestAnimationFrame(() => main.current?.focus());
  };
  const howByHand = useRef(false);   // opened from the folded line, so focus moves to it
  const closeHow = () => { markHowSeen(); setHow(false); };
  // Back from the app to the admin list, and forward again
  useEffect(() => {
    if (!admin) return;
    const on = () => {
      if (adminFromUrl(window.location.pathname)) setStage("admin");
      else setStage((s) => (s === "admin" ? (built ? "team" : "intake") : s));
    };
    window.addEventListener("popstate", on);
    return () => window.removeEventListener("popstate", on);
  }, [admin, built]);
  const build = (p: Profile) => { setBuilt(p); setRunId((r) => r + 1); go("team"); };
  const startOver = () => {
    for (const k of DRAFT_KEYS) { try { localStorage.removeItem(k); sessionStorage.removeItem(k); } catch { /* storage blocked */ } }
    api.reset().catch(() => { /* the page is already clear; the server only drops its cost log */ });
    setBuilt(null); setLive(null); setPatch(null); setLoad(null); setPlanSS(null); setReturned(0); setConfirm(false); setEpoch((e) => e + 1); setRunId((r) => r + 1); setStage("intake");
    window.scrollTo({ top: 0 });
  };
  /** Admin: put a sample household on page 1 (all figures filled), and optionally go straight to its plan. */
  const openSample = (s: Sample, buildNow: boolean) => {
    setPatch(null); setPlanSS(null); setReturned(0); setConfirm(false);
    setLive(null);
    setLoad((x) => ({ id: (x?.id ?? 0) + 1, intake: s.intake, name: s.name }));
    setBuilt(buildNow ? (s.intake.profile as Profile) : null);
    setEpoch((e) => e + 1); setRunId((r) => r + 1);
    go(buildNow ? "team" : "intake", true);
  };
  const model = prettyModel(health?.model);
  const stale = !!built && !!live && JSON.stringify(live.profile) !== JSON.stringify(built);

  return (
    <div className="app">
      <a href="#main" className="skip">Skip to content</a>
      <header className={`top${stage === "team" ? " top-team" : ""}`}>
        <div className="brand">
          <h1 className="logo">Enough<span className="logo-dot" aria-hidden="true">.</span></h1>
          <p className="promise">Can you retire when you want? A team of AI advisers checks for you.</p>
        </div>
        {stage !== "admin" && <ol className="steps" aria-label="Steps">
          <li aria-current={stage === "intake" ? "step" : undefined}>{stage === "team" ? <button type="button" className="step-link" onClick={() => { setReturned((n) => n + 1); go("intake"); }}>← Change my answers</button> : "1 · About you"}</li>
          <li aria-current={stage === "team" ? "step" : undefined}>{stage === "intake" && built ? <button type="button" className="step-link" onClick={() => go("team")}>2 · Your plan →</button> : "2 · Your plan"}</li>
        </ol>}
        {confirm ? (
          <div className="confirm" role="group" aria-label="Start over">
            <span>Clear everything and start again?</span>
            <button type="button" className="btn btn-primary btn-small" onClick={startOver}>Yes, clear</button>
            <button type="button" className="btn btn-quiet btn-small" autoFocus onClick={() => setConfirm(false)}>Keep my answers</button>
          </div>
        ) : (
          <button type="button" className="btn btn-quiet btn-small start-over" onClick={() => setConfirm(true)}>Start over</button>
        )}
        <ThemeToggle theme={theme} onToggle={toggleTheme} />
        {(stage === "intake" || mock) && (
          <p className="note" hidden={stage !== "intake" && !mock}>
            {stage === "intake" && <>
              Runs on {model}. A plan costs under a cent; token costs show under Team talk.
              Your answers go to the AI only to build your plan; leave out names and account numbers.
            </>}
            {mock && <strong className="mock-tag"> Demo data</strong>}
          </p>
        )}
      </header>
      {(healthErr || (health && !health.ai_available)) && (
        <div className="banner" role="status">
          {healthErr ? "We can't reach the server right now. Answers may fail until it is back." : "The AI service is not available right now, so the advisers may not run."}
        </div>
      )}
      <main id="main" ref={main} tabIndex={-1}>
        {how && stage === "intake" && <HowItWorks onClose={closeHow} focus={howByHand.current} />}
        {!how && stage === "intake" && <HowSummary onOpen={() => { howByHand.current = true; setHow(true); }} />}
        {admin && <div hidden={stage !== "admin"}><AdminScreen api={api} onOpen={(s) => openSample(s, false)} onBuild={(s) => openSample(s, true)} /></div>}
        <div hidden={stage !== "intake"}>
          <IntakeScreen key={epoch} api={api} patch={patch} load={load} planSS={stale ? null : planSS ?? null} returned={returned} onBuild={build} onFirstSend={() => { if (how) closeHow(); }} onProfile={(profile, canBuild) => setLive({ profile, canBuild })} />
        </div>
        {built && (
          <div hidden={stage !== "team"}>
            <TeamScreen key={runId} api={api} profile={built} model={model} onPlan={(pl) => setPlanSS(pl?.ss_basis ?? null)} onBack={() => { setReturned((n) => n + 1); go("intake"); }}
              onProfileChange={(p) => { setBuilt(p); setPatch((x) => ({ id: (x?.id ?? 0) + 1, profile: p })); }} stale={stale} canRebuild={!!live?.canBuild} onRebuild={() => (live?.canBuild ? build(live.profile) : go("intake"))} />
          </div>
        )}
      </main>
      <footer className="foot muted small">Not financial advice: figures are estimates from simple models.</footer>
    </div>
  );
}
