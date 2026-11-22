import { afterEach, describe, expect, it } from "vitest";
import { act } from "react";
import SavingsChart from "./components/SavingsChart";
import { render, type Mounted } from "./test-utils";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const ages = Array.from({ length: 11 }, (_, i) => 60 + i);
const chart = { ages, median: ages.map((a) => a * 1000), low: ages.map((a) => a * 800), high: ages.map((a) => a * 1300) };
const hit = () => m!.el.querySelector("[data-testid=savings-hit]") as SVGRectElement;
const tip = () => m!.el.querySelector("[data-testid=savings-tip]");
// jsdom has no layout: the rect is 0 wide, so clientX is a plain x in the 640 px drawing. Plot runs from x=52 to x=626.
const fire = (type: string, clientX: number, pointerType = "mouse") => act(async () => {
  const e = new MouseEvent(type, { bubbles: true, clientX, clientY: 10 });
  Object.defineProperty(e, "pointerType", { value: pointerType });
  hit().dispatchEvent(e);
});

describe("Savings chart readout", () => {
  it("a steady hover: every move shows the age under the pointer, the tip never takes the pointer", async () => {
    m = await render(<SavingsChart chart={chart} retireAge={65} />);
    expect(tip()).toBeNull();
    for (const [x, age] of [[52, 60], [339, 65], [100, 61], [339, 65], [626, 70]] as const) {
      await fire("pointermove", x);
      expect(tip()?.textContent).toContain(`Age ${age}`);
    }
    await fire("pointerout", 0);
    expect(tip()).toBeNull();
  });
  it("a tap or drag with a finger shows the age, and lifting the finger keeps it", async () => {
    m = await render(<SavingsChart chart={chart} retireAge={65} />);
    await fire("pointerdown", 339, "touch");
    expect(tip()?.textContent).toContain("Age 65");
    await fire("pointermove", 626, "touch");
    expect(tip()?.textContent).toContain("Age 70");
    await fire("pointerout", 0, "touch");
    expect(tip()?.textContent).toContain("Age 70");
    expect(m.el.querySelector("[data-testid=savings-live]")?.textContent).toContain("Age 70");
  });
});
