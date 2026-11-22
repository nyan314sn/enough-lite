import type { Theme } from "../theme";

/** The header switch. Its text names the theme you will get when you press it; the icon shows the same. */
export default function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  const next = theme === "dark" ? "Light" : "Dark";
  return (
    <button type="button" className="btn btn-quiet btn-small theme-toggle" data-theme-toggle onClick={onToggle} aria-label={`Switch to ${next.toLowerCase()} mode`}>
      <svg className="theme-icon" viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {theme === "dark"
          ? <><circle cx="10" cy="10" r="3.6" /><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.3 4.3l1.4 1.4M14.3 14.3l1.4 1.4M4.3 15.7l1.4-1.4M14.3 5.7l1.4-1.4" /></>
          : <path d="M16.5 11.8A7 7 0 0 1 8.2 3.5a7 7 0 1 0 8.3 8.3z" />}
      </svg>
      <span>{next}</span>
    </button>
  );
}
