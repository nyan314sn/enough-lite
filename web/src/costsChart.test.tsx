import { afterEach, describe, expect, it } from "vitest";
import { act } from "react";
import CostsChart, { costsReadout } from "./components/CostsChart";
import { render, type Mounted } from "./test-utils";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const ages = [60, 61, 62, 63, 64, 65];
const costs = {
  ages, total: [100000, 105000, 90000, 90000, 90000, 80000], basics: [70000, 70000, 70000, 70000, 70000, 70000],
  events: [{ age: 62, label: "Retire", year: 2028 }, { age: 65, label: "Medicare at 65", year: 2031 }],
};
const tip = () => m!.el.querySelector("[data-testid=costs-tip]");
const svg = () => m!.el.querySelector("svg") as SVGSVGElement;
const key = (k: string) => act(async () => { svg().dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true })); });

describe("Costs chart readout", () => {
  it("values match the data for an age", () => {
    const r = costsReadout(costs, 2);
    expect(r).toMatchObject({ age: 62, year: 2028, total: 90000, basics: 70000, extra: 20000, events: ["Retire"] });
    expect(r.text).toContain("$90,000");
  });
  it("keyboard steps, jumps and hides; the live region says it", async () => {
    m = await render(<CostsChart costs={costs} retireAge={62} />);
    expect(svg().getAttribute("tabindex")).toBe("0");
    expect(tip()).toBeNull();
    await key("ArrowRight");
    expect(tip()?.textContent).toContain("Age 60, 2026");
    await key("ArrowRight"); await key("ArrowRight");
    expect(tip()?.textContent).toContain("Age 62, 2028");
    expect(tip()?.textContent).toContain("Total $90,000 a year");
    expect(tip()?.textContent).toContain("On top of basics $20,000");
    expect(tip()?.textContent).toContain("Retire");
    const live = m.el.querySelector("[data-testid=costs-live]")!;
    expect(live.getAttribute("aria-live")).toBe("polite");
    expect(live.textContent).toContain("Age 62, 2028");
    await key("End");
    expect(tip()?.textContent).toContain("Medicare at 65");
    await key("ArrowRight");
    expect(tip()?.textContent).toContain("Age 65");
    await key("Home");
    expect(tip()?.textContent).toContain("Age 60");
    await key("Escape");
    expect(tip()).toBeNull();
  });
});
