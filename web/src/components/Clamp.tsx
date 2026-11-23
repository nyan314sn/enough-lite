import { useState } from "react";
import { PLAN_WORDS, shortText } from "../readiness";

/** A text that may run long (most come from the server): whole sentences up to `words` words, and a "more" button for the rest. */
export default function Clamp({ text, words = 16, className, testid, as: Tag = "p" }: { text: string; words?: number; className?: string; testid?: string; as?: "p" | "span" }) {
  const [open, setOpen] = useState(false);
  const short = shortText(text, words);
  if (short === text.trim()) return <Tag className={className}><span data-testid={testid}>{text}</span></Tag>;
  return (
    <Tag className={className}>
      <span data-testid={testid}>{open ? text : short}</span>{" "}
      <button type="button" className="more-btn" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {open ? PLAN_WORDS.less : PLAN_WORDS.more}<span className="sr-only">{open ? ": show less" : ": show the full text"}</span>
      </button>
    </Tag>
  );
}
