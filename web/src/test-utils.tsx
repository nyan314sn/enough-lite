import { act, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";

// A tiny render helper (no testing-library): mount into jsdom, act() around updates, query the DOM directly.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

export interface Mounted { el: HTMLElement; root: Root; unmount: () => void }

export async function render(ui: ReactElement): Promise<Mounted> {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const root = createRoot(el);
  await act(async () => { root.render(ui); });
  return { el, root, unmount: () => { act(() => root.unmount()); el.remove(); } };
}

export async function click(node: Element | null | undefined) {
  if (!node) throw new Error("nothing to click");
  await act(async () => { (node as HTMLElement).click(); });
}

/** Let pending promises and timers settle. */
export async function flush(times = 3) {
  for (let i = 0; i < times; i++) await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

export const byText = (root: ParentNode, sel: string, text: string | RegExp) =>
  Array.from(root.querySelectorAll(sel)).find((n) => (typeof text === "string" ? n.textContent?.includes(text) : text.test(n.textContent ?? "")));

/** Wait until a condition holds (the mock stream arrives in many small timer steps). */
export async function until(cond: () => unknown, tries = 400) {
  for (let i = 0; i < tries && !cond(); i++) await flush(1);
  if (!cond()) throw new Error("condition never became true");
}
