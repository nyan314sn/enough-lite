import { useEffect, useRef } from "react";
import { MAX_WHATIFS } from "./WhatIf";

// The row above the plan: Baseline, one tab per What If (each with a ✕), "+ What if…" and Compare.
// A proper tablist: arrow keys, Home and End move between tabs; the selected tab is marked with aria-selected and the indigo fill.
// The ✕ buttons and the two action buttons sit beside the tabs, not inside them, so each tab is one clear target.

export const PANEL_ID = "scenario-panel";
export interface Tab { id: number | null; label: string; full?: string }

export default function ScenarioTabs({ items, active, comparing, onSelect, onRemove, onNew, onCompare, focusTab }: {
  items: { id: number; q: string; name: string }[]; active: number | null; comparing: boolean;
  onSelect: (id: number | null) => void; onRemove: (id: number) => void; onNew: () => void; onCompare: () => void;
  /** After a ✕: the tab to move keyboard focus to (null is the baseline). */
  focusTab?: { id: number | null; n: number } | null;
}) {
  const tabs: Tab[] = [{ id: null, label: "Baseline" }, ...items.map((w) => ({ id: w.id, label: w.name, full: w.q }))];
  const refs = useRef(new Map<number | null, HTMLButtonElement>());
  useEffect(() => { if (focusTab) refs.current.get(focusTab.id)?.focus(); }, [focusTab?.n]); // eslint-disable-line react-hooks/exhaustive-deps
  const sel = (t: Tab) => !comparing && t.id === active;
  const tabbable = tabs.some(sel) ? tabs.find(sel)! : tabs[0];
  const key = (e: React.KeyboardEvent, i: number) => {
    const to = e.key === "ArrowRight" ? (i + 1) % tabs.length : e.key === "ArrowLeft" ? (i - 1 + tabs.length) % tabs.length : e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : -1;
    if (to < 0) return;
    e.preventDefault();
    refs.current.get(tabs[to].id)?.focus();
    onSelect(tabs[to].id);
  };
  const full = items.length >= MAX_WHATIFS;
  return (
    <div className="scen-row">
      <div className="scen-tabs" role="tablist" aria-label="Baseline and What Ifs">
        {tabs.map((t, i) => (
          <div key={t.id ?? "base"} className={`scen-item${sel(t) ? " on" : ""}${t.id == null ? " is-base" : ""}`} role="presentation">
            <button type="button" role="tab" id={`tab-${t.id ?? "base"}`} className="scen-tab" aria-selected={sel(t)} aria-controls={PANEL_ID} tabIndex={t === tabbable ? 0 : -1}
              title={t.full} ref={(el) => { if (el) refs.current.set(t.id, el); else refs.current.delete(t.id); }} onClick={() => onSelect(t.id)} onKeyDown={(e) => key(e, i)}>
              {t.label}
            </button>
            {t.id != null && <button type="button" className="scen-x" aria-label={`Remove What If: ${t.full ?? t.label}`} onClick={() => onRemove(t.id!)}><span aria-hidden="true">✕</span></button>}
          </div>
        ))}
      </div>
      <div className="scen-acts">
        <button type="button" id="scen-add" className="scen-add" onClick={onNew} aria-describedby={full ? "scen-full" : undefined}>+ What if…</button>
        {items.length > 0 && <button type="button" className="btn btn-quiet scen-compare" aria-pressed={comparing} onClick={onCompare}>Compare</button>}
      </div>
      {full && <p id="scen-full" className="small muted scen-full">You have {MAX_WHATIFS} What Ifs. Remove one first to add another.</p>}
    </div>
  );
}
