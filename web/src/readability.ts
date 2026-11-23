// A small reading-grade check for the tests (R26: grade 8 or lower). Flesch-Kincaid grade level:
//   grade = 0.39 × (words ÷ sentences) + 11.8 × (syllables ÷ words) − 15.59
// Syllables are counted by vowel groups with the usual silent-e fixes; a figure such as $23,300 or 401(k) counts as one short word.

export function syllables(word: string): number {
  const w = word.toLowerCase().replace(/[^a-z]/g, "");
  if (!w) return 1;          // a figure: read as one unit
  if (w.length <= 3) return 1;
  const trimmed = w.replace(/(?:[^laeiouy]es|[^laeiouy]ed|[^laeiouy]e)$/, "").replace(/^y/, "");
  const groups = trimmed.match(/[aeiouy]{1,2}/g);
  return Math.max(1, groups?.length ?? 1);
}

export function fkGrade(text: string): number {
  const sentences = Math.max(1, (text.match(/[.!?]+(\s|$)/g) ?? []).length || 1);
  const words = text.split(/\s+/).map((w) => w.replace(/^[^\w$]+|[^\w%)]+$/g, "")).filter(Boolean);
  if (words.length === 0) return 0;
  const syl = words.reduce((t, w) => t + syllables(w), 0);
  return 0.39 * (words.length / sentences) + 11.8 * (syl / words.length) - 15.59;
}
