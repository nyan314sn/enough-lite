import { useEffect, useRef, useState } from "react";
import AgentPortrait, { type AgentKey } from "../figure/Advisers";
import { cents } from "../format";
import RosterLines, { type Pulse } from "./RosterLines";
import type { AgentCard, Handoff, TeamState } from "../sse";
import CostBlock, { noAsk, type AskUse, type ScenarioUse } from "./CostBlock";
import type { CostSummary } from "../types";

// "Your advisory team": the right-hand panel. Seven portraits, each idle (dim), working (a teal ring that breathes) or done (a check).
// Click one to read its finding. Below: the newest tool call, the compact cost meter and "Team talk", the log of handoffs.

export type NodeState = "idle" | "working" | "done";

export const ROSTER: { key: AgentKey; name: string; role: string }[] = [
  { key: "adviser", name: "Lead adviser", role: "Puts it together" },
  { key: "intake", name: "Intake", role: "Takes your facts" },
  { key: "longevity", name: "Longevity", role: "How long you may live" },
  { key: "markets", name: "Markets", role: "Tests your money" },
  { key: "family", name: "Family", role: "Kids, pets, home" },
  { key: "tax", name: "Tax", role: "What you keep" },
  { key: "research", name: "Research", role: "Checks the rules" },
];
export const nameOf = (a: string) => ROSTER.find((r) => r.key === a)?.name ?? a;

/** State of one adviser, from the stream. Intake finished before the team started, so it counts as done unless the stream says otherwise. */
export function nodeState(team: Pick<TeamState, "agents">, agent: string, intakeDone = true): NodeState {
  const a = team.agents.find((x) => x.agent === agent);
  if (a) return a.status;
  return agent === "intake" && intakeDone ? "done" : "idle";
}

export function useCompact(q = "(max-width: 860px)") {
  const get = () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(q).matches : false);
  const [c, setC] = useState(get);
  useEffect(() => {
    if (!window.matchMedia) return;
    const m = window.matchMedia(q);
    const on = () => setC(m.matches);
    m.addEventListener?.("change", on);
    return () => m.removeEventListener?.("change", on);
  }, [q]);
  return c;
}

export function CostMeter({ usd, budget }: { usd: number; budget: number | null; tokens?: number }) {
  const pct = budget ? Math.min(100, (usd / budget) * 100) : 0;
  return (
    <div className="meter" aria-label="AI cost so far">
      <div className="meter-top">
        <span>AI cost <strong className="num">{cents(usd)}</strong>{budget != null && <span className="muted"> of {cents(budget)}</span>}</span>
        
      </div>
      {budget != null && (
        <div className="meter-bar" role="meter" aria-label="AI cost against the limit" aria-valuemin={0} aria-valuemax={budget} aria-valuenow={usd} aria-valuetext={`${cents(usd)} of ${cents(budget)}`}>
          <span style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}

function Detail({ a, state, name }: { a: AgentCard | undefined; state: NodeState; name: string }) {
  if (!a) {
    if (name === "Intake" && state === "done") return <p className="muted small">Intake read your answers and wrote down the facts the other advisers use. It finished before the team started.</p>;
    return <p className="muted small">{state === "done" ? `${name} finished before the team started.` : `${name} has not started yet.`}</p>;
  }
  return (
    <div className="detail">
      {a.finding ? (
        <div className="finding">
          <p className="finding-h">{a.finding.headline}</p>
          {a.finding.details.length > 0 && <ul>{a.finding.details.map((d, k) => <li key={k}>{d}</li>)}</ul>}
        </div>
      ) : <p className="muted small">Working…</p>}
    </div>
  );
}

/** On a What If tab: what the server sent back for it. It sends the reply and its cost, not new findings or talk from each adviser. */
export interface ScenarioView extends ScenarioUse { text: string }

export default function TeamPanel({ team, intakeDone = true, rerun = [], ask = noAsk, session = null, status, scenario = null }: {
  team: TeamState; intakeDone?: boolean; rerun?: string[]; ask?: AskUse; session?: CostSummary | null; status: string; scenario?: ScenarioView | null;
}) {
  const compact = useCompact();
  const [open, setOpen] = useState(true);
  const [pick, setPick] = useState<AgentKey | null>(null);

  // on a phone the panel folds away once the plan has arrived
  const folded = useRef(false);
  useEffect(() => {
    if (team.plan && compact && !folded.current) { folded.current = true; setOpen(false); }
  }, [team.plan, compact]);

  // the newest tool call shows for a few seconds; a handoff pings its recipient
  const [tool, setTool] = useState<{ agent: string; summary: string } | null>(null);
  useEffect(() => {
    if (!team.lastTool) { setTool(null); return; }
    setTool({ agent: team.lastTool.agent, summary: team.lastTool.summary });
    const t = setTimeout(() => setTool(null), 4500);
    return () => clearTimeout(t);
  }, [team.lastTool?.seq]);
  const [ping, setPing] = useState<string | null>(null);
  const [pulse, setPulse] = useState<Pulse | null>(null);
  useEffect(() => {
    const h = team.handoffs[team.handoffs.length - 1];
    if (!h) { setPing(null); setPulse(null); return; }
    setPulse({ from: h.from, to: h.to, n: h.id, text: h.message });
    setPing(h.to);
    const t = setTimeout(() => setPing(null), 1200);
    const t2 = setTimeout(() => setPulse(null), 3200);
    return () => { clearTimeout(t); clearTimeout(t2); };
  }, [team.handoffs.length]);

  const stateOf = (k: string): NodeState => (rerun.includes(k) ? "working" : nodeState(team, k, intakeDone));
  const working = ROSTER.filter((r) => stateOf(r.key) === "working").map((r) => r.name);
  const show = !compact || open;

  return (
    <aside className="team-panel card" aria-labelledby="team-h" data-testid="team-panel">
      {compact
        ? <h2 id="team-h" className="h-panel h-toggle"><button type="button" aria-expanded={open} aria-controls="team-body" onClick={() => setOpen((o) => !o)}>Your advisory team <span className="muted">{working.length ? `${working.length} working` : "ready"}</span><span aria-hidden="true">{open ? "▴" : "▾"}</span></button></h2>
        : <h2 id="team-h" className="h-panel">Your advisory team</h2>}
      <div id="team-body" hidden={!show}>
        <p className="muted small team-status" role="status">{status}</p>
        <RosterLines advisers={ROSTER.filter((r) => r.key !== "adviser").map((r) => r.key)} states={Object.fromEntries(ROSTER.map((r) => [r.key, stateOf(r.key)]))} pulse={pulse}>
        <ul className="roster">
          {ROSTER.map((r) => {
            const st = stateOf(r.key);
            return (
              <li key={r.key} className={r.key === "adviser" ? "lead" : undefined}>
                <button type="button" className={`node node-${r.key} ${st}${ping === r.key ? " ping" : ""}${pick === r.key ? " picked" : ""}`} data-agent={r.key} data-state={st}
                  aria-pressed={pick === r.key} onClick={() => setPick((p) => (p === r.key ? null : r.key))}>
                  <span className="node-fig">
                    <AgentPortrait agent={r.key} />
                    {st === "done" && <span className="node-check" aria-hidden="true">✓</span>}
                  </span>
                  <span className="badge">{r.name}</span>
                  <span className="sr-only">, {st === "done" ? "finished" : st === "working" ? "working" : "waiting"}. {r.role}.</span>
                </button>
              </li>
            );
          })}
        </ul>
        </RosterLines>
        {tool && <p key={team.lastTool?.seq} className="now" data-testid="node-tool"><span className="now-who">{nameOf(tool.agent)}</span> {tool.summary}</p>}
        {scenario && (
          <div className="detail-box scen-said" data-testid="scenario-said">
            <p className="h-mini">This What If</p>
            <p className="muted small">The advisers' findings and Team talk were not repeated for it. What you read below is from the baseline run. The reason is under "Why" in the tab.</p>
          </div>
        )}
        {pick
          ? <div className="detail-box"><p className="h-mini">{nameOf(pick)}<span className="muted"> · {ROSTER.find((r) => r.key === pick)?.role}{scenario ? " · baseline run" : ""}</span></p><Detail a={team.agents.find((a) => a.agent === pick)} state={stateOf(pick)} name={nameOf(pick)} /></div>
          : <p className="muted small hint">Select an adviser to read their finding.</p>}
        <TeamTalk handoffs={team.handoffs} caption={scenario ? "Team talk, baseline run" : undefined} />
        <CostBlock team={team} ask={ask} session={session} scenario={scenario} />
        <p className="sr-only" role="status">{working.length ? `Working now: ${working.join(", ")}.` : ""}</p>
      </div>
    </aside>
  );
}

/** The height for the talk log so that it shows only whole rows: from the top of the first row that fits (with every later row) to the end.
 *  tops are the rows' offsets in the list, total its scroll height, max the most the log may show. Returns null when everything fits. */
export function wholeRowsHeight(tops: number[], total: number, max: number): { height: number; scrollTo: number } | null {
  if (tops.length === 0 || total <= max) return null;
  let i = tops.findIndex((t) => total - t <= max);
  if (i < 0) i = tops.length - 1;
  return { height: total - tops[i], scrollTo: tops[i] };
}

export function TeamTalk({ handoffs, caption = "Team talk" }: { handoffs: Handoff[]; caption?: string }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const fit = () => {
      const el = box.current;
      if (!el) return;
      el.style.maxHeight = "";
      const max = el.clientHeight;
      const r = wholeRowsHeight(Array.from(el.querySelectorAll<HTMLElement>(".talk-row")).map((x) => x.offsetTop), el.scrollHeight, max);
      if (r) { el.style.maxHeight = `${r.height}px`; el.scrollTop = r.scrollTo; } else el.scrollTop = el.scrollHeight;
    };
    fit();
    window.addEventListener("resize", fit);
    // on a phone the panel is folded when the rows arrive; fit them once it opens
    const ro = typeof ResizeObserver !== "undefined" && box.current ? new ResizeObserver(() => { if (box.current && box.current.clientHeight > 0 && !box.current.dataset.fit) { box.current.dataset.fit = "1"; fit(); } }) : null;
    if (box.current) delete box.current.dataset.fit;
    if (ro && box.current) ro.observe(box.current);
    return () => { window.removeEventListener("resize", fit); ro?.disconnect(); };
  }, [handoffs.length]);
  return (
    <section className="talk" aria-labelledby="talk-h">
      <h3 id="talk-h" className="h-mini">{caption}</h3>
      {handoffs.length === 0
        ? <p className="muted small talk-empty">The advisers will pass notes to each other here.</p>
        : (
          <div className="talk-log" ref={box} role="log" aria-label="Team talk" tabIndex={0}>
            <ol className="talk-rows">
              {handoffs.map((h, i) => (
                <li key={h.id} className={`talk-row${i === handoffs.length - 1 ? " newest" : ""}`} data-from={h.from} data-to={h.to}>
                  <span className="talk-who"><strong>{nameOf(h.from)}</strong> <span aria-label="to">→</span> <strong>{nameOf(h.to)}</strong></span>
                  <span className="talk-msg">{h.message}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
    </section>
  );
}
