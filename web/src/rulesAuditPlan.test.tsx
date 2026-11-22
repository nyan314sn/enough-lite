import { describe, expect, it } from "vitest";
import { ideas } from "./components/AskBox";
import type { Plan, Profile } from "./types";

// Live rules audit (2026-11-22): "Save 5% more of pay" was offered to retirees and people with no pay, and did nothing.
describe("saving chips", () => {
  const plan = (retired: boolean) => ({ already_retired: retired, levers: [] }) as unknown as Plan;
  it("are offered to someone at work with pay", () => {
    const p = { age: 45, retire_age: 62, pay_per_year: 310000, save_rate: 0.1 } as unknown as Profile;
    expect(ideas(p, plan(false)).map((x) => x.label)).toContain("Save 5% more of pay");
  });
  it("are not offered to a retiree or to someone with no pay", () => {
    const retiree = { age: 68, retire_age: 68, pay_per_year: 0 } as unknown as Profile;
    const noPay = { age: 50, retire_age: 60, pay_per_year: 0, partner_pay_per_year: 0 } as unknown as Profile;
    for (const [p, r] of [[retiree, true], [noPay, false]] as const) {
      const labels = ideas(p, plan(r)).map((x) => x.label);
      expect(labels.some((l) => /save/i.test(l))).toBe(false);
      expect(labels).toContain("Spend $500 less a month");
    }
  });
});
