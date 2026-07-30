/**
 * Fast local estimate shown immediately in the UI, before the
 * server's AI-generated summary (with its own count) arrives.
 */
export function estimateReadingTime(markdown = "", wordsPerMinute = 200) {
  const plain = markdown
    .replace(/```[\s\S]*?```/g, "") // strip code blocks
    .replace(/[#*_>`~-]/g, "") // strip markdown symbols
    .trim();

  const words = plain.length ? plain.split(/\s+/).length : 0;
  const minutes = Math.max(1, Math.round(words / wordsPerMinute));

  return { words, minutes };
}
