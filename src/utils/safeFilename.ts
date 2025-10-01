// safeFilename.ts

const WIN_RESERVED = new Set([
  "con","prn","aux","nul",
  "com1","com2","com3","com4","com5","com6","com7","com8","com9",
  "lpt1","lpt2","lpt3","lpt4","lpt5","lpt6","lpt7","lpt8","lpt9",
]);

const DEFAULT_NAME = "INVALID_FILENAME";

function utf8PercentEncodeChar(ch: string): string {
  const enc = new TextEncoder().encode(ch);
  let out = "";
  for (const b of enc) out += "%" + b.toString(16).toUpperCase().padStart(2, "0");
  return out;
}

/**
 * Returns a filename safe for common filesystems and URL contexts.
 * - Never returns null; falls back to "untitled" when necessary.
 * - Adjusts Windows-reserved and other special cases *before* encoding.
 * - Percent-encodes characters that are illegal across platforms.
 */
export default function safeFilename(input: string | null | undefined): string {
  // 1) Normalize + default early
  let name = (input ?? "").normalize("NFC");

  // If empty or only control chars, make up a name
  if (!name || /^[\u0000-\u001F\u007F]+$/.test(name)) {
    name = DEFAULT_NAME;
  }

  // 2) Pre-adjust special cases on the raw string (before percent-encoding)

  // Avoid exactly "." or ".." (common path specials)
  if (name === "." || name === "..") {
    name = `_${name}`;
  }

  // Avoid Windows reserved basenames (case-insensitive), looking only at the part before the first dot
  const rawBase = name.split(".")[0].toLowerCase();
  if (WIN_RESERVED.has(rawBase)) {
    name = `_${name}`;
  }

  // Avoid trailing space or dot on Windows by replacing them with underscores
  while (/[ .]$/.test(name)) {
    name = name.slice(0, -1) + "_";
  }

  // If the whole thing ends up empty again, fallback
  if (!name) name = DEFAULT_NAME;

  // 3) Percent-encode disallowed characters, leave allowed ones as-is
  // Cross-platform illegal set: < > : " / \ | ? * and control chars
  let encoded = "";
  for (const ch of name) {
    const code = ch.codePointAt(0)!;

    // Control chars & DEL never allowed
    if (code <= 0x1F || code === 0x7F) {
      encoded += utf8PercentEncodeChar(ch);
      continue;
    }

    // Slash is always illegal (already covered by the class below, but keep explicit)
    if (ch === "/") {
      encoded += "%2F";
      continue;
    }

    // Cross-platform illegal set
    if (/[<>:"/\\|?*]/.test(ch)) {
      encoded += utf8PercentEncodeChar(ch);
      continue;
    }

    encoded += ch;
  }

  // 4) Final safety: if somehow we ended up empty, fall back
  if (!encoded) return DEFAULT_NAME;

  return encoded;
}
