import { describe, expect, it } from "vitest";
import { withPlanStart } from "./components/LivePanel";
import { showValue } from "./format";

describe("re-check intake items", () => {
  const ss = { panel_per_year: 82000, plan_per_year: 95100, panel_age: 67, claim_age: 70, already: false, same: false };
  it("names the plan's start age beside the answers' figure", () => {
    expect(withPlanStart("$82,000 a year at 67", ss)).toBe("$82,000 a year at 67; your plan starts it at 70 ($95,100)");
  });
  it("adds nothing when the plan starts it at the same age or the person is already claiming", () => {
    expect(withPlanStart("$82,000 a year at 67", { ...ss, same: true })).toBe("$82,000 a year at 67");
    expect(withPlanStart("$82,000 a year", { ...ss, already: true })).toBe("$82,000 a year");
    expect(withPlanStart("$82,000 a year at 67", null)).toBe("$82,000 a year at 67");
  });
  it("says age for one child and ages for more", () => {
    expect(showValue("children", [{ age: 12 }])).toBe("1 child, age 12");
    expect(showValue("children", [{ age: 12 }, { age: 9 }])).toBe("2 children, ages 9 and 12");
  });
});
