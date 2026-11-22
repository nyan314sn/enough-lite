import { useEffect, useRef } from "react";
import { ROSTER } from "./TeamPanel";

// "How it works": four short steps, said plainly. It opens by itself once for a first-time visitor on page 1. "Got it" folds it
// into a one-line summary that stays on page 1 ("Show details" opens it again); the header button opens it on either page.

export const HOW_KEY = "enough-lite-how-seen";

export const seenHow = (): boolean => { try { return localStorage.getItem(HOW_KEY) === "1"; } catch { return false; } };
export const markHowSeen = () => { try { localStorage.setItem(HOW_KEY, "1"); } catch { /* storage blocked */ } };

/** The folded form: one line that says what the app does, and a way to open the steps. */
export function HowSummary({ onOpen }: { onOpen: () => void }) {
  return (
    <section className="how how-folded card" aria-label="How Enough works" data-testid="how-collapsed">
      <p className="how-line"><strong>How Enough works:</strong> describe your household, check the figures on the right, and a team of {ROSTER.length} AI advisers builds your baseline plan. Then try a What if.</p>
      <button type="button" className="btn btn-quiet btn-small how-more" aria-expanded="false" aria-controls="how" onClick={onOpen}>Show details ▾</button>
    </section>
  );
}

export default function HowItWorks({ onClose, focus = false }: { onClose: () => void; focus?: boolean }) {
  const box = useRef<HTMLElement>(null);
  useEffect(() => { if (focus) box.current?.focus({ preventScroll: true }); }, [focus]);
  return (
    <section id="how" ref={box} tabIndex={-1} className="how card" aria-labelledby="how-h" data-testid="how-it-works"
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
      <div className="how-head">
        <h2 id="how-h" className="h-screen">How Enough works</h2>
        <button type="button" className="btn btn-quiet btn-small" aria-expanded="true" aria-controls="how" onClick={onClose}>Got it ▴</button>
      </div>
      <ol className="how-steps">
        <li><strong>You tell us about your household</strong>, in your own words. Type as you would tell a friend.</li>
        <li><strong>The panel on the right fills in.</strong> Check it and change any figure. Figures marked estimate are guesses.</li>
        <li>
          <strong>A team of AI advisers checks one part each</strong>, using real tools and data. The lead adviser then writes your plan.
          <ul className="how-team">
            {ROSTER.map((r) => <li key={r.key}><strong>{r.name}</strong>: {r.role.charAt(0).toLowerCase()}{r.role.slice(1)}</li>)}
          </ul>
          The numbers come from calculations, not from the AI.
        </li>
        <li><strong>Try a "What if".</strong> Retire earlier, save more, spend less. Each one is compared with your baseline plan.</li>
      </ol>
      <p className="muted small">A plan costs under a cent. Your answers go to the AI only to build your plan; leave out names and account numbers.</p>
    </section>
  );
}
