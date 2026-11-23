import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import FieldEditor, { applyEdit, chatLine, editorFor, isReadOnly } from "./components/FieldEditor";
import LivePanel from "./components/LivePanel";
import IntakeScreen from "./components/IntakeScreen";
import keys from "./panelKeys.json";
import { mockApi, mockSpeed } from "./mock";
import { byText, click, flush, render, type Mounted } from "./test-utils";
import type { Api, Field, IntakeResponse, Profile } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const f = (key: string, value: unknown, label = key, extra: Partial<Field> = {}): Field => ({ key, label, value, source: "you said", display: "", section: "Household", ...extra });

async function type(input: Element | null, v: string, tag: "input" | "select" = "input") {
  await act(async () => {
    const proto = tag === "select" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(input, v);
    input!.dispatchEvent(new Event(tag === "select" ? "change" : "input", { bubbles: true }));
  });
}
const q = (sel: string) => m!.el.querySelector(sel);
const qa = (sel: string) => Array.from(m!.el.querySelectorAll(sel));

const profile: Profile = { age: 45, partner_age: 43, has_partner: true, state: "CT", retire_age: 65, pay_per_year: 120000, children: [{ age: 12, college: true, college_type: "public", college_share: 1 }], pets: [{ kind: "dog", count: 1 }] };

describe("every field the panel can show has an inline editor", () => {
  it("covers every key the server sends (panelKeys.json), except the worked-out mortgage end", () => {
    const missing: string[] = [];
    for (const k of keys) {
      const key = k === "college_*" ? "college_0" : k;
      const fld = f(key, null, key, k === "college_*" ? { editable: { kind: "college", child: 0, options: ["public", "private", "none"] } } : { editable: { kind: "group", ask: "x" } });
      if (!editorFor(fld) && !isReadOnly(fld)) missing.push(k);
    }
    expect(missing).toEqual([]);
    expect(isReadOnly(f("mortgage_end", null))).toBe(true);
  });

  it("gives each kind of figure the right kind of editor", () => {
    const kind = (k: string) => editorFor(f(k, null))?.kind;
    expect(kind("state")).toBe("state");
    expect(kind("home")).toBe("home");
    expect(kind("debts")).toBe("rows");
    expect(kind("pensions")).toBe("rows");
    expect(kind("pets")).toBe("rows");
    expect(kind("children")).toBe("rows");
    expect(kind("big_costs")).toBe("rows");
    expect(kind("sex")).toBe("choice");
    expect(kind("health")).toBe("choice");
    expect(kind("risk")).toBe("choice");
    expect(kind("disability")).toBe("yesno");
    expect(kind("ltc")).toBe("yesno");
    expect(kind("job")).toBe("text");
    expect(kind("pay_per_year")).toBe("money");
    expect(kind("other_saving")).toBe("money");
    expect(kind("legacy")).toBe("money");
    expect(kind("age")).toBe("number");
    expect(kind("partner_retire_age")).toBe("number");
    expect(kind("savings")).toBe("split");
    expect(kind("life_insurance")).toBe("form");
    expect(kind("save_rate")).toBe("form");
  });

  it("no pen on the panel falls back to the chat, for any field the server can send", async () => {
    const fields = keys.filter((k) => k !== "mortgage_end" && k !== "college_*").map((k) => f(k, null, k, { editable: { kind: "group", ask: "x" } }));
    const onEdit = vi.fn();
    m = await render(<LivePanel profile={profile} fields={fields} missing={[]} onEdit={onEdit} onBuild={() => {}} canBuild={false} />);
    const pens = qa("li.field button.pen");
    expect(pens).toHaveLength(fields.length);
    expect(fields.every((x) => !!editorFor(x))).toBe(true);
    expect(q("li[data-key='mortgage_end'] button.pen")).toBeNull();
  });
});

function Harness({ field, p = profile, onSave }: { field: Field; p?: Profile; onSave: (f: Field, v: unknown) => void }) {
  return <FieldEditor field={field} profile={p} idp="t" onSave={onSave} onCancel={() => {}} />;
}
const save = () => click(q("button[type=submit]"));

describe("the editors", () => {
  it("state: a searchable list of the 50 states and DC by full name; saves the code", async () => {
    const onSave = vi.fn();
    m = await render(<Harness field={f("state", "CT", "State")} onSave={onSave} />);
    const opts = qa("datalist option").map((o) => (o as HTMLOptionElement).value);
    expect(opts).toHaveLength(51);
    expect(opts).toContain("Texas");
    expect(opts).toContain("Washington, DC");
    expect((q("input[list]") as HTMLInputElement).value).toBe("Connecticut");
    await type(q("input[list]"), "Atlantis"); await save();
    expect(onSave).not.toHaveBeenCalled();
    expect(q("[role=alert]")?.textContent).toContain("Pick a state");
    await type(q("input[list]"), "texas"); await save();
    expect(onSave).toHaveBeenCalledWith(expect.anything(), "TX");
  });

  it("yes/no and choice lists save at once", async () => {
    const a = vi.fn();
    m = await render(<Harness field={f("disability", null, "Disability insurance")} onSave={a} />);
    await click(byText(m.el, "button", "Yes")!);
    expect(a).toHaveBeenCalledWith(expect.anything(), true);
    m.unmount();
    const b = vi.fn();
    m = await render(<Harness field={f("health", "good", "Your health")} onSave={b} />);
    expect(qa(".choices button").map((x) => x.textContent)).toEqual(["Excellent", "Good", "Fair", "Poor"]);
    await click(byText(m.el, "button", "Fair")!);
    expect(b).toHaveBeenCalledWith(expect.anything(), "fair");
  });

  it("ages are bounded and the retirement age says it never goes past 70", async () => {
    const onSave = vi.fn();
    m = await render(<Harness field={f("retire_age", 65, "Retirement age", { editable: { kind: "number", min: 30, max: 80 } })} onSave={onSave} />);
    expect(m.el.textContent).toContain("never suggests retiring after 70");
    await type(q("input"), "95"); await save();
    expect(onSave).not.toHaveBeenCalled();
    expect(q("[role=alert]")?.textContent).toContain("30 to 80");
    m.unmount();
    m = await render(<Harness field={f("age", 45, "Your age")} onSave={onSave} />);
    await type(q("input"), "12"); await save();
    expect(onSave).not.toHaveBeenCalled();
    expect(q("[role=alert]")?.textContent).toContain("18 to 110");
  });

  it("debts: add and remove rows, a blank rate stays blank", async () => {
    const onSave = vi.fn();
    m = await render(<Harness field={f("debts", [{ kind: "car", balance: 9000, rate: 0.06, monthly_payment: 300 }], "Other debts")} onSave={onSave} />);
    expect(qa("fieldset.editor-row")).toHaveLength(1);
    await click(byText(m.el, "button", "Add a debt")!);
    expect(qa("fieldset.editor-row")).toHaveLength(2);
    await type(q("#t-ed-debts-1-balance"), "20k");
    await type(q("#t-ed-debts-1-kind"), "student", "select");
    await save();
    const v = onSave.mock.calls[0][1] as { kind: string; balance: number; rate: number | null; assumed: string[] }[];
    expect(v).toHaveLength(2);
    expect(v[0]).toMatchObject({ kind: "car", balance: 9000, rate: 0.06, monthly_payment: 300 });
    expect(v[1]).toMatchObject({ kind: "student", balance: 20000, rate: null, assumed: ["rate", "monthly_payment"] });
    onSave.mockClear();
    await click(q("button[aria-label='Remove debt 1']"));
    expect(qa("fieldset.editor-row")).toHaveLength(1);
    await save();
    expect((onSave.mock.calls[0][1] as unknown[]).length).toBe(1);
    onSave.mockClear();
    await click(q("button[aria-label='Remove debt 1']"));
    await save();
    expect(onSave).toHaveBeenCalledWith(expect.anything(), []);
  });

  it("debts: an interest rate over 60% is refused with the row named", async () => {
    const onSave = vi.fn();
    m = await render(<Harness field={f("debts", [], "Other debts")} onSave={onSave} />);
    await click(byText(m.el, "button", "Add a debt")!);
    await type(q("#t-ed-debts-0-balance"), "5000");
    await type(q("#t-ed-debts-0-rate"), "90");
    await save();
    expect(onSave).not.toHaveBeenCalled();
    expect(q("[role=alert]")?.textContent).toContain("Debt 1");
  });

  it("pets: kind and count, add and remove; children: ages, keeping the college choice of a child who stays", async () => {
    const onSave = vi.fn();
    m = await render(<Harness field={f("pets", [{ kind: "dog", count: 1 }], "Pets")} onSave={onSave} />);
    await click(byText(m.el, "button", "Add a pet")!);
    await type(q("#t-ed-pets-1-kind"), "cat", "select");
    await type(q("#t-ed-pets-1-count"), "2");
    await save();
    expect(onSave).toHaveBeenCalledWith(expect.anything(), [{ kind: "dog", count: 1 }, { kind: "cat", count: 2 }]);
    m.unmount();
    const kids = vi.fn();
    m = await render(<Harness field={f("children", profile.children, "Children")} onSave={kids} />);
    await type(q("#t-ed-children-0-age"), "13");
    await click(byText(m.el, "button", "Add a child")!);
    await type(q("#t-ed-children-1-age"), "4");
    await save();
    const v = kids.mock.calls[0][1] as Record<string, unknown>[];
    expect(v[0]).toMatchObject({ age: 13, college_type: "public" });
    expect(v[1]).toMatchObject({ age: 4, college: true });
  });

  it("pensions: your partner's pension is offered only with a partner", async () => {
    m = await render(<Harness field={f("pensions", [], "Pensions")} onSave={vi.fn()} />);
    await click(byText(m.el, "button", "Add a pension")!);
    expect(q("#t-ed-pensions-0-who")).not.toBeNull();
    m.unmount();
    m = await render(<Harness field={f("pensions", [], "Pensions")} p={{ age: 45 }} onSave={vi.fn()} />);
    await click(byText(m.el, "button", "Add a pension")!);
    expect(q("#t-ed-pensions-0-who")).toBeNull();
  });

  it("home: own with a mortgage saves the amounts", async () => {
    const onSave = vi.fn();
    m = await render(<Harness field={f("home", { owns: true, value: 500000 }, "Home")} onSave={onSave} />);
    await click(byText(m.el, "button", "Own with a mortgage")!);
    await type(q("#t-ed-home-mortgage_balance"), "300k");
    await type(q("#t-ed-home-mortgage_payment"), "2200");
    await save();
    expect(onSave).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ owns: true, value: 500000, mortgage_balance: 300000, mortgage_payment: 2200 }));
  });

  it("forms: life cover, match as a percent, yearly saving as a percent of pay", async () => {
    const onSave = vi.fn();
    m = await render(<Harness field={f("match", { rate: 0.5, cap: 0.06 }, "Employer match")} onSave={onSave} />);
    await type(q("#t-ed-match-0-rate"), "100"); await save();
    expect(onSave).toHaveBeenCalledWith(expect.anything(), { rate: 1, cap: 0.06 });
    m.unmount();
    m = await render(<Harness field={f("save_rate", 0.1, "Yearly saving")} onSave={onSave} />);
    await type(q("input"), "140"); await save();
    expect(q("[role=alert]")?.textContent).toContain("0 to 100");
  });

  it("savings split: each part's share shows and the total is 100%", async () => {
    m = await render(<Harness field={f("savings", { pretax: 300, roth: 100, taxable: 100, cash: 0 }, "Savings")} p={{ savings: { pretax: 300, roth: 100, taxable: 100, cash: 0 } }} onSave={vi.fn()} />);
    expect(q(".split-grid")?.textContent).toContain("60%");
    expect(q(".split-total")?.textContent).toContain("shares add to 100%");
  });

  it("Esc cancels, every box has a label, and an error is announced", async () => {
    const onCancel = vi.fn();
    m = await render(<FieldEditor field={f("debts", [], "Other debts")} profile={profile} idp="t" onSave={vi.fn()} onCancel={onCancel} />);
    await click(byText(m.el, "button", "Add a debt")!);
    for (const el of qa("input, select")) expect(m.el.querySelector(`label[for='${el.id}']`)).not.toBeNull();
    await save();
    expect(q("[role=alert]")).not.toBeNull();
    await act(async () => { q("form")!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
    expect(onCancel).toHaveBeenCalled();
  });
});

describe("how an edit lands in the profile and the chat", () => {
  it("nested figures go back to where the profile keeps them", () => {
    expect(applyEdit({ insurance: { life_kind: "term" } }, "disability", true)).toMatchObject({ insurance: { life_kind: "term", disability: true } });
    expect(applyEdit({}, "life_insurance", { kind: "whole", face: 1e5, premium: 800 })).toMatchObject({ insurance: { life_kind: "whole", life_face: 1e5, life_premium: 800 } });
    expect(applyEdit({}, "match", { rate: 0.5, cap: 0.06 })).toMatchObject({ saving: { match_rate: 0.5, match_cap: 0.06 } });
    expect(applyEdit({}, "legacy", 250000)).toMatchObject({ goals: { legacy: 250000 } });
    expect(applyEdit({}, "parents_help", { per_year: 6000, years: 10 })).toMatchObject({ goals: { parents_per_year: 6000, parents_years: 10 } });
    expect(applyEdit({}, "state", "TX")).toMatchObject({ state: "TX" });
  });

  it("the chat line names old and new and starts 'Updated your', which the server reads as the person's own word", () => {
    expect(chatLine(f("state", "TX", "State", { display: "Connecticut" }), "TX")).toBe("Updated your state: Texas. (was Connecticut)");
    expect(chatLine(f("retire_age", 62, "Retirement age", { display: "65" }), 62)).toBe("Updated your retirement age: 62. (was 65)");
  });
});

const first: IntakeResponse = {
  profile: { age: 45, state: "CT", retire_age: 65, pay_per_year: 120000, spending_per_year: 70000, risk: "balanced" },
  fields: [
    f("age", 45, "Your age", { display: "45" }),
    f("state", "CT", "State", { display: "Connecticut", source: "assumed" }),
    f("debts", [], "Other debts", { display: "None counted", source: "default", section: "Home & debts" }),
  ],
  missing: [], question: null, reply: "Got it.",
  sections_status: [{ section: "Household", status: "added" }, { section: "Home & debts", status: "default" }],
};

describe("on the page", () => {
  function setup() {
    mockSpeed.factor = 0;
    const intake = vi.fn(async (_t: string, p: unknown) => {
      const profile = (p as Profile) ?? first.profile;
      const fields = first.fields.map((x) => (JSON.stringify(profile[x.key]) !== JSON.stringify(first.profile[x.key]) ? { ...x, value: profile[x.key], source: "you said" } : x));
      return { ...first, profile, fields } as IntakeResponse;
    });
    return { api: { ...mockApi, intake } as Api, intake };
  }

  it("a state edit saves in place, shows 'you said' and tells the chat old to new", async () => {
    const { api, intake } = setup();
    m = await render(<IntakeScreen api={api} onBuild={() => {}} />);
    await click(byText(m.el, ".quick button", "Use an example"));
    await flush();
    await click(q(".side [aria-label='Change State']"));
    expect(q(".side .editor input[list]")).not.toBeNull();
    expect(q("#chat-input")).toBeNull();                       // one place to type
    await type(q(".side .editor input[list]"), "Texas");
    await click(q(".side .editor button[type=submit]"));
    await flush();
    const call = intake.mock.calls[intake.mock.calls.length - 1];
    expect(call[0]).toBe("Updated your state: Texas. (was Connecticut)");
    expect((call[1] as Profile).state).toBe("TX");
    expect(q(".side li[data-key='state'] .tag-said")).not.toBeNull();
  });

  it("an empty section's pen opens an add form inline, and the chat stays as the other way", async () => {
    const { api, intake } = setup();
    m = await render(<IntakeScreen api={api} onBuild={() => {}} />);
    await click(byText(m.el, ".quick button", "Use an example"));
    await flush();
    await click(q(".side [aria-label='Add debts']"));
    expect(q(".side form.editor[aria-label='Change Other debts']")).not.toBeNull();
    await click(byText(m.el, ".side .editor button", "Add a debt")!);
    await type(q(".side #lp-ed-debts-0-balance"), "12000");
    await click(q(".side .editor button[type=submit]"));
    await flush();
    const call = intake.mock.calls[intake.mock.calls.length - 1];
    expect(call[0]).toMatch(/^Updated your other debts: /);
    expect((call[1] as Profile).debts).toMatchObject([{ kind: "student", balance: 12000 }]);
    // the chat way is still there
    expect(q(".side [aria-label='Add debts in the chat']")).not.toBeNull();
  });
});
