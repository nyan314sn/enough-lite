import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import LivePanel from "./components/LivePanel";
import { chatLine } from "./components/FieldEditor";
import { click, render, type Mounted } from "./test-utils";
import type { Field, Profile } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const kids = [
  { age: 16, college: true, college_type: "public" as const, college_share: 1, college_source: "you said" as const },
  { age: 12, college: true, college_type: "private" as const, college_share: 0.5, college_source: "you said" as const },
  { age: 7, college: false, college_type: "none" as const, college_share: 1, college_source: "estimate" as const },
];
const profile: Profile = { age: 45, children: kids };
const ed = (i: number) => ({ kind: "college" as const, ask: "college", child: i, options: ["public", "private", "none"] });
const fields: Field[] = [
  { key: "age", label: "Your age", value: 45, source: "you said", section: "Household" },
  { key: "college_0", label: "College: child 1, age 16", value: kids[0], display: "public in-state, you pay 100%", source: "you said", section: "Household", editable: ed(0) },
  { key: "college_1", label: "College: child 2, age 12", value: kids[1], display: "private, you pay 50%", source: "you said", section: "Household", editable: ed(1) },
  { key: "college_2", label: "College: child 3, age 7", value: kids[2], display: "no college", source: "estimate", note: "Typical choice: public in-state, you pay 100%. Change it if that is not your plan.", section: "Household", editable: ed(2) },
];

function panel(editing: string | null, onSave = vi.fn(), onEdit = vi.fn()) {
  return render(<LivePanel profile={profile} fields={fields} missing={[]} onEdit={onEdit} editing={editing} onSave={onSave} onCancel={() => {}} onBuild={() => {}} canBuild={false} />);
}

describe("college rows, one per child", () => {
  it("shows a row for each child with its own type, share and note", async () => {
    m = await panel(null);
    const rows = Array.from(m.el.querySelectorAll("li.field")).filter((r) => (r.getAttribute("data-key") ?? "").startsWith("college_"));
    expect(rows.map((r) => r.getAttribute("data-key"))).toEqual(["college_0", "college_1", "college_2"]);
    expect(rows[0].textContent).toContain("College: child 1, age 16");
    expect(rows[0].textContent).toContain("public in-state, you pay 100%");
    expect(rows[1].textContent).toContain("private, you pay 50%");
    expect(rows[1].textContent).not.toMatch(/assumed|typical choice/i);
    expect(rows[2].textContent).toContain("no college");
    expect(rows[2].textContent).toContain("estimate");
  });

  it("the editor of one child offers type and share and saves only that child's choice", async () => {
    const onSave = vi.fn();
    m = await panel("college_1", onSave);
    const form = m.el.querySelector("form[aria-label='Change College: child 2, age 12']")!;
    expect(form).toBeTruthy();
    expect(Array.from(form.querySelectorAll("button.chip")).map((b) => b.textContent)).toEqual(["Public, in-state", "Private", "None"]);
    const share = form.querySelector("input") as HTMLInputElement;
    expect(share.value).toBe("50");
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => { setter.call(share, "25"); share.dispatchEvent(new Event("input", { bubbles: true })); });
    await click(Array.from(form.querySelectorAll("button.chip")).find((b) => b.textContent === "Public, in-state"));
    await click(Array.from(form.querySelectorAll("button")).find((b) => b.textContent === "Save"));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0].key).toBe("college_1");
    expect(onSave.mock.calls[0][1]).toEqual({ college_type: "public", college_share: 0.25 });
  });

  it("refuses a share outside 0 to 100", async () => {
    const onSave = vi.fn();
    m = await panel("college_0", onSave);
    const form = m.el.querySelector("form")!;
    const share = form.querySelector("input") as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => { setter.call(share, "150"); share.dispatchEvent(new Event("input", { bubbles: true })); });
    await click(Array.from(form.querySelectorAll("button")).find((b) => b.textContent === "Save"));
    expect(onSave).not.toHaveBeenCalled();
    expect(form.querySelector("[role=alert]")?.textContent).toMatch(/0 to 100/);
  });

  it("tells the chat which child changed, in words the server reads", () => {
    expect(chatLine(fields[2], { college_type: "private", college_share: 0.5 })).toBe("College for child 2 (age 12): private college, you pay 50%.");
    expect(chatLine(fields[3], { college_type: "none", college_share: 1 })).toBe("College for child 3 (age 7): no college.");
  });
});
