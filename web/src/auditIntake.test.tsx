import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import FieldEditor from "./components/FieldEditor";
import LivePanel from "./components/LivePanel";
import { click, render, type Mounted } from "./test-utils";
import type { Field, Profile } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

async function type(input: HTMLInputElement | null, v: string) {
  await act(async () => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    set.call(input, v);
    input!.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("Skipped answers show their figure in the panel (R1)", () => {
  const profile: Profile = { age: 50, retire_age: 65 };
  const fields: Field[] = [
    { key: "age", label: "Your age", value: 50, display: "50", source: "you said", section: "Household" },
    { key: "savings", label: "Savings", value: { pretax: 69000 }, display: "$69,000 pre-tax", source: "assumed", section: "Saving" },
  ];
  const sections = [{ section: "Household", status: "added" as const }, { section: "Saving", status: "default" as const, note: "Estimate: $115,000 saved" }];

  it("a section not filled in carries its estimated figure, not only 'Not added, using typical'", async () => {
    m = await render(<LivePanel profile={profile} fields={fields} missing={[]} sections={sections} onEdit={() => {}} onBuild={() => {}} canBuild={false} />);
    const saving = m.el.querySelector('[data-section="Saving"]') as HTMLElement;
    expect(saving.textContent).toContain("Estimate: $115,000 saved");
    expect(saving.textContent).not.toContain("Not added, using typical");
  });
});

describe("The editor checks the figure it is given", () => {
  const retire: Field = { key: "retire_age", label: "Retirement age", value: 62, source: "you said", editable: { kind: "number", min: 30, max: 80 } };
  const age: Field = { key: "age", label: "Your age", value: 45, source: "you said", editable: { kind: "number", min: 18, max: 110 } };
  const profile: Profile = { age: 45, retire_age: 62, pay_per_year: 400000 };

  async function submit(field: Field, value: string) {
    const onSave = vi.fn();
    m = await render(<FieldEditor field={field} profile={profile} idp="t" onSave={onSave} onCancel={() => {}} />);
    await type(m.el.querySelector("input"), value);
    await click(m.el.querySelector("button[type=submit], .editor button:not([type=button])") as HTMLElement);
    return { onSave, error: m.el.textContent ?? "" };
  }

  it("rejects a retirement age of 40 for a 45-year-old who is still working", async () => {
    const { onSave, error } = await submit(retire, "40");
    expect(onSave).not.toHaveBeenCalled();
    expect(error).toContain("below the age now (45)");
  });

  it("accepts a retirement age at or above the age now", async () => {
    const { onSave } = await submit(retire, "62");
    expect(onSave).toHaveBeenCalledWith(retire, 62);
  });

  it("the age field's error hint is about an age, not '120000'", async () => {
    const { onSave, error } = await submit(age, "abc");
    expect(onSave).not.toHaveBeenCalled();
    expect(error).toContain("whole number of years, such as 45");
    expect(error).not.toContain("120000");
  });
});
