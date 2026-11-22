import { describe, expect, it } from "vitest";
import { suggestions, SUGGEST } from "./components/AskBox";
import { costsLine } from "./components/CostsChart";
import { WAIT_TEXT } from "./components/TeamScreen";

describe("plan fixes", () => {
  it("never offers a chip that repeats the plan's retirement age", () => {
    expect(suggestions(62)).toEqual(SUGGEST);
    expect(suggestions(60)).toContain("Retire at 62");
    expect(suggestions(60)).not.toContain("Retire at 60");
    expect(suggestions(60)).toContain("Markets fall 30%");
  });

  it("explains a first retired year that costs more than the goal", () => {
    const c = { ages: [44, 60, 61], total: [150000, 211000, 200000], basics: [80000, 86000, 86000], events: [], retired_per_year: 168000 };
    expect(costsLine(c, 60)).toMatch(/first year retired: about \$211,000, your goal of \$168,000 plus/);
    expect(costsLine({ ...c, total: [150000, 168000, 168000] }, 60)).toBe("Costs now: $150,000 a year. In retirement: about $168,000.");
  });

  it("gives an estimate while the team works", () => {
    expect(WAIT_TEXT).toMatch(/10 to 30 seconds/);
  });
});
