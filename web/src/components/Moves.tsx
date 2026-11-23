import { usd } from "../format";
import { PLAN_WORDS, type Move } from "../readiness";
import Clamp from "./Clamp";

// "Your next moves": the plan's three actions as a short checklist. Each says what it is worth where the plan says so. Read only; a move is tried in the What If section.

/** The adviser's first action repeats the starting points in a long sentence; the move already lists them, so cut that tail. */
export function withoutRepeat(why: string, hasPoints: boolean): string {
  return hasPoints ? why.replace(/\s*Starting points:.*$/s, "").trim() : why;
}

export default function Moves({ moves, isNew }: {
  moves: Move[]; isNew: (title: string) => boolean;
}) {
  if (moves.length === 0) return null;
  return (
    <section className="moves" aria-labelledby="actions-h" data-testid="moves">
      <div className="moves-head">
        <h3 id="actions-h" className="h-sub">{PLAN_WORDS.movesTitle}</h3>
      </div>
      <p className="sec-line">{PLAN_WORDS.movesLine}</p>
      <ol className="actions moves-list">
        {moves.map((m, i) => {
          const fresh = isNew(m.original);
          return (
            <li key={m.id + i} className={`move${fresh ? " new" : ""}`} data-move={m.id}>
              <span className="action-n" aria-hidden="true">{i + 1}</span>
              <div className="move-body">
                <p className="move-title"><strong>{m.title}</strong>{fresh && <span className="new-tag">new</span>}</p>
                {m.why && <Clamp text={withoutRepeat(m.why, m.points.length > 0)} words={15} className="move-line" />}
                {m.worth && <p className="move-worth"><span className="worth-chip num" aria-hidden="true">{m.worth.text}</span><span className="sr-only">{m.worth.sr}</span></p>}
                {m.points.length > 0 && (
                  <div className="starting-points" aria-labelledby={`points-h-${i}`}>
                    <p id={`points-h-${i}`} className="h-mini">{PLAN_WORDS.pointsTitle}</p>
                    <ul>
                      {m.points.map((x) => (
                        <li key={x.title}>
                          <span className="pt-text"><strong>{x.title}</strong>{" "}
                            <span className={`worth-chip num${x.paid_of_100 < 90 ? " is-weak" : ""}`} aria-hidden="true">Needs paid {x.paid_of_100} of 100 · {usd(x.count_on_per_year)} a year</span>
                            <span className="sr-only">: {x.result}.</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
