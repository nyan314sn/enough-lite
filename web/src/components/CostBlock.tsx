import { cents } from "../format";
import type { TeamState } from "../sse";
import type { CostSummary, Tokens } from "../types";
import { nameOf } from "./TeamPanel";

// "Token costs": under Team talk. The tokens and dollars of this plan run, then what the follow-up questions and What Ifs added,
// then the session total. The per-adviser table sits behind an expander.

export interface AskUse { usd: number; input: number; cached: number; output: number; calls: number }
export const noAsk: AskUse = { usd: 0, input: 0, cached: 0, output: 0, calls: 0 };

/** Fold one answer's tokens and cost into the running follow-up total. `tokens` may be a number (old servers) or the three counts. */
export function addAsk(a: AskUse, usd: number, tokens?: Tokens | number | null): AskUse {
  const t = tokens && typeof tokens === "object" ? tokens : { input: typeof tokens === "number" ? tokens : 0, cached: 0, output: 0 };
  return { usd: a.usd + usd, input: a.input + t.input, cached: a.cached + t.cached, output: a.output + t.output, calls: a.calls + 1 };
}

const n = (x: number) => Math.round(x).toLocaleString("en-US");

export function runTotals(team: Pick<TeamState, "agents" | "cost">) {
  const t = { input: 0, cached: 0, output: 0, usd: 0 };
  for (const a of team.agents) {
    if (!a.tokens) continue;
    t.input += a.tokens.input; t.cached += a.tokens.cached; t.output += a.tokens.output; t.usd += a.cost_usd ?? 0;
  }
  return { ...t, usd: Math.max(t.usd, team.cost.total_usd) };
}

/** A What If tab shows that What If's own tokens and cost; the server may not report them (then the figures say so). */
export interface ScenarioUse { label: string; tokens?: Tokens | number | null; usd?: number | null }

export default function CostBlock({ team, ask, session, scenario = null }: { team: Pick<TeamState, "agents" | "cost" | "done" | "plan">; ask: AskUse; session: CostSummary | null; scenario?: ScenarioUse | null }) {
  const planRun = runTotals(team);
  const st = scenario?.tokens && typeof scenario.tokens === "object" ? scenario.tokens : scenario?.tokens != null ? { input: Number(scenario.tokens), cached: 0, output: 0 } : null;
  const known = !!scenario && (st != null || scenario.usd != null);
  const run = scenario ? { input: st?.input ?? 0, cached: st?.cached ?? 0, output: st?.output ?? 0, usd: scenario.usd ?? 0 } : planRun;
  const dash = (x: number) => (scenario && !known ? "—" : n(x));
  const rows = team.agents.filter((a) => a.tokens);
  const total = session ? session.total_usd : planRun.usd + ask.usd;
  const waiting = !team.done && !team.plan;
  return (
    <section className="costblock" aria-labelledby="cost-h" data-testid="cost-block">
      <h3 id="cost-h" className="h-mini">Token costs</h3>
      <dl className="cost-grid">
        <div><dt>Input tokens</dt><dd className="num" data-testid="cost-input">{dash(run.input)}</dd></div>
        <div><dt>Cached input tokens</dt><dd className="num" data-testid="cost-cached">{dash(run.cached)}</dd></div>
        <div><dt>Output tokens</dt><dd className="num" data-testid="cost-output">{dash(run.output)}</dd></div>
        <div className="cost-usd"><dt>{scenario ? "This What If" : "This plan"}</dt><dd className="num" data-testid="cost-run">{scenario && !known ? "—" : cents(run.usd)}{waiting && !scenario ? " so far" : ""}</dd></div>
      </dl>
      {scenario && <p className="small muted" data-testid="cost-scenario">{known ? `These are the tokens and cost of the What If “${scenario.label}” alone.` : "The server did not report tokens or cost for this What If. It is counted in the session total."}</p>}
      {ask.calls > 0 && (
        <p className="small muted num" data-testid="cost-ask">Questions and What Ifs ({ask.calls}): {cents(ask.usd)}, {n(ask.input + ask.cached + ask.output)} tokens. Not in the run cost above.</p>
      )}
      <p className="cost-total num" data-testid="cost-session"><span>Session total</span> <strong>{cents(total)}</strong>{session?.budget?.session_usd != null && <span className="muted small"> of {cents(session.budget.session_usd)} session limit</span>}</p>
      {(rows.length > 0 || ask.calls > 0) && (
        <details className="cost-detail">
          <summary>Token costs by adviser</summary>
          <div className="table-scroll">
            <table className="cost-table" data-testid="cost-table">
              <caption className="sr-only">Tokens and cost for each adviser</caption>
              <thead><tr><th scope="col">Adviser</th><th scope="col">In</th><th scope="col">Cached</th><th scope="col">Out</th><th scope="col">Cost</th></tr></thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.agent}><th scope="row">{nameOf(a.agent)}</th><td className="num">{n(a.tokens!.input)}</td><td className="num">{n(a.tokens!.cached)}</td><td className="num">{n(a.tokens!.output)}</td><td className="num">{cents(a.cost_usd ?? 0)}</td></tr>
                ))}
                {ask.calls > 0 && <tr><th scope="row">Questions and What Ifs</th><td className="num">{n(ask.input)}</td><td className="num">{n(ask.cached)}</td><td className="num">{n(ask.output)}</td><td className="num">{cents(ask.usd)}</td></tr>}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  );
}
