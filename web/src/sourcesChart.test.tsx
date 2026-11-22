import { afterEach, describe, expect, it } from "vitest";
import { act } from "react";
import { SourcesChart } from "./components/AnalysisSection";
import { render, type Mounted } from "./test-utils";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const ages = Array.from({ length: 11 }, (_, i) => 60 + i);
const src = { ages, series: [{ key: "savings", label: "From savings", values: ages.map(() => 40000) }], spending: ages.map(() => 40000), surplus: ages.map(() => 0), line: "Test." } as never;
const hit = () => m!.el.querySelector("[data-testid=sources-hit]") as SVGRectElement;
const live = () => m!.el.querySelector("[data-testid=sources-live]")!.textContent;
// jsdom has no layout, so clientX is a plain x in the 560 px drawing: the plot runs from x=48 to x=548
const fire = (type: string, clientX: number, pointerType = "mouse") => act(async () => {
  const e = new MouseEvent(type, { bubbles: true, clientX, clientY: 10 });
  Object.defineProperty(e, "pointerType", { value: pointerType });
  hit().dispatchEvent(e);
});

describe("Sources chart readout", () => {
  it("hover is steady and leaving hides it", async () => {
    m = await render(<SourcesChart src={src} />);
    expect(live()).toBe("");
    for (const [x, age] of [[48, 60], [298, 65], [100, 61], [298, 65], [548, 70]] as const) {
      await fire("pointermove", x);
      expect(live()).toContain(`Age ${age}.`);
    }
    await fire("pointerout", 0);
    expect(live()).toBe("");
  });
  it("a tap and a drag with a finger show the age, and lifting keeps it; keys still work", async () => {
    m = await render(<SourcesChart src={src} />);
    await fire("pointerdown", 298, "touch");
    expect(live()).toContain("Age 65.");
    await fire("pointermove", 548, "touch");
    expect(live()).toContain("Age 70.");
    await fire("pointerout", 0, "touch");
    expect(live()).toContain("Age 70.");
    const svg = m.el.querySelector("svg") as SVGElement;
    await act(async () => { svg.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true })); });
    expect(live()).toContain("Age 60.");
  });
});
