import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { mockApi } from "./mock";
import { THEME_KEY } from "./theme";
import { click, render, type Mounted } from "./test-utils";

const mem = new Map<string, string>();
Object.defineProperty(globalThis, "localStorage", { configurable: true, value: { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v), removeItem: (k: string) => void mem.delete(k), clear: () => mem.clear() } });

let m: Mounted | null = null;
const osDark = (dark: boolean) => vi.stubGlobal("matchMedia", (q: string) => ({ matches: dark && q.includes("dark"), media: q, addEventListener() {}, removeEventListener() {} }));
beforeEach(() => { mem.clear(); document.documentElement.removeAttribute("data-theme"); });
afterEach(() => { m?.unmount(); m = null; vi.unstubAllGlobals(); });
const toggle = () => m!.el.querySelector<HTMLButtonElement>("button.theme-toggle")!;

describe("Light and dark theme", () => {
  it("starts light with no saved choice and no dark OS preference, and offers Dark", async () => {
    osDark(false);
    m = await render(<App api={mockApi} admin={false} />);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(toggle().textContent).toContain("Dark");
    expect(toggle().getAttribute("aria-label")).toBe("Switch to dark mode");
    expect(toggle().querySelector("svg")).toBeTruthy();
  });

  it("follows a dark OS preference on the first visit, without saving it", async () => {
    osDark(true);
    m = await render(<App api={mockApi} admin={false} />);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(toggle().textContent).toContain("Light");
    expect(mem.get(THEME_KEY)).toBeUndefined();
  });

  it("sets data-theme on the page and remembers the choice", async () => {
    osDark(false);
    m = await render(<App api={mockApi} admin={false} />);
    await click(toggle());
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(mem.get(THEME_KEY)).toBe("dark");
    await click(toggle());
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(mem.get(THEME_KEY)).toBe("light");
  });

  it("a saved choice beats the OS preference", async () => {
    osDark(true);
    mem.set(THEME_KEY, "light");
    m = await render(<App api={mockApi} admin={false} />);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("the toggle is at least 44 px tall by its stylesheet rule and keeps no raw colours in the app styles", async () => {
    const fs: { readFileSync: (p: string, e: string) => string } = await import(/* @vite-ignore */ "node:" + "fs");
    const css = fs.readFileSync("src/styles.css", "utf-8");
    expect(css).toMatch(/\.theme-toggle \{[^}]*min-height: 44px/);
    const body = css.slice(css.indexOf("* { box-sizing"));
    // only the hand-inked portrait skin and ink colours may stay hard-coded below the token blocks
    const raw = (body.match(/#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)/g) ?? []).map((c: string) => c.toLowerCase());
    expect(raw.filter((c: string) => !["#26354d", "#e0b65a", "#efcdb0", "#d6a17a", "#b9784e", "#7b4b33"].includes(c))).toEqual([]);
  });
});
