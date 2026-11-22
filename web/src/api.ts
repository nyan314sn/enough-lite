import { parseSSE } from "./sse";
import type { Api, AskResponse, CostSummary, Health, IntakeResponse, ModelCompare, PlanEvent, Profile, Sample } from "./types";
import { mockApi } from "./mock";
import { adminSession } from "./admin";

// Relative paths only: the backend serves this app at /, so /api is on the same origin wherever it runs.

async function errorText(res: Response): Promise<string> {
  try {
    const j = await res.json();
    const d = j?.detail ?? j?.message ?? j?.error;
    if (typeof d === "string") return d;
  } catch { /* not JSON */ }
  if (res.status === 429) return "Too many requests, or the cost limit was reached. Please wait and try again.";
  return `The server had a problem (${res.status}). Please try again.`;
}

/** In an admin session (the tab was opened at /admin) every request asks for test mode. The server honours it only when it runs with ENOUGH_TEST_MODE=1,
 *  so Run all is not stopped by the per-minute plan limit on the owner's machine; the dollar caps still apply. */
const testHeader = (): Record<string, string> =>
  typeof window !== "undefined" && adminSession() ? { "X-Enough-Test": "1" } : {};

async function post<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", ...testHeader() }, body: JSON.stringify(body) });
  } catch {
    throw new Error("We could not reach the server. Check your connection and try again.");
  }
  if (!res.ok) throw new Error(await errorText(res));
  return (await res.json()) as T;
}

/** Read an SSE response body and hand each event on. Always ends with a done or error event. */
export async function readStream(body: ReadableStream<Uint8Array>, onEvent: (e: PlanEvent) => void): Promise<void> {
  const reader = body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let ended = false;
  const emit = (events: PlanEvent[]) => { for (const e of events) { if (e.type === "done" || e.type === "error") ended = true; onEvent(e); } };
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const { events, rest } = parseSSE(buf);
      buf = rest;
      emit(events);
    }
    emit(parseSSE(buf + "\n\n").events);
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    onEvent({ type: "error", message: "The connection dropped before the plan was ready. Please try again." });
    return;
  }
  if (!ended) onEvent({ type: "done" });
}

export const realApi: Api = {
  async health() {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("health");
    return (await res.json()) as Health;
  },
  async samples() {
    const res = await fetch("/api/samples");
    if (!res.ok) throw new Error("The sample households could not be loaded.");
    return (await res.json()) as Sample[];
  },
  async modelCompare() {
    const res = await fetch("/api/admin/model-compare");
    if (!res.ok) throw new Error("No model comparison has been saved yet.");
    return (await res.json()) as ModelCompare;
  },
  intake: (text: string, profileSoFar: Profile | null, reset?: string[]) =>
    post<IntakeResponse>("/api/intake", { text, profile_so_far: profileSoFar ?? {}, ...(reset && reset.length ? { reset } : {}) }),
  async reset() { await post("/api/reset", {}); },
  async plan(profile, onEvent, signal) {
    let res: Response;
    try {
      res = await fetch("/api/plan", { method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...testHeader() }, body: JSON.stringify({ profile }), signal });
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      onEvent({ type: "error", message: "We could not reach the server. Check your connection and try again." });
      return;
    }
    if (!res.ok || !res.body) { onEvent({ type: "error", message: await errorText(res) }); return; }
    await readStream(res.body, onEvent);
  },
  ask: (question, profile, plan, pendingChange) => post<AskResponse>("/api/ask", { question, profile, plan, ...(pendingChange ? { pending_change: pendingChange } : {}) }),
  async costs() {
    const res = await fetch("/api/costs", { headers: testHeader() });
    if (!res.ok) throw new Error("costs");
    return (await res.json()) as CostSummary;
  },
};

export const MOCK = import.meta.env.VITE_MOCK === "1";
export const api: Api = MOCK ? mockApi : realApi;
