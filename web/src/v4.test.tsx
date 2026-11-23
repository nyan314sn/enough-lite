import { afterEach, describe, expect, it, vi } from "vitest";
import AskBox, { ideas } from "./components/AskBox";
import LivePanel from "./components/LivePanel";
import PlanCard from "./components/PlanCard";
import { showValue } from "./format";
import { examplePlan, mockApi } from "./mock";
import { click, render, type Mounted } from "./test-utils";
import type { Api, AskResponse, Field, Profile } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const profile: Profile = { age: 45, retire_age: 62, pay_per_year: 380000 };
const base = examplePlan(profile);
const fields: Field[] = [
  { key: "age", label: "Your age", value: 45, display: "45", source: "you said", section: "Household" },
  { key: "risk", label: "Risk", value: "balanced", display: "Balanced", source: "assumed", section: "Saving" },
  { key: "debts", label: "Debts", value: [], display: "None given", source: "default", section: "Home & debts" },
  { key: "pensions", label: "Pension", value: [], display: "None given", source: "default", section: "Pensions & income" },
];
const sections = [{ section: "Household", status: "added" as const }, { section: "Saving", status: "added" as const }, { section: "Home & debts", status: "default" as const }, { section: "Pensions & income", status: "default" as const }];

describe("The empty state", () => {
  const panel = (onChip = vi.fn()) => render(<LivePanel profile={profile} fields={fields} missing={[]} sections={sections} onEdit={() => {}} onChip={onChip} onBuild={() => {}} canBuild={false} />);

  it("folds default sections to one line and sends the section's chip", async () => {
    const onChip = vi.fn();
    m = await panel(onChip);
    const debts = m.el.querySelector('[data-section="Home & debts"]') as HTMLElement;
    const toggle = (s: Element) => s.querySelector("button.group-toggle") as HTMLButtonElement;
    expect(toggle(debts).getAttribute("aria-expanded")).toBe("false");
    expect(debts.textContent).toContain("Not added, using typical");
    expect(toggle(m.el.querySelector('[data-section="Household"]')!).getAttribute("aria-expanded")).toBe("true");
    await click(debts.querySelector("button.chat-alt"));
    expect(onChip).toHaveBeenCalledWith("Add debts");
    await click(m.el.querySelector('[data-section="Pensions & income"] button.chat-alt'));
    expect(onChip).toHaveBeenCalledWith("Add a pension");
  });

  it("tags default fields 'typical', apart from 'Assumed: check this'", async () => {
    m = await panel();
    const debt = m.el.querySelector('li[data-key="debts"]')!;
    expect(debt.querySelector(".tag-default")?.textContent).toBe("typical");
    expect(debt.textContent).not.toContain("Assumed: check this");
    expect(m.el.querySelector('li[data-key="risk"]')?.textContent).toContain("Assumed: check this");
  });
});

describe("The plan's headline", () => {
  it("is the main line, and the wants line is not repeated when it is the same", async () => {
    const plan = { ...base, headline: "You can count on $50,400 a year, about your basics.", wants: { per_year: 0, line: "You can count on $50,400 a year, about your basics." } };
    m = await render(<PlanCard plan={plan} retireAge={62} />);
    expect(m.el.querySelector("[data-testid=plan-headline]")?.textContent).toBe(plan.headline);
    expect(m.el.textContent!.split(plan.headline!).length - 1).toBe(1);
  });
});

describe("Levers", () => {
  const levers = [{ key: "debt", title: "Pay off the credit card", why: "It costs 24% a year.", whatif_text: "What if I pay off my credit card" }, { key: "match", title: "Take the full match", why: "Free money.", whatif_text: "What if I save to the full 401(k) match" }];
  it("become the Worth trying chips and send whatif_text as is", async () => {
    const ask = vi.fn(async () => ({ kind: "whatif", text: "ok", citations: [], plan: base }) as AskResponse);
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={{ ...base, levers }} onCost={() => {}} onWhatIf={() => 1} />);
    const chips = Array.from(m.el.querySelectorAll(".ideas button"));
    expect(chips.map((b) => b.textContent)).toEqual(["Pay off the credit card", "Take the full match"]);
    expect(chips[0].getAttribute("title")).toBe("It costs 24% a year.");
    await click(chips[0]);
    expect(ask).toHaveBeenCalledWith("What if I pay off my credit card", profile, expect.anything(), null);
  });
  it("fall back to the plain chips when empty", () => {
    expect(ideas({ ...profile, save_rate: 0.1 }, { ...base, levers: [] }).map((i) => i.label)).toEqual(["Retire 2 years later", "Save 5% more of pay"]);
  });
});

describe("Plain text for edited values", () => {
  it("writes objects in words", () => {
    expect(showValue("pensions", [{ who: "you", per_year: 24000, start_age: 65, inflation_adjusted: true }])).toBe("You: $24,000 a year from 65, rises with prices");
    expect(showValue("home", { owns: true, value: null, mortgage_balance: 100000, mortgage_payment: 1500 })).toBe("Own, $100,000 left on the mortgage, $1,500 a month, value not given");
    expect(showValue("home", { owns: false, rent: 2000 })).toBe("Rent, $2,000 a month");
    expect(showValue("debts", [{ kind: "credit_card", balance: 8000, rate: 0.24, monthly_payment: 300 }])).toBe("Credit card: $8,000, 24%, $300 a month");
    expect(showValue("children", [{ age: 13 }, { age: 6 }, { age: 10 }])).toBe("3 children, ages 6, 10 and 13");
    expect(showValue("savings", { pretax: 100, roth: 0, taxable: 0, cash: 50 })).toBe("$150");
    expect(showValue("other", { a_b: 1, c: null })).not.toContain("{");
  });
});
