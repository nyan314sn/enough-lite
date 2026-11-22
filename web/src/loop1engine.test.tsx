import { afterEach, describe, expect, it } from "vitest";
import PlanCard from "./components/PlanCard";
import { costsLine } from "./components/CostsChart";
import { examplePlan } from "./mock";
import { render, type Mounted } from "./test-utils";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const base = examplePlan({ age: 45, retire_age: 62 });

describe("Round 1 engine fixes on the plan card", () => {
  it("says the figures are in today's dollars and keeps the assumptions behind a closed expander", async () => {
    const plan = { ...base, assumptions: ["All figures are in today's dollars.", "Pay stays at today's level until you retire."] };
    m = await render(<PlanCard plan={plan} retireAge={62} />);
    expect(m.el.textContent).toContain("All figures are in today's dollars.");
    const d = m.el.querySelector("[data-testid=plan-assumptions]") as HTMLDetailsElement;
    expect(d.open).toBe(false);
    expect(d.querySelector("summary")?.textContent).toBe("Assumptions");
    expect(d.querySelectorAll("li").length).toBe(2);
  });

  it("shows starting points when the basics are not safe, and no 'retire at' for someone retired", async () => {
    const plan = { ...base, already_retired: true, starting_points: [{ title: "Claim Social Security at 70", result: "basics paid in 95 of 100, and $30,000 a year to count on", whatif_text: "What if I claim Social Security at 70", paid_of_100: 95, count_on_per_year: 30000 }] };
    m = await render(<PlanCard plan={plan} retireAge={71} />);
    expect(m.el.textContent).toContain("Starting points");
    expect(m.el.querySelector("#plan-h")?.textContent).not.toContain("retire at");
  });

  it("uses the panel's spending-now figure for Costs now", () => {
    const c = { ages: [71, 72], total: [57600, 57600], basics: [30000, 30000], events: [], now_per_year: 72000 };
    expect(costsLine(c, 71)).toBe("Costs now: $72,000 a year.");
  });
});
