import { useEffect, useRef, useState, type KeyboardEvent as KeyEv } from "react";

// Shared by the analysis charts: the chart's width, and one point picked by hover, tap or the arrow keys.
// Arrow keys step, Home and End jump, Escape hides. A mouse that leaves hides the readout; a tap keeps it.

export function useWidth(initial = 560) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(initial);
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(260, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { box, w };
}

export function useReadout(n: number, indexAt: (px: number) => number) {
  const [hover, setHover] = useState<number | null>(null);
  const clamp = (i: number) => Math.max(0, Math.min(n - 1, i));
  const pick = (clientX: number, rect: DOMRect, w: number) => setHover(clamp(indexAt(((clientX - rect.left) / (rect.width || w)) * w)));
  const onKey = (e: KeyEv) => {
    const cur = hover ?? -1;
    let next: number | null = null;
    if (e.key === "ArrowRight") next = clamp(cur + 1);
    else if (e.key === "ArrowLeft") next = cur < 0 ? 0 : clamp(cur - 1);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = n - 1;
    else if (e.key === "Escape") { setHover(null); return; }
    else return;
    e.preventDefault();
    setHover(next);
  };
  const hi = hover != null && hover >= 0 && hover < n ? hover : null;
  return { hi, setHover, pick, onKey };
}
