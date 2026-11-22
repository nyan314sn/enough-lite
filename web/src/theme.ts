import { useCallback, useEffect, useState } from "react";

// Light or dark (Royal Indigo). The choice is kept in localStorage; with none, the first visit follows the operating system.
// index.html sets the same attribute before the page paints, so nothing flashes.
export type Theme = "light" | "dark";
export const THEME_KEY = "enough-theme";

export function storedTheme(): Theme | null {
  try { const v = localStorage.getItem(THEME_KEY); return v === "dark" || v === "light" ? v : null; } catch { return null; }
}

export function systemTheme(): Theme {
  try { return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; } catch { return "light"; }
}

export function applyTheme(t: Theme) {
  document.documentElement.setAttribute("data-theme", t);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", t === "dark" ? "#090914" : "#F7F7FC");
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => storedTheme() ?? systemTheme());
  useEffect(() => { applyTheme(theme); }, [theme]);
  const toggle = useCallback(() => {
    setTheme((t) => {
      const next: Theme = t === "dark" ? "light" : "dark";
      try { localStorage.setItem(THEME_KEY, next); } catch { /* private mode: the choice just lasts for this visit */ }
      return next;
    });
  }, []);
  return [theme, toggle];
}
